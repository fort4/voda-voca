# 2026-11-19 - voda-voca - 회귀 방지: no_db 표시가 붙은 테스트는 MySQL 이 없어도 통과해야 한다 (REQ-118)
# 파일 위치: src/backend/tests/test_no_db_guard.py
"""순수 단위 테스트(DB 를 쓰지 않는 테스트)가 DB 기동 여부에 묶이지 않도록 지키는 검사.

conftest 의 autouse 정리 fixture 는 DB 에 접속한다. 순수 단위 테스트에는 `no_db` 표시를 붙여 그 정리를 건너뛴다.
이 테스트는 접속할 수 없는 포트(1)를 가리킨 하위 pytest 로 `no_db` 테스트만 돌려, 표시가 거짓이 아닌지
(표시된 테스트가 실제로 DB 를 건드리지 않는지) 확인한다. 새 단위 테스트가 DB 를 쓰게 되면 여기서 실패한다.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.no_db

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parents[2]


def test_no_db_marked_tests_pass_without_a_database() -> None:
    env = {**os.environ, "MYSQL_HOST": "127.0.0.1", "MYSQL_PORT": "1"}  # 1번 포트는 닫혀 있다
    result = subprocess.run(
        [
            sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
            "-m", "no_db", "--ignore", str(Path(__file__)), str(TESTS_DIR),
        ],
        cwd=REPO_ROOT, env=env, capture_output=True, text=True, timeout=180,
    )
    tail = (result.stdout + result.stderr)[-3000:]
    assert result.returncode == 0, tail
    assert " passed" in result.stdout, tail
