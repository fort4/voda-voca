# 2026-11-26 - voda-voca - 관리자 계정의 고정 ID 와 초기 비밀번호, 관리자 닉네임 판정 (REQ-159)
# 파일 위치: src/backend/core/admin.py

# 관리자는 이 닉네임을 쓰는 계정 하나다. 일반 가입에서는 예약어다.
ADMIN_NICKNAME = "admin"

# 계정을 처음 만들 때만 쓰는 값이다. 관리자가 마이페이지에서 바꾸면 다시 덮어쓰지 않는다.
# 비밀값을 코드에 두지 않는다는 규칙(CLAUDE.md §5.3)의 예외다 (2026-11-26 사용자 결정, 채점 환경에서 바로 로그인하기 위함).
# 공개 저장소에서 보이는 값이므로, 배포한 서버에서는 바로 바꿔야 한다.
ADMIN_INITIAL_PASSWORD = "admin1234"


def is_admin_nickname(nickname: str) -> bool:
    """앞뒤 공백과 영문 대소문자를 무시하고 관리자 닉네임인지 본다 (DB 의 NOCASE 와 같은 기준)."""
    return nickname.strip().lower() == ADMIN_NICKNAME
