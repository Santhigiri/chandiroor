"""
Security primitives: password hashing and JWT creation/verification.

Pure functions with no HTTP or FastAPI coupling — the request-time wiring
(extracting the bearer token, resolving the principal, enforcing roles) lives in
``api.deps``. Passwords are hashed with bcrypt; tokens are signed with the
HS256 secret from ``core.config.settings``.

Two token *types* are issued, distinguished by the ``type`` claim:

* ``access``  — short-lived, carries ``sub`` (username) and ``role``; the only
  token accepted when authorizing a request.
* ``refresh`` — long-lived, carries ``sub`` only; accepted solely by the
  ``/auth/refresh`` endpoint to mint a new access token.

``decode_token`` verifies the signature and expiry *and* that the token's
``type`` matches what the caller expects, raising ``TokenError`` on any
mismatch so a refresh token can never be used as an access token (or vice
versa).
"""
from __future__ import annotations

import datetime
from typing import Any, Dict

import bcrypt
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from jose import JWTError, jwt

from core.config import settings

ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_TYPE = "refresh"


class TokenError(Exception):
    """Raised when a JWT is invalid, expired, or of the wrong type."""


class GoogleTokenError(Exception):
    """Raised when a Google ID token is invalid, expired, or unverifiable."""


# ── Password hashing ──────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    """Return a bcrypt hash of *password* (safe to store)."""
    # bcrypt only considers the first 72 bytes of the input; longer passwords are
    # truncated by the algorithm itself, which is the standard behaviour.
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    """Return True if *password* matches the stored bcrypt *hashed_password*."""
    try:
        return bcrypt.checkpw(
            password.encode("utf-8"), hashed_password.encode("utf-8")
        )
    except ValueError:
        # Malformed hash in the DB — treat as a non-match rather than crashing.
        return False


# ── Token creation ────────────────────────────────────────────────────────────

def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _encode(claims: Dict[str, Any]) -> str:
    return jwt.encode(
        claims, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )


def create_access_token(subject: str, role: str) -> str:
    """Mint a short-lived access token for *subject* carrying its *role*."""
    expire = _now() + datetime.timedelta(
        minutes=settings.access_token_expire_minutes
    )
    return _encode(
        {
            "sub": subject,
            "role": role,
            "type": ACCESS_TOKEN_TYPE,
            "exp": expire,
        }
    )


def create_refresh_token(subject: str) -> str:
    """Mint a long-lived refresh token for *subject*."""
    expire = _now() + datetime.timedelta(
        minutes=settings.refresh_token_expire_minutes
    )
    return _encode(
        {
            "sub": subject,
            "type": REFRESH_TOKEN_TYPE,
            "exp": expire,
        }
    )


# ── Token verification ────────────────────────────────────────────────────────

def decode_token(token: str, expected_type: str) -> Dict[str, Any]:
    """
    Decode and validate *token*, returning its claims.

    Verifies the signature and expiry, then enforces that the ``type`` claim
    equals *expected_type* and that a ``sub`` is present. Raises ``TokenError``
    on any failure.
    """
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError as exc:
        raise TokenError(str(exc)) from exc

    if claims.get("type") != expected_type:
        raise TokenError(
            f"expected {expected_type} token, got {claims.get('type')!r}"
        )
    if not claims.get("sub"):
        raise TokenError("token missing subject")

    return claims


# ── Google Sign-In ────────────────────────────────────────────────────────────

def verify_google_id_token(token: str) -> Dict[str, Any]:
    """
    Verify a Google-issued ID token and return its claims.

    Checks the signature (against Google's published keys), expiry, and that
    the token's audience matches ``settings.google_client_id``. Raises
    ``GoogleTokenError`` if the token is invalid/expired/wrong-audience, or if
    ``google_client_id`` is not configured.
    """
    if not settings.google_client_id:
        raise GoogleTokenError("GOOGLE_CLIENT_ID is not configured")
    try:
        return google_id_token.verify_oauth2_token( #type: ignore
            token, google_requests.Request(), audience=settings.google_client_id 
        ) 
    except ValueError as exc:
        raise GoogleTokenError(str(exc)) from exc
