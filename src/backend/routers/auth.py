# 2026-11-02 - voda-voca - 인증 라우터: 가입, 로그인(세션 쿠키, 무차별 대입 방어 REQ-121), 로그아웃, 내 정보, 회원 탈퇴 (REQ-001, REQ-002)
# 파일 위치: src/backend/routers/auth.py

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import get_settings
from backend.core.deps import SESSION_COOKIE_NAME, get_current_user
from backend.core.rate_limit import login_rate_limiter
from backend.db.session import get_db_session
from backend.models import User
from backend.schemas.auth import LoginRequest, SignupRequest, UserOut
from backend.services import auth as auth_service
from backend.services.session import create_session, delete_session

router = APIRouter(prefix="/api/auth", tags=["auth"])

LOGIN_RATE_LIMITED_DETAIL = "로그인 시도가 너무 많습니다. 잠시 후 다시 시도해 주세요."


def _login_keys(request: Request, nickname: str) -> tuple[str, str]:
    """로그인 집계 키: (IP 키, 계정 키). 계정 키는 닉네임 기준이다 (회원 체계 단순화 후).

    X-Forwarded-For 는 신뢰하지 않는다. 역방향 프록시 뒤에서는 프록시 IP로 집계된다.
    """
    client_ip = request.client.host if request.client else "unknown"
    return f"ip:{client_ip}", f"acct:{nickname.strip().lower()}"


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
        return await auth_service.signup(db, body.password, body.nickname)
    except auth_service.NicknameAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이미 사용 중인 닉네임입니다.",
        ) from exc


@router.post("/login", response_model=UserOut)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
) -> User:
    """로그인. 1분 내 5회 실패한 IP 또는 계정은 비밀번호와 무관하게 429 로 거부한다 (REQ-121).

    차단 판정은 DB 조회 전에 한다. 차단된 요청은 실패로 집계하지 않는다.
    """
    ip_key, account_key = _login_keys(request, body.nickname)
    retry_after = login_rate_limiter.retry_after([ip_key, account_key])
    if retry_after is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=LOGIN_RATE_LIMITED_DETAIL,
            headers={"Retry-After": str(retry_after)},
        )

    try:
        user = await auth_service.authenticate(db, body.nickname, body.password)
    except auth_service.InvalidCredentialsError as exc:
        login_rate_limiter.record_failure([ip_key, account_key])
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="닉네임 또는 비밀번호가 올바르지 않습니다.",
        ) from exc

    login_rate_limiter.reset(account_key)  # 성공하면 이 계정의 실패 기록을 지운다

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


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """회원 탈퇴. 계정과 연관 데이터(단어장, 단어, 북마크, 학습 이력, 세션)를 모두 지우고 쿠키를 만료시킨다.

    인증되지 않은 요청은 get_current_user 가 401 로 막는다. 탈퇴 후 같은 쿠키로는 접근할 수 없다.
    """
    await auth_service.delete_account(db, user.id)
    response.delete_cookie(key=SESSION_COOKIE_NAME, **_cookie_options())
