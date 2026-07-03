"""
Authentication endpoints: login, token refresh, current user, and admin-only
user creation.

The HTTP boundary only — credential checking, hashing, and token minting are
delegated to ``core.security`` and ``db.user_repository``.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session

from api.deps import Principal, require_role
from core.security import (
    REFRESH_TOKEN_TYPE,
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from db.database import get_session
from db.user_repository import UserRepository
from schemas.auth import RefreshRequest, Token, UserCreate, UserRead
from utils.roles import Role

router = APIRouter(prefix="/auth")


def _issue_tokens(username: str, role: str) -> Token:
    return Token(
        access_token=create_access_token(subject=username, role=role),
        refresh_token=create_refresh_token(subject=username),
    )


@router.post("/login", response_model=Token)
def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: Annotated[Session, Depends(get_session)],
) -> Token:
    """Verify username/password and issue an access + refresh token pair."""
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
    return _issue_tokens(user.username, user.role)


@router.post("/refresh", response_model=Token)
def refresh(
    body: RefreshRequest,
    session: Annotated[Session, Depends(get_session)],
) -> Token:
    """
    Exchange a valid refresh token for a new access + refresh token pair
    (refresh-token rotation). The user is re-checked for existence and active
    status on every refresh.
    """
    try:
        claims = decode_token(body.refresh_token, REFRESH_TOKEN_TYPE)
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
    return _issue_tokens(user.username, user.role)


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
    return UserRead(username=user.username, role=Role(user.role), is_active=user.is_active)


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
    return UserRead(username=user.username, role=Role(user.role), is_active=user.is_active)
