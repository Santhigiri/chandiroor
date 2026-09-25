"""
v2 admin settings endpoints — same data as ``features/settings/router.py`` (v1),
wrapped in the ``{success, message, data}`` envelope (``app/api/envelope.py``):

* ``GET /api/v2/settings``       — list every setting  (admin)
* ``GET /api/v2/settings/{key}`` — fetch one setting     (admin)
* ``PUT /api/v2/settings/{key}`` — replace a setting's value (admin)

Additive sibling: v1's endpoints are untouched.
"""
from typing import Annotated, List

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.api.deps import get_settings_service, require_role
from app.api.envelope import AppHTTPException, envelope, ok
from app.schemas.api_response import ApiResponse, MessageCode
from app.schemas.app_setting import AppSettingRead, AppSettingUpdate
from app.features.etag.service import etag_json_response
from app.features.settings.service import InvalidSettingValue, SettingNotFound, SettingsService
from app.utils.roles import Role

router = APIRouter(
    prefix="/settings",
    tags=["settings"],
    dependencies=[Depends(require_role(Role.ADMIN))],
)


_get_service = get_settings_service


@router.get("", response_model=ApiResponse[List[AppSettingRead]])
def list_settings_v2(
    request: Request,
    service: Annotated[SettingsService, Depends(_get_service)],
) -> Response:
    payload = [AppSettingRead.model_validate(row) for row in service.list_all()]
    return etag_json_response(
        request, payload, body_transform=envelope(MessageCode.SETTINGS_LIST_SUCCESS)
    )


@router.get("/{key}", response_model=ApiResponse[AppSettingRead])
def get_setting_v2(
    key: str,
    request: Request,
    service: Annotated[SettingsService, Depends(_get_service)],
) -> Response:
    try:
        row = service.get_row(key)
    except SettingNotFound:
        raise AppHTTPException(
            status.HTTP_404_NOT_FOUND, f"Setting '{key}' not found.", MessageCode.SETTING_NOT_FOUND
        )
    payload = AppSettingRead.model_validate(row)
    return etag_json_response(
        request, payload, body_transform=envelope(MessageCode.SETTING_FETCHED)
    )


@router.put("/{key}", response_model=ApiResponse[AppSettingRead])
def update_setting_v2(
    key: str,
    payload: AppSettingUpdate,
    service: Annotated[SettingsService, Depends(_get_service)],
):
    try:
        row = service.update(key, payload)
    except SettingNotFound:
        raise AppHTTPException(
            status.HTTP_404_NOT_FOUND, f"Setting '{key}' not found.", MessageCode.SETTING_NOT_FOUND
        )
    except InvalidSettingValue as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return ok(data=AppSettingRead.model_validate(row), message=MessageCode.SETTING_UPDATED)
