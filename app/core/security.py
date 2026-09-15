"""
Verification of TVM-issued JWT access tokens.

Chandiroor is a pure resource server: it never mints tokens or stores
credentials. Every request's identity comes from an access token minted by
TVM (the Ashram's auth microservice), signed with TVM's private key (RS256).
Verification prefers TVM's published JWKS (``core.config.settings.tvm_jwks_url``,
via ``core.jwks_client``), resolving the signing key by the token's ``kid``.
If the JWKS endpoint is unset or unreachable, verification falls back to the
static ``core.config.settings.tvm_jwt_public_key`` (a PEM-encoded RSA public
key) when configured — useful before TVM exposes a JWKS endpoint, or during a
TVM outage — at the cost of not picking up a TVM key rotation automatically.
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
    Verify *token* against TVM's published key (JWKS, or the static fallback
    key) and return its claims.

    Raises ``TokenError`` on any failure: an unresolvable/unknown signing
    key, a bad signature, an expired token, a wrong issuer/audience, or
    missing/unrecognized claims.
    """
    try:
        header = jwt.get_unverified_header(token)
    except JWTError as exc:
        raise TokenError(str(exc)) from exc

    kid = header.get("kid")

    signing_key: Any
    if kid:
        try:
            signing_key = get_signing_key(kid)
        except JwksFetchError:
            if not settings.tvm_jwt_public_key:
                raise TokenError(
                    f"could not resolve signing key {kid!r} and no "
                    "TVM_JWT_PUBLIC_KEY fallback is configured"
                ) from None
            signing_key = settings.tvm_jwt_public_key
    elif settings.tvm_jwt_public_key:
        # No 'kid' header — nothing to look up in the JWKS, so the static
        # fallback key is the only option.
        signing_key = settings.tvm_jwt_public_key
    else:
        raise TokenError("token is missing a 'kid' header")

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
