# 2026-11-05 - voda-voca - 서비스 계층 공용 예외: 표준 단어를 찾지 못했을 때
# 파일 위치: src/backend/services/errors.py


class WordNotFoundError(Exception):
    """단어가 없다. 라우터는 404 로 바꾼다."""


class VocabularyNotFoundError(Exception):
    """표준 단어장이 없다. 라우터는 404 로 바꾼다."""
