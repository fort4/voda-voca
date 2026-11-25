# 2026-11-25 - voda-voca - 설정 모듈 단위 테스트 (SQLite 접속 URL 조립, 환경 변수 주입, 비밀값 노출 방지)
# 파일 위치: src/backend/tests/test_config.py

import pytest
from pydantic import SecretStr

from backend.core.config import Settings


pytestmark = pytest.mark.no_db  # DB 서버 없이 통과해야 한다 (test_no_db_guard.py)


def test_database_url_uses_aiosqlite_driver_and_db_path() -> None:
    url = Settings(db_path="/data/voca.db").database_url
    assert url.drivername == "sqlite+aiosqlite"
    assert url.database == "/data/voca.db"
    assert url.host is None and url.password is None  # 서버·계정 개념이 없다


def test_db_path_defaults_to_data_volume(monkeypatch: pytest.MonkeyPatch) -> None:
    # 과제 서버 규칙: 실행 중 쓰기는 /data 와 /tmp 에만 허용된다. 외부 환경(.env, 셸)에 영향받지 않게 격리한다.
    monkeypatch.delenv("DB_PATH", raising=False)
    assert Settings(_env_file=None).db_path == "/data/voca.db"


def test_db_path_is_read_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DB_PATH", "/tmp/other.db")
    assert Settings().database_url.database == "/tmp/other.db"


def test_no_mysql_settings_remain() -> None:
    fields = set(Settings.model_fields)
    assert not {f for f in fields if f.startswith("mysql_")}


def test_secret_key_is_optional_and_masked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SECRET_KEY", raising=False)
    assert Settings(_env_file=None).secret_key is None
    settings = Settings(secret_key=SecretStr("very-secret"))
    assert "very-secret" not in repr(settings)
