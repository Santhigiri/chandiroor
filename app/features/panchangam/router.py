from typing import Annotated, Dict
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from datetime import date, datetime
from zoneinfo import ZoneInfoNotFoundError

from app.api.deps import (
    EtagRepositoryDep,
    UnitOfWorkDep,
    get_location,
    get_panchangam_service,
    require_role,
)
from app.features.panchangam.schemas.GetInstantPanchangamParams import GetInstantPanchangamParams
from app.features.panchangam.schemas.GetMonthlyPanchangamParams import GetMonthlyPanchangamParams
from app.features.panchangam.schemas.GetSunriseSunsetParams import GetSunriseSunsetParams
from app.features.panchangam.schemas.GetYearlyPanchangamParams import GetYearlyPanchangamParams
from app.features.panchangam.schemas.SunriseSunsetResponse import SunriseSunsetResponse
from app.features.panchangam.service import PanchangamService, YearOutOfRange
from app.schemas.compact_panchangam_data import CompactPanchangamData
from app.features.etag.service import (
    build_year_payload,
    conditional_json_response,
    year_key,
)
from app.utils.location import Location
from app.utils.roles import Role


# Panchangam data is public: every endpoint on this router validates any bearer
# token that is supplied (rejecting malformed/expired ones) but still permits
# the anonymous principal, satisfying the per-endpoint privilege check.
router = APIRouter(
    prefix='/panchangam',
    dependencies=[Depends(require_role(Role.ANONYMOUS))],
)


@router.get(
    '/day',
    response_model=CompactPanchangamData
)
def panchangam(
    day: Annotated[date, Query()],
    service: Annotated[PanchangamService, Depends(get_panchangam_service)],
    location: Annotated[Location, Depends(get_location)],
):

    data = service.get_by_date(day, location)
    return CompactPanchangamData.from_panchangam_data(data)


@router.get(
    '/sunrise-sunset',
    response_model=SunriseSunsetResponse,
)
def sunrise_sunset(
    params: Annotated[GetSunriseSunsetParams, Query()],
    service: Annotated[PanchangamService, Depends(get_panchangam_service)],
):
    """Sunrise/sunset (UTC) for an arbitrary coordinate and date.

    Intended for clients that supply the device's live location (e.g. a
    user moving around during the day) rather than the Santhigiri Ashram
    default. Before computing, the submitted latitude/longitude are rounded
    to 1 decimal degree (~11 km) server-side so nearby callers share the
    same cached result; the accuracy cost of this is negligible (at most
    ~14 seconds of sunrise/sunset shift, even at the solstices). The
    response still echoes back the coordinates as submitted — only the
    internal computation snaps to the grid.
    """
    try:
        sunrise, sunset = service.get_sunrise_sunset(
            params.day, params.latitude, params.longitude
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return SunriseSunsetResponse(
        latitude=params.latitude,
        longitude=params.longitude,
        day=params.day,
        sunrise=sunrise,
        sunset=sunset,
    )


@router.get(
    '/instant',
    response_model=CompactPanchangamData,
)
def panchangam_instant(
    params: Annotated[GetInstantPanchangamParams, Query()],
    service: Annotated[PanchangamService, Depends(get_panchangam_service)],
):
    """Compact Panchangam active at an arbitrary date/time/location instant.

    Intended for clients (e.g. the Starfinder page) that supply their own
    date, time-of-day, and coordinates rather than relying on the Santhigiri
    Ashram default. Always live-computed; no DB lookup involved.
    """
    try:
        data = service.get_panchangam_at_instant(
            params.day, params.time, params.latitude, params.longitude, params.timezone
        )
    except (ValueError, ZoneInfoNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return CompactPanchangamData.from_panchangam_data(data)


@router.get(
    '/month',
    response_model=Dict[date, CompactPanchangamData]
)
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
    except YearOutOfRange as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {
        day: CompactPanchangamData.from_panchangam_data(value)
        for day, value in data.items()
    }


@router.get('/year')
def panchangam_yearly(
    request: Request,
    params: Annotated[GetYearlyPanchangamParams, Query()],
    service: Annotated[PanchangamService, Depends(get_panchangam_service)],
    location: Annotated[Location, Depends(get_location)],
    etag_repository: EtagRepositoryDep,
    unit_of_work: UnitOfWorkDep,
) -> Response:
    # ETag-validated: unchanged years return 304 so the frontend skips the
    # full-year download. The ETag key includes the location code so different
    # locations don't collide. The stored ETag is refreshed whenever the data is
    # reloaded (see features.etag.service), or computed lazily on first request.
    try:
        return conditional_json_response(
            request,
            etag_repository,
            unit_of_work,
            year_key(params.year, location.code),
            lambda: build_year_payload(service, params.year, location),
        )
    except YearOutOfRange as exc:
        raise HTTPException(status_code=422, detail=str(exc))

