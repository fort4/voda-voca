# 2026-11-02 - voda-voca - FastAPI 애플리케이션 진입점 (현재: 헬스체크만 제공)
# 파일 위치: src/backend/main.py

from fastapi import FastAPI

app = FastAPI(title="voda-voca")


@app.get("/health")
async def health() -> dict[str, str]:
    """프로세스 기동 여부를 확인하는 헬스체크 엔드포인트."""
    return {"status": "ok"}
