"""
Request/response models for the authentication endpoints.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.utils.nakshatra import Nakshatra
from app.utils.roles import Role


def _validate_nakshatra_name(value: Optional[str]) -> Optional[str]:
    if value is not None and value not in Nakshatra.__members__:
        raise ValueError(
            f"Unknown nakshatra {value!r}; must be one of {sorted(Nakshatra.__members__)}"
        )
    return value


class Token(BaseModel):
    """
    An access + refresh token pair. Used internally to carry freshly minted
    tokens to the cookie-setting layer — the tokens are delivered to clients as
    HTTP-only cookies, never serialized in a response body.
    """

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class CreateUserRequest(BaseModel):
    """Body for the admin-only ``POST /auth/users`` endpoint."""

    username: str = Field(min_length=1)
    password: str = Field(min_length=8)
    role: Role = Role.USER


class GetUserResponse(BaseModel):
    """Public view of a user — never includes the password hash."""

    username: str
    role: Role
    is_active: bool
    email: Optional[str] = None
    full_name: Optional[str] = None
    date_of_birth: Optional[date] = None
    birth_nakshatra: Optional[str] = None


class LoginUserRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=8)


class GoogleLoginRequest(BaseModel):
    """Body for ``POST /auth/google`` — a Google Identity Services ID token."""

    id_token: str


class UpdateUserRequest(BaseModel):
    """
    Body for ``PATCH /auth/me`` — self-service profile fields.

    All fields are optional; only the ones supplied are updated (partial
    update semantics), leaving the rest of the profile untouched.
    """

    full_name: Optional[str] = None
    date_of_birth: Optional[date] = None
    birth_nakshatra: Optional[str] = None

    _validate_birth_nakshatra = field_validator("birth_nakshatra")(
        _validate_nakshatra_name
    )
