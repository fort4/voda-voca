# 2026-11-24 - voda-voca - 앱 이미지 레시피: 공통 기반(base) → 개발용(dev) / 배포용(prod) 멀티스테이지 (2026-11-25 SQLite·과제 서버 규칙 반영)
# 파일 위치: Dockerfile
#
# 빌드(프로젝트 루트에서):
#   docker build -t voda-voca .                               # 마지막 스테이지(prod)가 기본 대상이다 (과제 서버가 이 한 줄로 빌드한다)
#   docker build --target dev -t voda-voca:dev .              # 개발용
#
# 원칙
#  - 비밀(.env, SECRET_KEY)은 이미지에 넣지 않는다. 컨테이너를 실행할 때 환경 변수로 주입한다.
#  - 실행 중 쓰기는 /data(SQLite 파일)와 /tmp 에서만 한다. 나머지 파일시스템은 읽기만 한다.
#  - 의존성 파일을 소스보다 먼저 복사해, 소스만 바뀌면 설치 단계는 빌드 캐시를 재사용한다.
#  - 실행할 때 인터넷이 필요 없다. 의존성은 빌드 때 모두 설치하고, 화면 자원(vendor/)은 소스에 들어 있다.

FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore \
    TZ=Asia/Seoul \
    PYTHONPATH=/app/src \
    DB_PATH=/data/voca.db

WORKDIR /app

# 의존성만 먼저 설치한다 (소스가 바뀌어도 이 레이어는 재사용된다)
COPY requirements.txt ./
RUN pip install -r requirements.txt


# ---------- 개발용: 테스트 도구 포함, 소스는 복사하지 않고 마운트해서 --reload 로 실행 ----------
# 1000 은 WSL 기본 사용자와 같아 마운트한 소스·볼륨의 파일 권한이 맞는다.
FROM base AS dev

RUN groupadd --gid 1000 app \
    && useradd --uid 1000 --gid app --create-home --shell /usr/sbin/nologin app \
    && mkdir -p /data \
    && chown app:app /data

COPY requirements-dev.txt ./
RUN pip install -r requirements-dev.txt

USER app
EXPOSE 8080
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8080", "--reload", "--reload-dir", "src"]


# ---------- 배포용(기본 빌드 대상): 런타임 의존성만, 소스를 이미지에 복사 ----------
# 과제 서버는 UID 10001, 리눅스 권한 없음(--cap-drop ALL), 쓰기는 /data 와 /tmp 만 허용한다.
FROM base AS prod

RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app \
    && mkdir -p /data \
    && chown app:app /data

COPY src ./src
COPY docker-entrypoint.sh ./docker-entrypoint.sh
# COPY --chmod 는 BuildKit 전용이라 쓰지 않는다 (# syntax 지시어 금지 규칙과 같은 이유로 기본 빌더만 가정한다)
RUN chmod 0755 /app/docker-entrypoint.sh

USER app
EXPOSE 8080

# DB 연결까지 확인하는 /health 로 상태를 본다 (실패하면 unhealthy 로 표시)
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD ["python", "-c", "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=4).status == 200 else 1)"]

# 시작할 때 마이그레이션을 먼저 적용한 뒤 서버를 띄운다 (빈 DB 에서 시작해도 된다)
ENTRYPOINT ["/app/docker-entrypoint.sh"]
# 앞단 프록시(nginx) 뒤에서 동작하므로 X-Forwarded-* 를 신뢰한다. 개발 서버 옵션(--reload)은 쓰지 않는다.
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers", "--forwarded-allow-ips", "*"]
