# 2026-11-02 - voda-voca - 헬스체크 엔드포인트 스모크 테스트
# 파일 위치: src/backend/tests/test_health.py

from fastapi.testclient import TestClient

from backend.main import app


def test_health_returns_ok() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
