"""
Admin CRUD for application-wide tunable settings, mounted under ``/api/v1``:

* ``GET /api/v1/settings``       — list every setting                        (admin)
* ``GET /api/v1/settings/{key}`` — fetch one setting                          (admin)
* ``PUT /api/v1/settings/{key}`` — replace a setting's value                  (admin)

Unlike the public-read Santhigiri event definitions, every endpoint here
requires the ``admin`` role, including reads — these are internal
tuning/ops knobs (calendar year bounds, generation caps, astronomy search
tuning), not ashram-facing reference data. See ``utils.settings_keys.SettingKey``
for the known keys and ``schemas.app_setting`` for each key's expected
``value`` shape.

Changing a setting here never retroactively rewrites already-stored
panchangam/event data (computed offline or via a previous generate run) — it
only affects future live computation and future admin-triggered
regeneration. See CLAUDE.md's existing warning about
``NAKSHATRA_TRANSITION_STEP_DAYS`` for the same caveat, now data-driven
instead of code-driven.
"""
from typing import Annotated, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from api.deps import require_role
from db.database import get_session
from schemas.app_setting import AppSettingRead, AppSettingUpdate
from services.settings_service import InvalidSettingValue, SettingNotFound, SettingsService
from utils.roles import Role

router = APIRouter(
    prefix="/settings",
    tags=["settings"],
    dependencies=[Depends(require_role(Role.ADMIN))],
)


def _get_service(
    session: Annotated[Session, Depends(get_session)],
) -> SettingsService:
    return SettingsService(session)


@router.get("", response_model=List[AppSettingRead])
def list_settings(
    service: Annotated[SettingsService, Depends(_get_service)],
) -> List[AppSettingRead]:
    return [AppSettingRead.model_validate(row) for row in service.list_all()]


@router.get("/{key}", response_model=AppSettingRead)
def get_setting(
    key: str,
    service: Annotated[SettingsService, Depends(_get_service)],
) -> AppSettingRead:
    try:
        row = service.get_row(key)
    except SettingNotFound:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=f"Setting '{key}' not found."
        )
    return AppSettingRead.model_validate(row)


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
