# 2026-11-02 - voda-voca - Alembic 마이그레이션 환경 (비동기 엔진, 설정 모듈 연동)
# 파일 위치: src/backend/alembic/env.py

import asyncio
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy.engine import Connection

from alembic import context

# src/ 를 import 경로에 추가해 `backend` 패키지를 찾을 수 있게 한다.
# 이 파일 기준 세 단계 상위가 src/ 이다 (src/backend/alembic/env.py).
SRC_DIR = Path(__file__).resolve().parents[2]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from backend.core.config import get_settings  # noqa: E402
from backend.db.session import dispose_engine, get_engine  # noqa: E402
from backend.models import Base  # noqa: E402

config = context.config

# alembic.ini 의 logging 설정을 적용한다.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# autogenerate 가 비교할 기준 스키마. 모든 모델은 models/__init__.py 에서 등록된다.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """오프라인 모드: DB 연결 없이 SQL 스크립트만 출력한다."""
    context.configure(
        url=get_settings().database_url.render_as_string(hide_password=False),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """온라인 모드: 애플리케이션과 같은 비동기 엔진으로 마이그레이션을 실행한다."""
    connectable = get_engine()

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await dispose_engine()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
