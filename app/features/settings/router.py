"""
Application-wide tunable settings, mounted under ``/api/v1``:

* ``GET /api/v1/settings``       — list every setting                        (mixed)
* ``GET /api/v1/settings/{key}`` — fetch one setting                          (mixed)
* ``PUT /api/v1/settings/{key}`` — replace a setting's value                  (admin)

Most of these are internal tuning/ops knobs (generation caps, astronomy
search tuning, ...) and stay admin-only, including reads. ``PUBLIC_SETTING_KEYS``
is the small exception: ``calendar_range`` and ``languages`` are client-facing
config (what year range/languages a frontend should offer), so their reads are
public — any caller, authenticated or not, can read them; only writes and
every other key still require the ``admin`` role. See
``utils.settings_keys.SettingKey`` for the known keys and
``schemas.app_setting`` for each key's expected ``value`` shape.

Changing a setting here never retroactively rewrites already-stored
panchangam/event data (computed offline or via a previous generate run) — it
only affects future live computation and future admin-triggered
regeneration. See CLAUDE.md's existing warning about
``NAKSHATRA_TRANSITION_STEP_DAYS`` for the same caveat, now data-driven
instead of code-driven.

Both GET endpoints are ETag-validated via
``features.etag.service.etag_json_response``: the ETag is computed fresh from
the response on every request (unlike the year/enum reference endpoints,
these payloads are cheap enough that there's no benefit to persisting a
stored ETag), so a matching ``If-None-Match`` gets a ``304`` and any write
is reflected immediately with no separate invalidation step.
"""
from typing import Annotated, List

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.api.deps import Principal, get_current_principal, get_settings_service, require_role
from app.schemas.app_setting import AppSettingRead, AppSettingUpdate
from app.features.etag.service import etag_json_response
from app.features.settings.service import InvalidSettingValue, SettingNotFound, SettingsService
from app.utils.roles import Role
from app.utils.settings_keys import SettingKey

router = APIRouter(prefix="/settings", tags=["settings"])


_get_service = get_settings_service

PUBLIC_SETTING_KEYS = frozenset(
    {SettingKey.CALENDAR_RANGE.value, SettingKey.LANGUAGES.value}
)


def require_setting_read_access(
    key: str,
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> Principal:
    """Gate a single-setting read: *key* being in ``PUBLIC_SETTING_KEYS``
    lets any caller (including anonymous) through; every other key still
    needs the ``admin`` role, same as a write."""
    if key in PUBLIC_SETTING_KEYS or principal.role.satisfies(Role.ADMIN):
        return principal
    if not principal.is_authenticated:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Insufficient privileges for this resource",
    )


@router.get("", response_model=List[AppSettingRead])
def list_settings(
    request: Request,
    service: Annotated[SettingsService, Depends(_get_service)],
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> Response:
    """Admins see every setting; every other caller (including anonymous)
    sees only the keys in ``PUBLIC_SETTING_KEYS``."""
    rows = service.list_all()
    if not principal.role.satisfies(Role.ADMIN):
        rows = [row for row in rows if row.key in PUBLIC_SETTING_KEYS]
    payload = [AppSettingRead.model_validate(row) for row in rows]
    return etag_json_response(request, payload)


@router.get(
    "/{key}",
    response_model=AppSettingRead,
    dependencies=[Depends(require_setting_read_access)],
)
def get_setting(
    key: str,
    request: Request,
    service: Annotated[SettingsService, Depends(_get_service)],
) -> Response:
    try:
        row = service.get_row(key)
    except SettingNotFound:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=f"Setting '{key}' not found."
        )
    payload = AppSettingRead.model_validate(row)
    return etag_json_response(request, payload)


@router.put(
    "/{key}",
    response_model=AppSettingRead,
    dependencies=[Depends(require_role(Role.ADMIN))],
)
def update_setting(
    key: str,
    payload: AppSettingUpdate,
    service: Annotated[SettingsService, Depends(_get_service)],
) -> AppSettingRead:
    try:
        row = service.update(key, payload)
    except SettingNotFound:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=f"Setting '{key}' not found."
        )
    except InvalidSettingValue as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return AppSettingRead.model_validate(row)
