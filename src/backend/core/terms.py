# 2026-11-26 - voda-voca - 표제어 중복 판정 키: 시드 로더와 관리자 단어 등록이 같은 기준을 쓴다 (REQ-143, REQ-161)
# 파일 위치: src/backend/core/terms.py

import unicodedata


def term_key(term: str) -> str:
    """대소문자와 악센트를 무시한 비교 키다 (DB 의 NOCASE 는 악센트를 접지 못해 앱이 정규화한다)."""
    decomposed = unicodedata.normalize("NFKD", term.casefold())
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
