#!/bin/sh
# 2026-11-25 - voda-voca - 컨테이너 진입점: 마이그레이션 적용 후 전달받은 명령(uvicorn)으로 교체 실행
# 파일 위치: docker-entrypoint.sh
set -e

# 빈 DB 에서 시작해도 테이블이 만들어진다 (VOCA-NFR-003). 이미 최신이면 아무 일도 하지 않는다.
alembic -c src/backend/alembic.ini upgrade head

# 셸이 PID 1 로 남지 않고 서버로 교체되어, 종료 신호(SIGTERM)가 서버에 직접 전달된다.
exec "$@"
