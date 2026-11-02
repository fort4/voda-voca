# 2026-11-02 - voda-voca - 인증 라우터: 가입, 로그인(세션 쿠키), 로그아웃, 내 정보 (REQ-001, REQ-002)
# 파일 위치: src/backend/routers/auth.py

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import get_settings
from backend.core.deps import SESSION_COOKIE_NAME, get_current_user
from backend.db.session import get_db_session
from backend.models import User
from backend.schemas.auth import LoginRequest, SignupRequest, UserOut
from backend.services import auth as auth_service
from backend.services.session import create_session, delete_session

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _cookie_options() -> dict[str, object]:
    """세션 쿠키 공통 속성. set 과 delete 가 같은 속성을 써야 브라우저가 쿠키를 지운다."""
    return {
        "path": "/",
        "httponly": True,  # 자바스크립트에서 읽을 수 없다 (XSS 로 인한 토큰 탈취 방지)
        "samesite": "lax",
        "secure": get_settings().cookie_secure,
    }


@router.post("/signup", status_code=status.HTTP_201_CREATED, response_model=UserOut)
async def signup(
    body: SignupRequest,
    db: AsyncSession = Depends(get_db_session),
) -> User:
    try:
        return await auth_service.signup(db, body.email, body.password, body.nickname)
    except auth_service.EmailAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이미 사용 중인 이메일입니다.",
        ) from exc


@router.post("/login", response_model=UserOut)
async def login(
    body: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
) -> User:
    try:
        user = await auth_service.authenticate(db, body.email, body.password)
    except auth_service.InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="이메일 또는 비밀번호가 올바르지 않습니다.",
        ) from exc

    token = await create_session(db, user.id)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=get_settings().session_ttl_days * 24 * 60 * 60,
        **_cookie_options(),
    )
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """세션을 삭제하고 쿠키를 만료시킨다. 쿠키가 없어도 204 를 반환한다 (멱등)."""
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token:
        await delete_session(db, token)
    response.delete_cookie(key=SESSION_COOKIE_NAME, **_cookie_options())


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)) -> User:
    return user
