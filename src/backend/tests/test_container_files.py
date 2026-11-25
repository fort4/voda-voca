# 2026-11-24 - voda-voca - 컨테이너 빌드 파일 정적 검사: 비밀·로컬 자산 제외, 과제 서버 규칙(8080, UID 10001, /data, SQLite) (2026-11-25 SQLite 전환)
# 파일 위치: src/backend/tests/test_container_files.py
"""Dockerfile, entrypoint, compose, .dockerignore 가 지켜야 할 규칙을 정적으로 검사한다 (Docker 불필요).

이미지는 한 번 만들어 다른 컴퓨터(학교 서버)로 옮기는 물건이다. `.env`(비밀)나 `.venv`, 로컬 DB 파일이 실수로 들어가면
유출되거나 이미지가 비대해지므로, 빌드 전에 파일 내용만으로 잡는다 (CLAUDE.md §5.3, REQ-112).
과제 서버 규칙(공지 4.4, R-01~R-10)도 여기서 고정한다: 리포 루트 Dockerfile, 0.0.0.0:8080, UID 10001, 쓰기는 /data 와 /tmp 만.
"""

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.no_db

REPO_ROOT = Path(__file__).resolve().parents[3]
DOCKERFILE = REPO_ROOT / "Dockerfile"
ENTRYPOINT = REPO_ROOT / "docker-entrypoint.sh"
DOCKERIGNORE = REPO_ROOT / ".dockerignore"
GITATTRIBUTES = REPO_ROOT / ".gitattributes"
GITIGNORE = REPO_ROOT / ".gitignore"


def _dockerfile() -> str:
    return DOCKERFILE.read_text(encoding="utf-8")


def _stage(name: str) -> str:
    """`FROM ... AS name` 부터 다음 FROM 직전까지."""
    parts = re.split(r"^(?=FROM\s)", _dockerfile(), flags=re.M)
    return next(p for p in parts if re.match(rf"FROM\s+\S+\s+AS\s+{name}\b", p, re.I))


def _code(text: str) -> str:
    """주석 줄을 뺀 실제 설정만 남긴다 (설명 주석에 옛 이름이 언급되어도 검사가 걸리지 않게)."""
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))


def _ignore_patterns() -> set[str]:
    lines = DOCKERIGNORE.read_text(encoding="utf-8").splitlines()
    return {line.strip() for line in lines if line.strip() and not line.startswith("#")}


# ---------- .dockerignore / .gitattributes / .gitignore ----------


def test_dockerignore_excludes_secrets_and_local_artifacts() -> None:
    patterns = _ignore_patterns()
    for required in [".env", ".env.*", ".venv", ".git", "ai-agent", "**/__pycache__"]:
        assert required in patterns, f".dockerignore 에 {required} 가 없다"
    assert "!.env.example" not in patterns or ".env.*" in patterns


@pytest.mark.parametrize("pattern", ["*.db", "*.db-wal", "*.db-shm", "data"])
def test_dockerignore_excludes_local_sqlite_files(pattern: str) -> None:
    """개발 중 만든 DB 파일(사용자 계정 포함)이 이미지에 들어가면 안 된다."""
    assert pattern in _ignore_patterns()


def test_dockerignore_does_not_exclude_what_the_image_needs() -> None:
    patterns = _ignore_patterns()
    assert "docker" not in patterns or ENTRYPOINT.parent != REPO_ROOT / "docker"
    for needed in ("src", "requirements.txt", "docker-entrypoint.sh", "Dockerfile"):
        assert needed not in patterns, f"{needed} 는 이미지에 필요하다"


def test_gitattributes_forces_lf_line_endings() -> None:
    """Windows 에서 CRLF 로 체크아웃되면 셸 스크립트가 `bad interpreter` 로 죽는다."""
    text = GITATTRIBUTES.read_text(encoding="utf-8")
    assert re.search(r"^\*\s+text=auto\s+eol=lf\s*$", text, re.M)


@pytest.mark.parametrize("pattern", ["*.db", "*.db-wal", "*.db-shm"])
def test_gitignore_excludes_sqlite_files(pattern: str) -> None:
    assert pattern in GITIGNORE.read_text(encoding="utf-8").splitlines()


# ---------- Dockerfile ----------


def test_dockerfile_is_at_repo_root_with_prod_as_last_stage() -> None:
    """`docker build .` 한 번에 배포용 이미지가 나와야 한다 (VOCA-SUB-031). 마지막 스테이지가 기본 빌드 대상이다."""
    stages = re.findall(r"^FROM\s+\S+\s+AS\s+(\w+)", _dockerfile(), re.M | re.I)
    assert stages == ["base", "dev", "prod"]
    assert not (REPO_ROOT / "docker" / "Dockerfile").exists(), "Dockerfile 이 두 곳에 있으면 서로 어긋난다"


