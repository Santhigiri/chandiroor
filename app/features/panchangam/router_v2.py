"""
v2 panchangam endpoints — same data/computation as ``features/panchangam/router.py``
(v1), wrapped in the ``{success, message, data}`` envelope (``app/api/envelope.py``).

Additive sibling: v1's endpoints are untouched. Declares only its own
feature-local prefix — ``main.py`` mounts it under ``/api/v2`` — per
CLAUDE.md's "Versioning without a `v1/` directory".
"""
from typing import Annotated, Dict
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from datetime import date
from zoneinfo import ZoneInfoNotFoundError

from app.api.deps import (
    EtagRepositoryDep,
    UnitOfWorkDep,
    get_location,
    get_panchangam_service,
    require_role,
)
from app.api.envelope import envelope, ok
from app.features.panchangam.schemas.get_instant_panchangam_params import GetInstantPanchangamParams
from app.features.panchangam.schemas.get_monthly_panchangam_params import GetMonthlyPanchangamParams
from app.features.panchangam.schemas.get_sunrise_sunset_params import GetSunriseSunsetParams
from app.features.panchangam.schemas.get_sunrise_sunset_range_params import (
    GetSunriseSunsetRangeParams,
)
from app.features.panchangam.schemas.get_yearly_panchangam_params import GetYearlyPanchangamParams
from app.features.panchangam.schemas.sunrise_sunset_response import SunriseSunsetResponse
from app.features.panchangam.schemas.sunrise_sunset_range_response import (
    SunriseSunsetDay,
    SunriseSunsetRangeResponse,
)
from app.features.panchangam.service import (
    ChandraMasaNotFoundError,
    PanchangamService,
    YearOutOfRange,
)
from app.schemas.api_response import ApiResponse, MessageCode
from app.schemas.compact_panchangam_data import CompactPanchangamData
from app.features.etag.service import (
    build_year_payload,
    conditional_json_response,
    year_key,
)
from app.utils.location import Location
from app.utils.roles import Role


router = APIRouter(
    prefix='/panchangam',
    dependencies=[Depends(require_role(Role.ANONYMOUS))],
)


@router.get('/day', response_model=ApiResponse[CompactPanchangamData])
def panchangam(
    day: Annotated[date, Query()],
    service: Annotated[PanchangamService, Depends(get_panchangam_service)],
    location: Annotated[Location, Depends(get_location)],
):
    try:
        data = service.get_by_date(day, location)
    except ChandraMasaNotFoundError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return ok(
        data=CompactPanchangamData.from_panchangam_data(data),
        message=MessageCode.PANCHANGAM_DAY_SUCCESS,
    )


@router.get('/sunrise-sunset', response_model=ApiResponse[SunriseSunsetResponse])
def sunrise_sunset(
    params: Annotated[GetSunriseSunsetParams, Query()],
    service: Annotated[PanchangamService, Depends(get_panchangam_service)],
):
    try:
        sunrise, sunset = service.get_sunrise_sunset(
            params.day, params.latitude, params.longitude
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return ok(
        data=SunriseSunsetResponse(
            latitude=params.latitude,
            longitude=params.longitude,
            day=params.day,
            sunrise=sunrise,
            sunset=sunset,
        ),
        message=MessageCode.SUNRISE_SUNSET_SUCCESS,
    )


@router.get('/sunrise-sunset/range', response_model=ApiResponse[SunriseSunsetRangeResponse])
def sunrise_sunset_range(
    params: Annotated[GetSunriseSunsetRangeParams, Query()],
    service: Annotated[PanchangamService, Depends(get_panchangam_service)],
):
    try:
        results = service.get_sunrise_sunset_range(
            params.start_date, params.end_date, params.latitude, params.longitude
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return ok(
        data=SunriseSunsetRangeResponse(
            latitude=params.latitude,
            longitude=params.longitude,
            start_date=params.start_date,
            end_date=params.end_date,
            results={
                day: SunriseSunsetDay(sunrise=sunrise, sunset=sunset)
                for day, (sunrise, sunset) in results.items()
            },
        ),
        message=MessageCode.SUNRISE_SUNSET_RANGE_SUCCESS,
    )


@router.get('/instant', response_model=ApiResponse[CompactPanchangamData])
def panchangam_instant(
    params: Annotated[GetInstantPanchangamParams, Query()],
    service: Annotated[PanchangamService, Depends(get_panchangam_service)],
):
    try:
        data = service.get_panchangam_at_instant(
            params.day, params.time, params.latitude, params.longitude, params.timezone
        )
    except (ValueError, ZoneInfoNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except ChandraMasaNotFoundError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return ok(
        data=CompactPanchangamData.from_panchangam_data(data),
        message=MessageCode.PANCHANGAM_INSTANT_SUCCESS,
    )


@router.get('/month', response_model=ApiResponse[Dict[date, CompactPanchangamData]])
def panchangam_monthly(
    params: Annotated[GetMonthlyPanchangamParams, Query()],
    service: Annotated[PanchangamService, Depends(get_panchangam_service)],
    location: Annotated[Location, Depends(get_location)],
):
    try:
        data = service.get_by_month(
            year=params.year,
            month=params.month,
            location=location,
        )
    except (YearOutOfRange, ChandraMasaNotFoundError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return ok(
        data={
            day: CompactPanchangamData.from_panchangam_data(value)
            for day, value in data.items()
        },
        message=MessageCode.PANCHANGAM_MONTH_SUCCESS,
    )


@router.get('/year')
def panchangam_yearly(
    request: Request,
    params: Annotated[GetYearlyPanchangamParams, Query()],
    service: Annotated[PanchangamService, Depends(get_panchangam_service)],
    location: Annotated[Location, Depends(get_location)],
    etag_repository: EtagRepositoryDep,
    unit_of_work: UnitOfWorkDep,
) -> Response:
    # Same ETag key as v1's /year (year_key(year, location.code)) — the
    # underlying data is identical, so v1 and v2 share one stored ETag row.
    try:
        return conditional_json_response(
            request,
            etag_repository,
            unit_of_work,
            year_key(params.year, location.code),
            lambda: build_year_payload(service, params.year, location),
            body_transform=envelope(MessageCode.PANCHANGAM_YEAR_SUCCESS),
        )
    except (YearOutOfRange, ChandraMasaNotFoundError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))
