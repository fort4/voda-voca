# 2026-11-02 - voda-voca - 설정 모듈 단위 테스트 (접속 URL 조립, 비밀번호 노출 방지)
# 파일 위치: src/backend/tests/test_config.py

from pydantic import SecretStr

from backend.core.config import Settings


def make_settings(password: str) -> Settings:
    return Settings(
        mysql_host="db.local",
        mysql_port=3307,
        mysql_user="voda_user",
        mysql_password=SecretStr(password),
        mysql_database="voda_voca",
    )


def test_database_url_uses_asyncmy_driver() -> None:
    url = make_settings("pw").database_url
    assert url.drivername == "mysql+asyncmy"
    assert url.host == "db.local"
    assert url.port == 3307
    assert url.database == "voda_voca"
    assert url.query == {"charset": "utf8mb4"}


def test_special_characters_in_password_are_escaped() -> None:
    # '@', ':', '/' 가 들어가도 호스트 부분이 깨지지 않아야 한다.
    url = make_settings("p@ss:w/rd").database_url
    assert url.password == "p@ss:w/rd"
    assert url.host == "db.local"
    rendered = url.render_as_string(hide_password=False)
    assert "p%40ss%3Aw%2Frd" in rendered


def test_masked_url_does_not_leak_password() -> None:
    url = make_settings("very-secret").database_url
    assert "very-secret" not in url.render_as_string(hide_password=True)
