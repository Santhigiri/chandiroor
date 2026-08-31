"""
Admin CRUD for application-wide tunable settings, mounted under ``/api/v1``:

* ``GET /api/v1/settings``       — list every setting                        (admin)
* ``GET /api/v1/settings/{key}`` — fetch one setting                          (admin)
* ``PUT /api/v1/settings/{key}`` — replace a setting's value                  (admin)

Unlike the public-read Santhigiri event definitions, every endpoint here
requires the ``admin`` role, including reads — these are internal
tuning/ops knobs (calendar year bounds, generation caps, astronomy search
tuning), not ashram-facing reference data. See ``utils.settings_keys.SettingKey``
for the known keys and ``shared.schemas.app_setting`` for each key's expected
``value`` shape.

Changing a setting here never retroactively rewrites already-stored
panchangam/event data (computed offline or via a previous generate run) — it
only affects future live computation and future admin-triggered
regeneration. See CLAUDE.md's existing warning about
``NAKSHATRA_TRANSITION_STEP_DAYS`` for the same caveat, now data-driven
instead of code-driven.

Both GET endpoints are ETag-validated via
``shared.services.etag_service.etag_json_response``: the ETag is computed fresh from
the response on every request (unlike the year/enum reference endpoints,
these payloads are cheap enough that there's no benefit to persisting a
stored ETag), so a matching ``If-None-Match`` gets a ``304`` and any write
is reflected immediately with no separate invalidation step.
"""
from typing import Annotated, List

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.api.deps import get_settings_service, require_role
from app.shared.schemas.app_setting import AppSettingRead, AppSettingUpdate
from app.shared.services.etag_service import etag_json_response
from app.shared.services.settings_service import InvalidSettingValue, SettingNotFound, SettingsService
from app.utils.roles import Role

router = APIRouter(
    prefix="/settings",
    tags=["settings"],
    dependencies=[Depends(require_role(Role.ADMIN))],
)


_get_service = get_settings_service


@router.get("", response_model=List[AppSettingRead])
def list_settings(
    request: Request,
    service: Annotated[SettingsService, Depends(_get_service)],
) -> Response:
    payload = [AppSettingRead.model_validate(row) for row in service.list_all()]
    return etag_json_response(request, payload)


@router.get("/{key}", response_model=AppSettingRead)
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


@router.put("/{key}", response_model=AppSettingRead)
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
