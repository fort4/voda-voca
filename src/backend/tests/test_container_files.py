# 2026-11-24 - voda-voca - 컨테이너 빌드 파일 안전 검사: 비밀·로컬 자산이 이미지에 들어가지 않고 비root 로 실행된다
# 파일 위치: src/backend/tests/test_container_files.py
"""Dockerfile 과 .dockerignore 가 지켜야 할 규칙을 정적으로 검사한다 (Docker 불필요).

이미지는 한 번 만들어 다른 컴퓨터로 옮기는 물건이다. `.env`(비밀번호)나 `.venv` 가 실수로 들어가면
외부에 유출되거나 이미지가 비대해지므로, 빌드 전에 파일 내용만으로 잡는다 (CLAUDE.md §5.3, REQ-112).
"""

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.no_db

REPO_ROOT = Path(__file__).resolve().parents[3]
DOCKERFILE = REPO_ROOT / "docker" / "Dockerfile"
DOCKERIGNORE = REPO_ROOT / ".dockerignore"


def _ignore_patterns() -> set[str]:
    lines = DOCKERIGNORE.read_text(encoding="utf-8").splitlines()
    return {line.strip() for line in lines if line.strip() and not line.startswith("#")}


def test_dockerignore_excludes_secrets_and_local_artifacts() -> None:
    patterns = _ignore_patterns()
    for required in [".env", ".env.*", ".venv", ".git", "ai-agent", "**/__pycache__"]:
        assert required in patterns, f".dockerignore 에 {required} 가 없다"
    # .env.example 은 템플릿이라 이미지에 들어가도 되지만, 막는다고 해서 문제는 없다. 예외 규칙만 확인한다.
    assert "!.env.example" not in patterns or ".env.*" in patterns


def test_dockerfile_has_three_stages_base_dev_prod() -> None:
    stages = re.findall(r"^FROM\s+\S+\s+AS\s+(\w+)", DOCKERFILE.read_text(encoding="utf-8"), re.M | re.I)
    assert stages == ["base", "dev", "prod"]


def test_dockerfile_does_not_copy_env_files_or_bake_secrets() -> None:
    text = DOCKERFILE.read_text(encoding="utf-8")
    assert not re.search(r"^\s*COPY\s+.*\.env", text, re.M), ".env 를 이미지에 복사하면 안 된다"
    assert not re.search(r"^\s*(ENV|ARG)\s+\w*(PASSWORD|SECRET)", text, re.M | re.I), "비밀번호를 이미지에 굽지 않는다"


def test_dockerfile_pins_python_minor_version() -> None:
    first_from = re.search(r"^FROM\s+(\S+)", DOCKERFILE.read_text(encoding="utf-8"), re.M)
    assert first_from and re.fullmatch(r"python:3\.12-slim", first_from.group(1)), "개발 환경과 같은 3.12 로 고정한다"


def test_dockerfile_runs_as_non_root_in_dev_and_prod() -> None:
    text = DOCKERFILE.read_text(encoding="utf-8")
    dev, prod = text.split(" AS dev", 1)[1].split(" AS prod", 1)
    assert re.search(r"^USER\s+app\b", dev, re.M), "dev 단계는 비root 로 실행한다"
    assert re.search(r"^USER\s+app\b", prod, re.M), "prod 단계는 비root 로 실행한다"


def test_prod_stage_has_healthcheck_and_no_reload() -> None:
    prod = DOCKERFILE.read_text(encoding="utf-8").split(" AS prod", 1)[1]
    assert "HEALTHCHECK" in prod and "/health" in prod
    assert "--reload" not in prod