def test_dockerfile_does_not_copy_env_files_or_bake_secrets() -> None:
    text = _dockerfile()
    assert not re.search(r"^\s*COPY\s+.*\.env", text, re.M), ".env 를 이미지에 복사하면 안 된다"
    assert not re.search(r"^\s*(ENV|ARG)\s+\w*(PASSWORD|SECRET)", text, re.M | re.I), "비밀을 이미지에 굽지 않는다"


def test_dockerfile_pins_python_minor_version() -> None:
    first_from = re.search(r"^FROM\s+(\S+)", _dockerfile(), re.M)
    assert first_from and re.fullmatch(r"python:3\.12-slim", first_from.group(1)), "개발 환경과 같은 3.12 로 고정한다"


def test_dockerfile_uses_no_forbidden_build_features() -> None:
    """점검 워크플로는 인터넷이 없는 환경에서 빌드한다. 외부 접근이 필요한 빌드 기능은 쓸 수 없다 (R-10)."""
    text = _dockerfile()
    assert not re.match(r"\s*#\s*syntax\s*=", text, re.I), "# syntax 지시어 금지"
    assert not re.search(r"--mount\s*=\s*type\s*=\s*(ssh|secret)", text)
    assert not re.search(r"RUN\s+--(network|security)\b", text)
    assert not re.search(r":latest\b", text), "이미지 태그는 버전을 명시한다"


def test_prod_runs_as_uid_10001_without_privileges() -> None:
    prod = _stage("prod")
    assert re.search(r"useradd[^\n]*--uid\s+10001", _dockerfile()), "UID 10001 사용자를 만든다"
    assert re.search(r"^USER\s+(10001|app)\b", prod, re.M)


def test_dev_runs_as_non_root() -> None:
    assert re.search(r"^USER\s+\S+", _stage("dev"), re.M)


def test_prod_listens_on_0_0_0_0_8080_with_proxy_headers() -> None:
    prod = _stage("prod")
    assert "EXPOSE 8080" in prod
    cmd = re.search(r"^CMD\s+(\[.*\])", prod, re.M)
    assert cmd, "exec 형식(JSON 배열) CMD 를 쓴다"
    args = cmd.group(1)
    for token in ('"uvicorn"', '"0.0.0.0"', '"8080"', '"--proxy-headers"', '"--forwarded-allow-ips"'):
        assert token in args, f"CMD 에 {token} 가 없다"


def test_prod_has_no_dev_server_flags() -> None:
    prod = _code(_stage("prod"))
    assert "--reload" not in prod
    assert "--debug" not in prod


def test_prod_has_healthcheck_on_8080() -> None:
    prod = _stage("prod")
    assert "HEALTHCHECK" in prod and "/health" in prod and "8080" in prod


def test_data_directory_is_owned_by_the_app_user_and_db_path_points_there() -> None:
    """쓰기는 /data 와 /tmp 에서만 허용된다. 빈 볼륨을 /data 에 마운트하면 이 디렉터리의 소유권을 물려받는다."""
    text = _dockerfile()
    assert re.search(r"mkdir[^\n]*/data", text)
    assert re.search(r"chown[^\n]*/data", text)
    assert "DB_PATH=/data/voca.db" in text.replace("DB_PATH =", "DB_PATH=")


def test_prod_uses_the_migrating_entrypoint() -> None:
    prod = _stage("prod")
    assert re.search(r'^ENTRYPOINT\s+\["/app/docker-entrypoint\.sh"\]', prod, re.M)
    assert "docker-entrypoint.sh" in _dockerfile()


# ---------- entrypoint ----------


def test_entrypoint_migrates_then_execs_the_command() -> None:
    text = ENTRYPOINT.read_text(encoding="utf-8")
    assert text.startswith("#!/bin/sh"), "slim 이미지에 bash 가 없을 수 있다 (POSIX sh 로 쓴다)"
    assert "\r" not in text, "CRLF 금지"
    assert re.search(r"set -e", text)
    upgrade = text.index("alembic -c src/backend/alembic.ini upgrade head")
    run = text.index('exec "$@"')
    assert upgrade < run, "마이그레이션이 서버 시작보다 먼저여야 한다"


# ---------- docker-compose.yml: 앱 단일 서비스 ----------

COMPOSE = REPO_ROOT / "docker" / "docker-compose.yml"
COMPOSE_DEV = REPO_ROOT / "docker" / "docker-compose.dev.yml"


def _yaml(path: Path) -> dict:
    import yaml  # 개발 의존성(PyYAML)은 requirements-dev 에 포함된다

    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_compose_has_only_the_app_service() -> None:
    assert set(_yaml(COMPOSE)["services"]) == {"app"}, "DB 서버 컨테이너와 migrate 서비스는 SQLite 전환으로 사라졌다"


def test_compose_text_has_no_mysql_leftovers() -> None:
    for path in (COMPOSE, COMPOSE_DEV):
        assert not re.search(r"mysql", _code(path.read_text(encoding="utf-8")), re.I), path.name


