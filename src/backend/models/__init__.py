# 2026-11-02 - voda-voca - ORM 모델 패키지. 모든 모델을 import 해 Base.metadata 에 등록한다.
# 파일 위치: src/backend/models/__init__.py

# 이 import 들이 실행되어야 Base.metadata 에 모든 테이블이 등록되고 Alembic autogenerate 가 본다.
from backend.models.base import Base
from backend.models.bookmark import Bookmark
from backend.models.session import AuthSession
from backend.models.study_log import StudyLog
from backend.models.user import User
from backend.models.word import Word
from backend.models.wordbook import Wordbook

__all__ = [
    "AuthSession",
    "Base",
    "Bookmark",
    "StudyLog",
    "User",
    "Word",
    "Wordbook",
]
