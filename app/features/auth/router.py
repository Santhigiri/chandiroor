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

from app.api.deps import ACCESS_TOKEN_COOKIE, Principal, get_auth_service, require_role
from app.core.config import settings
from app.core.security import (
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
from app.db.database import get_session
from app.features.auth.ports import UserUpdate
from app.features.auth.service import AuthService, InvalidTokenException
from app.utils.nakshatra import Nakshatra
from .auth_repository import AuthRepository, UserNotFoundException
from .schemas import GoogleLoginRequest, LoginUserRequest, UpdateUserRequest, Token, CreateUserRequest, GetUserResponse
from app.utils.roles import Role

router = APIRouter(prefix="/auth", tags=["Authentication"])

REFRESH_TOKEN_COOKIE = "refresh_token"


def _to_user_read(user) -> GetUserResponse:
    return GetUserResponse(
        username=user.username,
        role=Role[user.role] if user.role else Role.ANONYMOUS ,
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


@router.post("/login", response_model=GetUserResponse)
def login(
    response: Response,
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    auth_service: AuthService =  Depends(get_auth_service)
) -> GetUserResponse:
    """
    Verify username/password, set the access + refresh tokens as HTTP-only
    cookies, and return the (non-sensitive) current user so the client can show
    who is logged in without ever handling the tokens.
    """


    try:
        credentials = LoginUserRequest(username=form.username, password = form.password)
        user = auth_service.login_user(credentials)
        _set_auth_cookies(response, _issue_tokens(user.username, user.role))
        return _to_user_read(user)
    except UserNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
            


@router.post("/refresh", status_code=status.HTTP_204_NO_CONTENT)
def refresh(
    response: Response,
    refresh_token: Annotated[Optional[str], Cookie()] = None,
    service: AuthService = Depends(get_auth_service)
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
        user = service.refresh_session(refresh_token)
    except InvalidTokenException:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    _set_auth_cookies(response, _issue_tokens(user.username, user.role))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> None:
    """Clear the auth cookies. Safe to call even without a valid session."""
    _clear_auth_cookies(response)



@router.get("/me", response_model=GetUserResponse)
def me(
    principal: Annotated[Principal, Depends(require_role(Role.USER))],
    service: AuthService = Depends(get_auth_service)
) -> GetUserResponse:
    """Return the currently authenticated user (requires user or admin)."""
    if principal.username is None: 
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Username is None"
        )
    user = service.get_user(principal.username)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    return _to_user_read(user)


@router.patch("/me", response_model=GetUserResponse)
def update_profile(
    payload: UpdateUserRequest,
    principal: Annotated[Principal, Depends(require_role(Role.USER))],
) -> GetUserResponse:
    """Update the caller's own profile fields (requires user or admin)."""
    if principal.username is None: 
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Username is None"
        )
    first_name = payload.full_name.split(" ")[0] if payload.full_name else principal.username
    last_name = payload.full_name.split(" ")[-1] if payload.full_name else ""
    user_profile = UserUpdate(
        username= principal.username,
        full_name=payload.full_name,
        date_of_birth=payload.date_of_birth,
        birth_nakshatra=Nakshatra[payload.birth_nakshatra] if payload.birth_nakshatra else None,
    )
    return _to_user_read(user_profile)


@router.post(
    "/users",
    response_model=GetUserResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_user(
    payload: CreateUserRequest,
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[Principal, Depends(require_role(Role.ADMIN))],
) -> GetUserResponse:
    """Create a new user with a chosen role. Admin only."""
    repo = AuthRepository(session)
    if repo.exists(payload.username):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with that username already exists",
        )
    
    user = repo.create_user(payload)
    return _to_user_read(user)
