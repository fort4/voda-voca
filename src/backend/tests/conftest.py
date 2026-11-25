# 2026-11-02 - voda-voca - 테스트 공통 fixture: 임시 SQLite DB(마이그레이션 적용), 엔진 정리, 빠른 bcrypt, 테스트 계정 정리 (2026-11-25 SQLite 전환)
# 파일 위치: src/backend/tests/conftest.py

from collections.abc import AsyncIterator, Awaitable, Callable, Iterator, Mapping, Sequence
import asyncio
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from sqlalchemy import delete

from backend.core.config import get_settings
from backend.core.rate_limit import login_rate_limiter
from backend.db import session as db_session_module
from backend.db.session import dispose_engine, get_session_factory
from backend.models import SystemVocabulary, SystemWord, User
from backend.services.system_seed import init_system_seeds
from backend.tests.helpers import TEST_VOCABULARY_SLUG_PREFIX, TestVocabulary

# 테스트 계정 닉네임 패턴. 정리(cleanup) 시 이 패턴만 지운다.
TEST_NICKNAME_LIKE = "tvoda-%"

BACKEND_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def _test_database(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    """DB 를 쓰는 테스트가 공유하는 임시 SQLite 파일. Alembic 마이그레이션(운영과 같은 경로)으로 만든다.

    개발자의 실제 DB(.env 의 DB_PATH)를 건드리지 않도록 항상 임시 경로로 덮어쓴다. Docker 도 필요 없다.
    `no_db` 테스트는 이 fixture 를 요청하지 않아 DB 파일이 만들어지지 않는다.
    """
    db_file = tmp_path_factory.mktemp("db") / "voca-test.db"
    previous = os.environ.get("DB_PATH")
    os.environ["DB_PATH"] = str(db_file)
    for cached in (get_settings, db_session_module.get_engine, db_session_module.get_session_factory):
        cached.cache_clear()
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    # env.py 가 asyncio.run 을 쓰므로, 이미 이벤트 루프가 도는 스레드(비동기 fixture 안)에서는 새 스레드에서 실행한다.
    with ThreadPoolExecutor(max_workers=1) as pool:
        pool.submit(command.upgrade, config, "head").result()
        # 실제 서버는 시작할 때 표준 단어장 시드를 적재한다 (lifespan). 테스트 DB 도 같은 상태로 맞춘다.
        pool.submit(asyncio.run, init_system_seeds()).result()
        pool.submit(asyncio.run, dispose_engine()).result()
    yield db_file
    if previous is None:
        os.environ.pop("DB_PATH", None)
    else:
        os.environ["DB_PATH"] = previous
    for cached in (get_settings, db_session_module.get_engine, db_session_module.get_session_factory):
        cached.cache_clear()


@pytest_asyncio.fixture(autouse=True)
async def _dispose_db_engine() -> AsyncIterator[None]:
    """각 테스트가 끝나면 엔진을 닫는다.

    pytest-asyncio 는 테스트마다 이벤트 루프를 새로 만든다. 풀에 남은 커넥션은 이전 루프에
    묶여 있으므로, 테스트 사이에 정리하지 않으면 다음 테스트에서 루프 불일치 오류가 난다.
    """
    yield
    await dispose_engine()


@pytest.fixture(autouse=True)
def _reset_login_rate_limiter() -> Iterator[None]:
    """로그인 실패 집계는 프로세스 전역이다. 테스트마다 비워 서로의 실패가 섞이지 않게 한다."""
    login_rate_limiter.clear()
    yield
    login_rate_limiter.clear()


@pytest.fixture(autouse=True)
def _fast_bcrypt(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """테스트에서는 bcrypt cost 를 4 로 낮춰 실행 시간을 줄인다. 운영 기본값은 12 이다."""
    monkeypatch.setenv("BCRYPT_ROUNDS", "4")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _skips_db(request: pytest.FixtureRequest) -> bool:
    """`no_db` 표시가 붙은 순수 단위 테스트는 DB 정리를 건너뛴다 (DB 파일 없이도 돌아가야 한다)."""
    return request.node.get_closest_marker("no_db") is not None


@pytest_asyncio.fixture(autouse=True)
async def _cleanup_test_users(request: pytest.FixtureRequest) -> AsyncIterator[None]:
    """테스트 계정(과 그 세션, FK CASCADE)을 테스트 전후로 지운다. `no_db` 테스트는 건너뛴다."""
    if _skips_db(request):
        yield
        return
    request.getfixturevalue("_test_database")
    await _delete_test_users()
    yield
    await _delete_test_users()
    await dispose_engine()


async def _delete_test_users() -> None:
    async with get_session_factory()() as session:
        await session.execute(delete(User).where(User.nickname.like(TEST_NICKNAME_LIKE)))
        await session.commit()


@pytest_asyncio.fixture(autouse=True)
async def _cleanup_test_vocabularies(request: pytest.FixtureRequest) -> AsyncIterator[None]:
    """테스트가 만든 표준 단어장(slug 가 tvoda- 로 시작)을 테스트 전후로 지운다 (단어·북마크·이력은 CASCADE). `no_db` 는 건너뛴다."""
    if _skips_db(request):
        yield
        return
    await _delete_test_vocabularies()
    yield
    await _delete_test_vocabularies()


async def _delete_test_vocabularies() -> None:
    async with get_session_factory()() as session:
        await session.execute(
            delete(SystemVocabulary).where(SystemVocabulary.slug.like(f"{TEST_VOCABULARY_SLUG_PREFIX}%"))
        )
        await session.commit()


@pytest_asyncio.fixture
async def make_vocabulary() -> AsyncIterator[Callable[..., Awaitable[TestVocabulary]]]:
    """표준 단어장을 만드는 팩토리. 단어는 term 목록으로 주고, 뜻과 예문은 term 에서 만든다.

    사용: vocab = await make_vocabulary(["apple", "banana", "cherry", "date"])
    발음기호가 필요하면 phonetics={"apple": "ˈæpəl"} 처럼 term → IPA 로 준다 (없으면 NULL).
    품사가 필요하면 parts_of_speech={"apple": "noun"} 처럼 term → 품사로 준다 (없으면 NULL).
    표준 단어장은 공용 콘텐츠라 사용자가 만들 수 없으므로, 테스트는 DB 에 직접 넣는다. 테스트가 끝나면 지운다.
    """

    async def _make(
        terms: Sequence[str],
        *,
        title: str = "테스트 단어장",
        category: str = "ELEMENTARY",
        level: int = 1,
        phonetics: Mapping[str, str] | None = None,
        parts_of_speech: Mapping[str, str] | None = None,
    ) -> TestVocabulary:
        slug = f"{TEST_VOCABULARY_SLUG_PREFIX}{uuid.uuid4().hex[:10]}"
        async with get_session_factory()() as session:
            vocabulary = SystemVocabulary(
                slug=slug, title=title, category=category, level=level, total_words=len(terms)
            )
            session.add(vocabulary)
            await session.flush()
            words = [
                SystemWord(
                    vocabulary_id=vocabulary.id,
                    term=term,
                    meaning=f"{term}의 뜻",
                    example=f"I like {term}.",
                    example_meaning=f"나는 {term}을(를) 좋아한다.",
                    phonetic=(phonetics or {}).get(term),
                    pos=(parts_of_speech or {}).get(term),
                    order_index=index,
                )
                for index, term in enumerate(terms)
            ]
            session.add_all(words)
            await session.commit()
            return TestVocabulary(
                id=vocabulary.id, slug=slug, title=title, word_ids={w.term: w.id for w in words}
            )

    yield _make
