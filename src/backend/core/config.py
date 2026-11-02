# 2026-11-02 - voda-voca - .env 기반 DB 접속 설정 로드 및 비동기 접속 URL 생성
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

    변수명은 기존 .env / .env.example / docker-compose 와 맞춰 MYSQL_* 를 사용한다.
    대소문자는 구분하지 않는다.
    """

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",  # TZ, MYSQL_ROOT_PASSWORD 등 이 모듈이 쓰지 않는 값은 무시
    )

    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3306
    mysql_user: str
    mysql_password: SecretStr
    mysql_database: str

    # --- 인증 (REQ-001, REQ-002) ---
    # 세션 수명(일). 로그인 시점부터 절대 만료 (기본 14일, ADR-001).
    session_ttl_days: int = 14
    # 세션 쿠키 Secure 속성. 로컬 HTTP 개발을 위해 기본 false. HTTPS 배포 시 COOKIE_SECURE=true.
    cookie_secure: bool = False
    # bcrypt cost factor (ADR-002). 테스트에서는 낮춰서 실행 시간을 줄인다.
    bcrypt_rounds: int = 12

    @property
    def database_url(self) -> URL:
        """비동기 드라이버(asyncmy) 접속 URL.

        문자열을 직접 조립하지 않고 URL.create 로 만든다.
        그래야 비밀번호에 '@', ':', '/' 같은 특수문자가 있어도 안전하게 인코딩된다.
        """
        return URL.create(
            drivername="mysql+asyncmy",
            username=self.mysql_user,
            password=self.mysql_password.get_secret_value(),
            host=self.mysql_host,
            port=self.mysql_port,
            database=self.mysql_database,
            query={"charset": "utf8mb4"},
        )


@lru_cache
def get_settings() -> Settings:
    """설정 객체를 프로세스당 한 번만 로드한다."""
    return Settings()
