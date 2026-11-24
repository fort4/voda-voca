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


# ---------- docker-compose.yml (2단계: mysql + migrate + app) ----------

COMPOSE = REPO_ROOT / "docker" / "docker-compose.yml"


def _compose() -> dict:
    import yaml  # 개발 의존성(PyYAML)은 requirements-dev 에 포함된다

    return yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))


def test_compose_has_mysql_migrate_app_services() -> None:
    assert {"mysql", "migrate", "app"} <= set(_compose()["services"])


def test_compose_keeps_mysql_data_volume_and_name() -> None:
    """DB 컨테이너 이름과 데이터 볼륨 이름이 바뀌면 기존 개발 데이터를 잃은 것처럼 보인다 (회귀 방지)."""
    c = _compose()
    assert c["services"]["mysql"]["container_name"] == "voda-voca-mysql"
    assert c["volumes"]["mysql_data"]["name"] == "voda-voca-mysql-data"


@pytest.mark.parametrize("name", ["migrate", "app"])
def test_app_services_reach_db_by_service_name_not_loopback(name: str) -> None:
    env = _compose()["services"][name]["environment"]
    assert env["MYSQL_HOST"] == "mysql", "컨테이너 안의 127.0.0.1 은 자기 자신이다"
    assert str(env["MYSQL_PORT"]) == "3306", "컨테이너 사이 통신은 호스트 노출 포트(3307)가 아니라 3306 이다"


@pytest.mark.parametrize("name", ["migrate", "app"])
def test_app_services_get_only_needed_env_never_root_password(name: str) -> None:
    svc = _compose()["services"][name]
    assert "env_file" not in svc, ".env 를 통째로 넘기면 루트 비밀번호까지 앱에 전달된다"
    assert "MYSQL_ROOT_PASSWORD" not in svc["environment"]
    for needed in ["MYSQL_USER", "MYSQL_PASSWORD", "MYSQL_DATABASE"]:
        assert needed in svc["environment"]


def test_startup_order_mysql_healthy_then_migrate_then_app() -> None:
    services = _compose()["services"]
    assert services["migrate"]["depends_on"]["mysql"]["condition"] == "service_healthy"
    assert services["app"]["depends_on"]["mysql"]["condition"] == "service_healthy"
    assert services["app"]["depends_on"]["migrate"]["condition"] == "service_completed_successfully"


def test_migrate_runs_once_and_app_restarts() -> None:
    services = _compose()["services"]
    assert services["migrate"]["restart"] in ("no", False)
    assert " ".join(services["migrate"]["command"]) == "alembic -c src/backend/alembic.ini upgrade head"
    assert services["app"]["restart"] == "unless-stopped"


def test_app_uses_prod_image_without_source_mount() -> None:
    app = _compose()["services"]["app"]
    assert app["build"]["target"] == "prod"
    assert "volumes" not in app, "배포용 앱은 소스를 마운트하지 않는다 (개발용은 override 파일에서)"
    assert "${APP_PORT:-8000}:8000" in app["ports"]


# ---------- docker-compose.dev.yml (3단계: 개발용 override) ----------

COMPOSE_DEV = REPO_ROOT / "docker" / "docker-compose.dev.yml"


def _dev() -> dict:
    import yaml

    return yaml.safe_load(COMPOSE_DEV.read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", ["migrate", "app"])
def test_dev_override_builds_dev_target_and_mounts_source(name: str) -> None:
    svc = _dev()["services"][name]
    assert svc["build"]["target"] == "dev"
    assert svc["image"] == "voda-voca:dev", "prod 이미지 태그와 섞이지 않게 한다"
    assert "./src:/app/src" in svc["volumes"], "소스를 마운트해야 --reload 와 새 마이그레이션이 바로 반영된다"


def test_dev_override_never_mounts_env_file_or_whole_repo() -> None:
    """저장소 전체(.)나 .env 를 마운트하면 루트 비밀번호가 컨테이너에 노출된다."""
    for name in ("migrate", "app"):
        for mount in _dev()["services"][name]["volumes"]:
            source = mount.split(":")[0]
            assert source not in (".", "./", "./.env"), f"{mount} 는 마운트하면 안 된다"
            assert ".env" not in source.split("/")[-1] or source.endswith(".env.example")


def test_dev_override_mounts_what_the_tests_read_as_read_only() -> None:
    mounts = _dev()["services"]["app"]["volumes"]
    for needed in ["./pytest.ini:/app/pytest.ini:ro", "./.coveragerc:/app/.coveragerc:ro",
                   "./docker:/app/docker:ro", "./.dockerignore:/app/.dockerignore:ro"]:
        assert needed in mounts


def test_dev_override_disables_pytest_cache_in_readonly_workdir() -> None:
    """/app 은 root 소유라 app 사용자가 .pytest_cache 를 쓸 수 없다. 경고 대신 캐시를 끈다."""
    assert _dev()["services"]["app"]["environment"]["PYTEST_ADDOPTS"] == "-p no:cacheprovider"


@pytest.mark.parametrize("name", ["migrate", "app"])
@pytest.mark.parametrize("var", ["MYSQL_DATABASE", "MYSQL_USER", "MYSQL_PASSWORD"])
def test_required_db_settings_fail_fast_when_env_is_missing(name: str, var: str) -> None:
    """새 PC 에서 .env 를 만들지 않고 실행하면 빈 비밀번호로 조용히 시작하는 대신, 안내 메시지와 함께 중단된다."""
    value = str(_compose()["services"][name]["environment"][var])
    assert value.startswith("${" + var + ":?"), f"{var} 는 필수 표기(:?)여야 한다"
    assert ".env" in value, "메시지에 .env 를 만들라는 안내가 있어야 한다"


def test_mysql_host_port_is_bound_to_loopback_only() -> None:
    """DB 포트를 모든 인터페이스에 열면 같은 망의 누구든 접속을 시도할 수 있다. 호스트(127.0.0.1)에서만 열고,
    앱 컨테이너는 내부 네트워크(mysql:3306)로 접속한다."""
    ports = _compose()["services"]["mysql"]["ports"]
    assert ports == ["127.0.0.1:${MYSQL_PORT:-3306}:3306"]
