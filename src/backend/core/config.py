# 2026-11-02 - voda-voca - .env 기반 설정 로드 및 비동기 SQLite 접속 URL 생성 (2026-11-25 MySQL → SQLite 전환, ADR-010)
# 파일 위치: src/backend/core/config.py

from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

# 프로젝트 루트의 .env (src/backend/core/config.py 기준 네 단계 상위)
ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    """애플리케이션 설정. 값은 .env 또는 OS 환경 변수에서 주입한다 (REQ-112).

    DB 는 SQLite 파일 하나다 (과제 서버 규칙: 쓰기는 /data 와 /tmp 에만 허용). 경로는 DB_PATH 로 주입한다.
    대소문자는 구분하지 않는다.
    """

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",  # TZ 등 이 모듈이 쓰지 않는 값은 무시
    )

    db_path: str = "/data/voca.db"
    # 서버 배포 규칙(VOCA-NFR-004)상 비밀값은 환경 변수로 받는다. 세션은 DB 토큰 방식이라 아직 쓰지 않지만 주입은 허용한다.
    secret_key: SecretStr | None = None

    # --- 인증 (REQ-001, REQ-002) ---
    # 세션 수명(일). 로그인 시점부터 절대 만료 (기본 14일, ADR-001).
    session_ttl_days: int = 14
    # 세션 쿠키 Secure 속성. 로컬 HTTP 개발을 위해 기본 false. HTTPS 배포 시 COOKIE_SECURE=true.
    cookie_secure: bool = False
    # bcrypt cost factor (ADR-002). 테스트에서는 낮춰서 실행 시간을 줄인다.
    bcrypt_rounds: int = 12

    @property
    def database_url(self) -> URL:
        """비동기 드라이버(aiosqlite) 접속 URL. 경로 문자열을 직접 이어 붙이지 않고 URL.create 로 만든다."""
        return URL.create(drivername="sqlite+aiosqlite", database=self.db_path)


@lru_cache
def get_settings() -> Settings:
    """설정 객체를 프로세스당 한 번만 로드한다."""
    return Settings()