def test_compose_persists_sqlite_in_a_named_volume_at_data() -> None:
    c = _yaml(COMPOSE)
    assert "voda-voca-data:/data" in c["services"]["app"]["volumes"]
    assert c["volumes"]["voda-voca-data"]["name"] == "voda-voca-data"


def test_compose_app_environment_is_explicit_and_has_no_root_secrets() -> None:
    svc = _yaml(COMPOSE)["services"]["app"]
    assert "env_file" not in svc, ".env 를 통째로 넘기지 않고 필요한 값만 명시한다"
    env = svc["environment"]
    assert env["DB_PATH"] == "/data/voca.db"
    assert "SECRET_KEY" in env
    assert not [k for k in env if "ROOT" in k or k.startswith("MYSQL")]


def test_compose_app_uses_prod_image_on_8080_without_source_mount() -> None:
    app = _yaml(COMPOSE)["services"]["app"]
    assert app["build"]["target"] == "prod"
    assert app["build"]["dockerfile"] == "Dockerfile"
    assert "${APP_PORT:-8080}:8080" in app["ports"]
    assert app["restart"] == "unless-stopped"
    assert [v for v in app["volumes"] if "src" in v] == [], "배포용 앱은 소스를 마운트하지 않는다 (개발용은 override 파일에서)"


def test_secret_key_fails_fast_when_env_is_missing() -> None:
    """새 PC 에서 .env 를 만들지 않으면 빈 비밀값으로 조용히 시작하는 대신, 안내 메시지와 함께 중단된다."""
    value = str(_yaml(COMPOSE)["services"]["app"]["environment"]["SECRET_KEY"])
    assert value.startswith("${SECRET_KEY:?") and ".env" in value


# ---------- docker-compose.dev.yml: 개발용 override ----------


def test_dev_override_builds_dev_target_and_mounts_source() -> None:
    svc = _yaml(COMPOSE_DEV)["services"]["app"]
    assert svc["build"]["target"] == "dev"
    assert svc["image"] == "voda-voca:dev", "prod 이미지 태그와 섞이지 않게 한다"
    assert "./src:/app/src" in svc["volumes"], "소스를 마운트해야 --reload 가 바로 반영된다"


def test_dev_override_never_mounts_env_file_or_whole_repo() -> None:
    """저장소 전체(.)나 .env 를 마운트하면 비밀이 컨테이너에 노출된다."""
    for mount in _yaml(COMPOSE_DEV)["services"]["app"]["volumes"]:
        source = mount.split(":")[0]
        assert source not in (".", "./", "./.env"), f"{mount} 는 마운트하면 안 된다"
        assert ".env" not in source.split("/")[-1] or source.endswith(".env.example")


def test_dev_override_mounts_what_the_tests_read_as_read_only() -> None:
    mounts = _yaml(COMPOSE_DEV)["services"]["app"]["volumes"]
    for needed in ["./pytest.ini:/app/pytest.ini:ro", "./.coveragerc:/app/.coveragerc:ro",
                   "./docker:/app/docker:ro", "./.dockerignore:/app/.dockerignore:ro",
                   "./Dockerfile:/app/Dockerfile:ro", "./docker-entrypoint.sh:/app/docker-entrypoint.sh:ro",
                   "./.gitattributes:/app/.gitattributes:ro", "./.gitignore:/app/.gitignore:ro"]:
        assert needed in mounts, f"{needed} 가 없다 (컨테이너 안 pytest 가 읽는다)"


def test_dev_override_disables_pytest_cache_in_readonly_workdir() -> None:
    """/app 은 root 소유라 app 사용자가 .pytest_cache 를 쓸 수 없다. 경고 대신 캐시를 끈다."""
    assert _yaml(COMPOSE_DEV)["services"]["app"]["environment"]["PYTEST_ADDOPTS"] == "-p no:cacheprovider"


# ---------- 과제 점검 워크플로 ----------

WORKFLOW = REPO_ROOT / ".github" / "workflows" / "docker-check.yml"


def test_course_check_workflow_is_present_and_untouched_in_its_key_rules() -> None:
    """제출 요건(VOCA-SUB-037): 점검 워크플로를 고치지 않고 넣는다. 사라지거나 핵심 규칙이 바뀌면 알린다.

    파일 전체 해시는 과목이 파일을 갱신하면 깨지므로, 앱 쪽에 영향을 주는 규칙만 고정한다.
    """
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "이 파일은 수정하지 마세요" in text
    assert "docker build -t voca-app ." in text, "리포 루트 Dockerfile 로 빌드한다"
    assert "--user 10001:10001" in text and "--cap-drop ALL" in text
    assert "--internal" in text, "인터넷이 막힌 네트워크에서 실행한다"
    assert "on: [push, workflow_dispatch]" in text
