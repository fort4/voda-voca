# 2026-11-05 - voda-voca - 레거시 퀴즈·플래시카드 API 제거 회귀 테스트 (D단계): 옛 경로는 없고 새 경로는 남아 있는지 확인
# 파일 위치: src/backend/tests/test_legacy_study_removed.py

import pytest

from backend.main import app
from backend.services import study as study_service

REMOVED = [
    ("GET", "/api/study/flashcards"),
    ("POST", "/api/study/quiz/sessions"),
    ("POST", "/api/study/quiz/sessions/{session_id}/answers"),
    ("POST", "/api/study/quiz/sessions/{session_id}/submit"),
    ("GET", "/api/study/quiz/sessions/{session_id}"),
]
KEPT = [
    ("POST", "/api/study/sessions"),
    ("POST", "/api/study/sessions/{session_id}/answer"),
    ("GET", "/api/study/stats"),
    ("GET", "/api/study/wrong-words"),
    ("GET", "/api/study/logs"),
]
REMOVED_SERVICE_NAMES = [
    "list_flashcards",
    "create_quiz",
    "record_answer",
    "submit_quiz",
    "get_quiz_session",
    "FlashcardOffsetWithShuffleError",
]


def _routes() -> set[tuple[str, str]]:
    """OpenAPI 스키마에서 (METHOD, 경로) 집합을 얻는다. include_router 방식이 바뀌어도 깨지지 않는다."""
    return {(method.upper(), path) for path, item in app.openapi()["paths"].items() for method in item}


@pytest.mark.parametrize(("method", "path"), REMOVED)
def test_legacy_routes_are_gone(method: str, path: str) -> None:
    assert (method, path) not in _routes()


@pytest.mark.parametrize(("method", "path"), KEPT)
def test_session_runner_and_stats_routes_remain(method: str, path: str) -> None:
    assert (method, path) in _routes()


@pytest.mark.parametrize("name", REMOVED_SERVICE_NAMES)
def test_legacy_service_functions_are_gone(name: str) -> None:
    assert not hasattr(study_service, name)
