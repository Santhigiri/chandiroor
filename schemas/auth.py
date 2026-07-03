"""
Request/response models for the authentication endpoints.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from utils.roles import Role


class Token(BaseModel):
    """The pair of tokens returned by login and refresh."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    """Body for ``POST /auth/refresh``."""

    refresh_token: str


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
