"""
Verification of TVM-issued JWT access tokens.

Chandiroor is a pure resource server: it never mints tokens or stores
credentials. Every request's identity comes from an access token minted by
TVM (the Ashram's auth microservice), signed with TVM's private key (RS256)
and verified here against TVM's published JWKS
(``core.config.settings.tvm_jwks_url``, via ``core.jwks_client``).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from jose import JWTError, jwt

from app.core.config import settings
from app.core.jwks_client import JwksFetchError, get_signing_key
from app.utils.roles import Role


class TokenError(Exception):
    """Raised when a JWT is invalid, expired, or cannot be verified."""


@dataclass(frozen=True)
class TvmClaims:
    """The subset of TVM's access-token claims Chandiroor trusts."""

    user_id: int
    role: Role
    is_verified: bool


def verify_access_token(token: str) -> TvmClaims:
    """
    Verify *token* against TVM's JWKS and return its claims.

    Raises ``TokenError`` on any failure: an unresolvable/unknown signing
    key, a bad signature, an expired token, a wrong issuer/audience, or
    missing/unrecognized claims.
    """
    try:
        header = jwt.get_unverified_header(token)
    except JWTError as exc:
        raise TokenError(str(exc)) from exc

    kid = header.get("kid")
    if not kid:
        raise TokenError("token is missing a 'kid' header")

    try:
        signing_key = get_signing_key(kid)
    except JwksFetchError as exc:
        raise TokenError(str(exc)) from exc

    try:
        claims: Dict[str, Any] = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            audience=settings.tvm_jwt_audience,
            issuer=settings.tvm_jwt_issuer,
        )
    except JWTError as exc:
        raise TokenError(str(exc)) from exc

    user_id = claims.get("userId")
    role_name = claims.get("role")
    if user_id is None or role_name is None:
        raise TokenError("token is missing required claims")

    try:
        role = Role[role_name]
    except KeyError:
        raise TokenError(f"unrecognized role claim: {role_name!r}") from None

    return TvmClaims(
        user_id=int(user_id),
        role=role,
        is_verified=bool(claims.get("isVerified", False)),
    )
