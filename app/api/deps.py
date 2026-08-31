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

from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session

from app.core.ports.unit_of_work import UnitOfWork
from app.db.database import get_session
from app.db.unit_of_work import SqlUnitOfWork
from app.features.auth.auth_repository import AuthRepository
from app.features.auth.ports import AuthRepositoryPort, UserNotFoundException
from app.features.auth.service import AuthService, InvalidTokenException
from app.features.etag.ports import EtagRepositoryPort
from app.features.etag.repository import EtagRepository
from app.features.panchangam.generation_service import PanchangamGenerationService
from app.features.panchangam.ports import PanchangamRepositoryPort
from app.features.panchangam.repository import PanchangamRepository
from app.features.panchangam.service import PanchangamService
from app.features.santhigiri_events.ports import SanthigiriEventsRepositoryPort
from app.features.santhigiri_events.repository import SanthigiriEventRepository
from app.features.santhigiri_events.service import SanthigiriEventService
from app.features.settings.ports import AppSettingRepositoryPort
from app.features.settings.repository import AppSettingRepository
from app.services.settings_service import SettingsService
from app.utils.location import Location
from app.utils.roles import Role

SessionDep = Annotated[Session, Depends(get_session)]


# ── Service wiring ────────────────────────────────────────────────────────────
def get_unit_of_work(session: Annotated[Session, Depends(get_session)]) -> UnitOfWork:
    return SqlUnitOfWork(session)


UnitOfWorkDep = Annotated[UnitOfWork, Depends(get_unit_of_work)]


def get_app_setting_repository(session: SessionDep) -> AppSettingRepositoryPort:
    return AppSettingRepository(session)


AppSettingRepositoryDep = Annotated[
    AppSettingRepositoryPort, Depends(get_app_setting_repository)
]


def get_settings_service(
    app_setting_repository: AppSettingRepositoryDep,
    unit_of_work: UnitOfWorkDep,
) -> SettingsService:
    return SettingsService(app_setting_repository, unit_of_work)


SettingsServiceDep = Annotated[SettingsService, Depends(get_settings_service)]


def get_etag_repository(session: SessionDep) -> EtagRepositoryPort:
    return EtagRepository(session)


EtagRepositoryDep = Annotated[EtagRepositoryPort, Depends(get_etag_repository)]


def get_panchangam_repository(
    session: SessionDep,
) -> PanchangamRepositoryPort:
    return PanchangamRepository(session=session)


PanchangamRepositoryDep = Annotated[
    PanchangamRepositoryPort, Depends(get_panchangam_repository)
]


def get_santhigiri_event_repository(
    session: SessionDep,
) -> SanthigiriEventsRepositoryPort:
    return SanthigiriEventRepository(session=session)


SanthigiriEventRepositoryDep = Annotated[
    SanthigiriEventsRepositoryPort, Depends(get_santhigiri_event_repository)
]


def get_santhigiri_event_service(
    panchangam_repository: PanchangamRepositoryDep,
    event_repository: SanthigiriEventRepositoryDep,
    etag_repository: EtagRepositoryDep,
    session: SessionDep,
    settings_service: SettingsServiceDep,
    unit_of_work: UnitOfWorkDep,
) -> SanthigiriEventService:
    return SanthigiriEventService(
        session=session,
        event_repository=event_repository,
        etag_repository=etag_repository,
        panchangam_repo=panchangam_repository,
        settings=settings_service,
        unit_of_work=unit_of_work,
    )


def get_panchangam_service(
    panchangam_repository: PanchangamRepositoryDep,
    settings_service: SettingsServiceDep,
) -> PanchangamService:
    return PanchangamService(panchangam_repository, settings_service)


def get_panchangam_generation_service(
    session: SessionDep,
    panchangam_repository: PanchangamRepositoryDep,
    settings_service: SettingsServiceDep,
    etag_repository: EtagRepositoryDep,
    unit_of_work: UnitOfWorkDep,
) -> PanchangamGenerationService:
    return PanchangamGenerationService(
        session=session,
        repository=panchangam_repository,
        settings=settings_service,
        etag_repository=etag_repository,
        unit_of_work=unit_of_work,
    )


def get_auth_repository(session: SessionDep) -> AuthRepositoryPort:
    return AuthRepository(session)


AuthRepositoryDep = Annotated[AuthRepositoryPort, Depends(get_auth_repository)]


def get_auth_service(
    auth_repository: AuthRepositoryDep,
    uow: UnitOfWorkDep,
) -> AuthService:
    return AuthService(auth_repository, uow)


# ── Location selection ────────────────────────────────────────────────────────


def get_location(
    settings_service: Annotated[SettingsService, Depends(get_settings_service)],
    location: Annotated[
        str | None, Query(description="Location code, e.g. 'tvm'")
    ] = None,
) -> Location:
    """Resolve the ``?location=`` query param (a location code) to a ``Location``.

    Defaults to the admin-configured ``default_location_code`` setting (the
    ashram, ``tvm``, unless changed) when omitted. An unknown code is a 404 —
    the caller asked for a location the API does not serve.
    """
    code = (
        location
        if location is not None
        else settings_service.get_default_location_code()
    )
    try:
        return Location.from_code(code)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown location code: {code!r}",
        )


# ── Principal ─────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Principal:
    """The authenticated (or anonymous) identity behind a request."""

    role: Role
    username: str | None = None

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
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    access_token: Annotated[str | None, Cookie()] = None,
    auth_service: AuthService = Depends(get_auth_service),
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
        user = auth_service.resolve_principal_credentials(token)
    except InvalidTokenException:
        raise _unauthorized("Invalid or expired token")
    except UserNotFoundException:
        raise _unauthorized("User Not Found")
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
