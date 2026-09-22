"""
Shared FastAPI dependencies for the API layer.

Two concerns live here:

* **Service wiring** — ``get_service`` builds a ``PanchangamService`` from a
  request-scoped DB session, replacing the ``_get_service`` helper that was
  previously duplicated in each route module.

* **Authentication / authorization** — ``get_current_principal`` verifies the
  bearer token (if any) against TVM's JWKS (``core.security.verify_access_token``)
  and resolves it into a ``Principal``; ``require_role`` is a dependency
  factory that gates an endpoint at a minimum ``Role``. Every request resolves
  to either an authenticated principal backed by a valid TVM-issued access
  token, or the ``anonymous`` principal when no token is presented. A
  malformed, expired, or unverifiable token is rejected outright (401) rather
  than being downgraded to anonymous. Chandiroor never mints tokens or looks
  up a local user record — the token's claims are trusted as-is.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session

from app.core.ports.panchangam_service import PanchangamServicePort
from app.core.ports.reference_repository import ReferenceRepositoryPort
from app.core.ports.unit_of_work import UnitOfWork
from app.core.security import TokenError, verify_access_token
from app.db.database import get_session
from app.db.reference_repository import ReferenceRepository
from app.db.unit_of_work import SqlUnitOfWork
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
from app.features.settings.service import SettingsService
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


def get_reference_repository(session: SessionDep) -> ReferenceRepositoryPort:
    return ReferenceRepository(session)


ReferenceRepositoryDep = Annotated[
    ReferenceRepositoryPort, Depends(get_reference_repository)
]


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
    reference_repository: ReferenceRepositoryDep,
    settings_service: SettingsServiceDep,
    panchangam_service_for_etag_refresh: PanchangamServiceForEtagRefreshDep,
    unit_of_work: UnitOfWorkDep,
) -> SanthigiriEventService:
    return SanthigiriEventService(
        reference_repository=reference_repository,
        event_repository=event_repository,
        etag_repository=etag_repository,
        panchangam_repo=panchangam_repository,
        settings=settings_service,
        panchangam_service_for_etag_refresh=panchangam_service_for_etag_refresh,
        unit_of_work=unit_of_work,
    )


def get_panchangam_service(
    panchangam_repository: PanchangamRepositoryDep,
    settings_service: SettingsServiceDep,
) -> PanchangamService:
    return PanchangamService(panchangam_repository, settings_service)


def get_panchangam_service_for_etag_refresh(
    panchangam_repository: PanchangamRepositoryDep,
) -> PanchangamServicePort:
    """A ``PanchangamService`` built *without* a ``SettingsServicePort`` — the
    binding ``features/etag/service.py::refresh_etags`` gets injected for its
    year-payload rebuild.

    Deliberately settings-free: refresh_etags runs right after a write (bulk
    seed, admin generate, event-occurrence regeneration) that may target a
    year outside the currently configured ``seed_year_range``, and refreshing
    that year's ETag must not fail with ``YearOutOfRange`` the way a normal
    ``/year`` read would. This preserves the range-check-free behaviour the
    bulk ETag refresh has always had.
    """
    return PanchangamService(panchangam_repository)


PanchangamServiceForEtagRefreshDep = Annotated[
    PanchangamServicePort, Depends(get_panchangam_service_for_etag_refresh)
]


def get_panchangam_generation_service(
    panchangam_repository: PanchangamRepositoryDep,
    settings_service: SettingsServiceDep,
    etag_repository: EtagRepositoryDep,
    reference_repository: ReferenceRepositoryDep,
    panchangam_service_for_etag_refresh: PanchangamServiceForEtagRefreshDep,
    unit_of_work: UnitOfWorkDep,
) -> PanchangamGenerationService:
    return PanchangamGenerationService(
        reference_repository=reference_repository,
        repository=panchangam_repository,
        settings=settings_service,
        etag_repository=etag_repository,
        panchangam_service_for_etag_refresh=panchangam_service_for_etag_refresh,
        unit_of_work=unit_of_work,
    )


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
    user_id: int | None = None

    @property
    def is_authenticated(self) -> bool:
        return self.role is not Role.ANONYMOUS


ANONYMOUS = Principal(role=Role.ANONYMOUS)

# auto_error=False so requests without an Authorization header are allowed
# through as the anonymous principal instead of being rejected here.
_bearer = HTTPBearer(auto_error=False)


def get_current_principal(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> Principal:
    """
    Resolve the request's identity from its ``Authorization: Bearer`` access
    token, verified against TVM's JWKS.

    * No header → the anonymous principal.
    * A token that verifies against TVM's JWKS → that token's principal,
      trusted as-is (no local user lookup — Chandiroor owns no user data).
    * A malformed/expired/unverifiable token → 401.
    """
    if credentials is None:
        return ANONYMOUS

    try:
        claims = verify_access_token(credentials.credentials)
    except TokenError:
        raise _unauthorized("Invalid or expired token")

    return Principal(role=claims.role, user_id=claims.user_id)


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
