"""
Shared FastAPI dependencies for the API layer.

Two concerns live here:

* **Service wiring** — ``get_service`` builds a ``PanchangamService`` from a
  request-scoped DB session, replacing the ``_get_service`` helper that was
  previously duplicated in each route module.

* **Authentication / authorization** — ``get_current_principal`` resolves the
  bearer token (if any) into a ``Principal``; ``require_role`` is a dependency
  factory that gates an endpoint at a minimum ``Role``. Every request resolves
  to one of the three principals: an ``admin``/``user`` backed by a valid access
  token, or the ``anonymous`` principal when no token is presented. A malformed,
  expired, or wrong-type token is rejected outright (401) rather than being
  downgraded to anonymous.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Callable, Optional

from fastapi import Cookie, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session

from core.security import ACCESS_TOKEN_TYPE, TokenError, decode_token
from db.database import get_session
from db.repository import PanchangamRepository
from db.user_repository import UserRepository
from services.panchangam_service import PanchangamService
from utils.location import DEFAULT_LOCATION_CODE, Location
from utils.roles import Role


# ── Service wiring ────────────────────────────────────────────────────────────

def get_service(
    session: Annotated[Session, Depends(get_session)],
) -> PanchangamService:
    return PanchangamService(PanchangamRepository(session))


# ── Location selection ────────────────────────────────────────────────────────

def get_location(
    location: Annotated[str, Query(description="Location code, e.g. 'tvm'")] = DEFAULT_LOCATION_CODE,
) -> Location:
    """Resolve the ``?location=`` query param (a location code) to a ``Location``.

    Defaults to the ashram (``tvm``). An unknown code is a 404 — the caller asked
    for a location the API does not serve.
    """
    try:
        return Location.from_code(location)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown location code: {location!r}",
        )


# ── Principal ─────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Principal:
    """The authenticated (or anonymous) identity behind a request."""

    role: Role
    username: Optional[str] = None

    @property
    def is_authenticated(self) -> bool:
        return self.role is not Role.ANONYMOUS


ANONYMOUS = Principal(role=Role.ANONYMOUS)

# Name of the HTTP-only cookie carrying the access token (must match the name
# the auth routes set it under).
ACCESS_TOKEN_COOKIE = "access_token"

# auto_error=False so requests without an Authorization header are allowed
# through as the anonymous principal instead of being rejected here.
_bearer = HTTPBearer(auto_error=False)


def get_current_principal(
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(_bearer)],
    session: Annotated[Session, Depends(get_session)],
    access_token: Annotated[Optional[str], Cookie()] = None,
) -> Principal:
    """
    Resolve the request's identity from its access token.

    The token is taken from the HTTP-only ``access_token`` cookie (how browsers
    authenticate), falling back to an ``Authorization: Bearer`` header when
    present (for non-browser/programmatic clients). Resolution:

    * No cookie and no header → the anonymous principal.
    * A valid access token for an existing, active user → that user's principal.
    * A malformed/expired/wrong-type token, or one naming an unknown or
      deactivated user → 401.
    """
    token = access_token or (credentials.credentials if credentials else None)
    if token is None:
        return ANONYMOUS

    try:
        claims = decode_token(token, ACCESS_TOKEN_TYPE)
    except TokenError:
        raise _unauthorized("Invalid or expired token")

    username = claims["sub"]
    user = UserRepository(session).get_by_username(username)
    if user is None or not user.is_active:
        raise _unauthorized("User no longer valid")

    return Principal(role=Role(user.role), username=user.username)


def require_role(minimum: Role) -> Callable[..., Principal]:
    """
    Build a dependency that requires the caller to have at least *minimum* role.

    Returns the resolved ``Principal`` so handlers can read the current user.
    Anonymous callers hitting a protected endpoint get 401 (not authenticated);
    authenticated callers with an insufficient role get 403 (forbidden).
    """

    def dependency(
        principal: Annotated[Principal, Depends(get_current_principal)],
    ) -> Principal:
        if principal.role.satisfies(minimum):
            return principal
        if not principal.is_authenticated:
            raise _unauthorized("Authentication required")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient privileges for this resource",
        )

    return dependency


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )
