# 2026-11-24 - voda-voca - 앱 이미지 레시피: 공통 기반(base) → 개발용(dev) / 배포용(prod) 멀티스테이지
# 파일 위치: docker/Dockerfile
#
# 빌드(프로젝트 루트에서):
#   docker build -f docker/Dockerfile --target prod -t voda-voca:prod .
#   docker build -f docker/Dockerfile --target dev  -t voda-voca:dev  .
#
# 원칙
#  - .env(비밀번호)는 이미지에 넣지 않는다. DB 접속 정보는 컨테이너를 실행할 때 환경 변수로 주입한다.
#  - 의존성 파일을 소스보다 먼저 복사해, 소스만 바뀌면 설치 단계는 빌드 캐시를 재사용한다.
#  - 비root(app, uid 1000)로 실행한다. 1000 은 WSL 기본 사용자와 같아 dev 에서 마운트한 파일 권한이 맞는다.

FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore \
    TZ=Asia/Seoul \
    PYTHONPATH=/app/src

WORKDIR /app

RUN groupadd --gid 1000 app \
    && useradd --uid 1000 --gid app --create-home --shell /usr/sbin/nologin app

# 의존성만 먼저 설치한다 (소스가 바뀌어도 이 레이어는 재사용된다)
COPY requirements.txt ./
RUN pip install -r requirements.txt


# ---------- 개발용: 테스트 도구 포함, 소스는 복사하지 않고 마운트해서 --reload 로 실행 ----------
FROM base AS dev

COPY requirements-dev.txt ./
RUN pip install -r requirements-dev.txt

USER app
EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--reload-dir", "src"]


# ---------- 배포용: 런타임 의존성만, 소스를 이미지에 복사 ----------
FROM base AS prod

COPY src ./src

USER app
EXPOSE 8000

# DB 연결까지 확인하는 /health 로 상태를 본다 (실패하면 compose 가 unhealthy 로 표시)
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status == 200 else 1)"]

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
