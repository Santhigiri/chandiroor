"""
Request/response models for the authentication endpoints.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from utils.roles import Role


class Token(BaseModel):
    """
    An access + refresh token pair. Used internally to carry freshly minted
    tokens to the cookie-setting layer — the tokens are delivered to clients as
    HTTP-only cookies, never serialized in a response body.
    """

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserCreate(BaseModel):
    """Body for the admin-only ``POST /auth/users`` endpoint."""

    username: str = Field(min_length=1)
    password: str = Field(min_length=8)
    role: Role = Role.USER


class UserRead(BaseModel):
    """Public view of a user — never includes the password hash."""

    username: str
    role: Role
    is_active: bool
