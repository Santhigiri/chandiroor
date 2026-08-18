"""
Authentication endpoints: login, token refresh, current user, and admin-only
user creation.

The HTTP boundary only — credential checking, hashing, and token minting are
delegated to ``core.security`` and ``db.user_repository``.
"""
from typing import Annotated, Optional

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session

from core.deps import ACCESS_TOKEN_COOKIE, Principal, require_role
from core.config import settings
from core.security import (
    REFRESH_TOKEN_TYPE,
    GoogleTokenError,
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_google_id_token,
    verify_password,
)
from db.database import get_session
from db.user_repository import UserRepository
from features.auth.schemas import GoogleLoginRequest, ProfileUpdate, Token, UserCreate, UserRead
from utils.roles import Role

router = APIRouter(prefix="/auth")

REFRESH_TOKEN_COOKIE = "refresh_token"


def _to_user_read(user) -> UserRead:
    return UserRead(
        username=user.username,
        role=Role(user.role),
        is_active=user.is_active,
        email=user.email,
        full_name=user.full_name,
        date_of_birth=user.date_of_birth,
        birth_nakshatra=user.birth_nakshatra,
    )


def _issue_tokens(username: str, role: str) -> Token:
    return Token(
        access_token=create_access_token(subject=username, role=role),
        refresh_token=create_refresh_token(subject=username),
    )


def _set_auth_cookies(response: Response, tokens: Token) -> None:
    """Deliver the token pair as HTTP-only cookies (never in the body)."""
    common = {
        "httponly": True,
        "secure": settings.cookie_secure,
        "samesite": settings.cookie_samesite,
        "domain": settings.cookie_domain,
        "path": "/",
    }
    response.set_cookie(
        ACCESS_TOKEN_COOKIE,
        tokens.access_token,
        max_age=settings.access_token_expire_minutes * 60,
        **common,
    )
    response.set_cookie(
        REFRESH_TOKEN_COOKIE,
        tokens.refresh_token,
        max_age=settings.refresh_token_expire_minutes * 60,
        **common,
    )


def _clear_auth_cookies(response: Response) -> None:
    """Expire both auth cookies (same attributes used to set them)."""
    common = {
        "httponly": True,
        "secure": settings.cookie_secure,
        "samesite": settings.cookie_samesite,
        "domain": settings.cookie_domain,
        "path": "/",
    }
    response.delete_cookie(ACCESS_TOKEN_COOKIE, **common)
    response.delete_cookie(REFRESH_TOKEN_COOKIE, **common)


@router.post("/login", response_model=UserRead)
def login(
    response: Response,
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: Annotated[Session, Depends(get_session)],
) -> UserRead:
    """
    Verify username/password, set the access + refresh tokens as HTTP-only
    cookies, and return the (non-sensitive) current user so the client can show
    who is logged in without ever handling the tokens.
    """
    user = UserRepository(session).get_by_username(form.username)
    if (
        user is None
        or not user.is_active
        or not verify_password(form.password, user.hashed_password)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    _set_auth_cookies(response, _issue_tokens(user.username, user.role))
    return _to_user_read(user)


@router.post("/refresh", status_code=status.HTTP_204_NO_CONTENT)
def refresh(
    response: Response,
    session: Annotated[Session, Depends(get_session)],
    refresh_token: Annotated[Optional[str], Cookie()] = None,
) -> None:
    """
    Exchange a valid refresh-token cookie for a fresh access + refresh token
    pair (refresh-token rotation), re-setting both cookies. The user is
    re-checked for existence and active status on every refresh.
    """
    if refresh_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        claims = decode_token(refresh_token, REFRESH_TOKEN_TYPE)
    except TokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = UserRepository(session).get_by_username(claims["sub"])
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User no longer valid",
            headers={"WWW-Authenticate": "Bearer"},
        )
    _set_auth_cookies(response, _issue_tokens(user.username, user.role))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> None:
    """Clear the auth cookies. Safe to call even without a valid session."""
    _clear_auth_cookies(response)


@router.post("/google", response_model=UserRead)
def google_login(
    response: Response,
    payload: GoogleLoginRequest,
    session: Annotated[Session, Depends(get_session)],
) -> UserRead:
    """
    Verify a Google Identity Services ID token, create a ``user``-role account
    on first sign-in (matched by the Google account's stable ``sub``), set the
    access + refresh tokens as HTTP-only cookies, and return the current user —
    same contract as ``/login``.
    """
    try:
        claims = verify_google_id_token(payload.id_token)
    except GoogleTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired Google ID token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not claims.get("email_verified"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google account email is not verified",
        )

    repo = UserRepository(session)
    user = repo.get_by_google_id(claims["sub"])
    if user is None:
        user = repo.create_google_user(
            google_id=claims["sub"],
            email=claims["email"],
            full_name=claims.get("name"),
        )
    elif not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User no longer valid",
            headers={"WWW-Authenticate": "Bearer"},
        )

    _set_auth_cookies(response, _issue_tokens(user.username, user.role))
    return _to_user_read(user)


@router.get("/me", response_model=UserRead)
def me(
    principal: Annotated[Principal, Depends(require_role(Role.USER))],
    session: Annotated[Session, Depends(get_session)],
) -> UserRead:
    """Return the currently authenticated user (requires user or admin)."""
    user = UserRepository(session).get_by_username(principal.username)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    return _to_user_read(user)


@router.patch("/me", response_model=UserRead)
def update_profile(
    payload: ProfileUpdate,
    principal: Annotated[Principal, Depends(require_role(Role.USER))],
    session: Annotated[Session, Depends(get_session)],
) -> UserRead:
    """Update the caller's own profile fields (requires user or admin)."""
    user = UserRepository(session).update_profile(
        username=principal.username,
        full_name=payload.full_name,
        date_of_birth=payload.date_of_birth,
        birth_nakshatra=payload.birth_nakshatra,
    )
    return _to_user_read(user)


@router.post(
    "/users",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
)
def create_user(
    payload: UserCreate,
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[Principal, Depends(require_role(Role.ADMIN))],
) -> UserRead:
    """Create a new user with a chosen role. Admin only."""
    repo = UserRepository(session)
    if repo.exists(payload.username):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with that username already exists",
        )
    user = repo.create(
        username=payload.username,
        hashed_password=hash_password(payload.password),
        role=payload.role,
    )
    return _to_user_read(user)
