from typing import Annotated, Dict, List
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from datetime import date, datetime
from zoneinfo import ZoneInfoNotFoundError

from sqlmodel import Session

from app.api.deps import (
    EtagRepositoryDep,
    UnitOfWorkDep,
    get_location,
    get_panchangam_service,
    require_role,
)
from app.db.database import get_session
from app.features.panchangam.schemas.GetInstantPanchangamParams import GetInstantPanchangamParams
from app.features.panchangam.schemas.GetMonthlyPanchangamParams import GetMonthlyPanchangamParams
from app.features.panchangam.schemas.GetSunriseSunsetParams import GetSunriseSunsetParams
from app.features.panchangam.schemas.GetYearlyPanchangamParams import GetYearlyPanchangamParams
from app.features.panchangam.schemas.SunriseSunsetResponse import SunriseSunsetResponse
from app.features.panchangam.service import PanchangamService, YearOutOfRange
from app.schemas.compact_panchangam_data import CompactPanchangamData, CompactSanthigiriEvent
from app.schemas.location import LocationInfo
from app.services.etag_service import (
    build_enum_payload,
    build_year_payload,
    conditional_json_response,
    enum_key,
    year_key,
)
from app.utils.location import Location
from app.utils.malayalam_masa import MalayalamMasa
from app.utils.nakshatra import Nakshatra
from app.utils.roles import Role
from app.utils.thithi import Thithi


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
    # reloaded (see services.etag_service), or computed lazily on first request.
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



# The enum reference datasets are read from the database (not the Python enums)
# so DB edits — e.g. to Santhigiri event names/descriptions — are reflected.
# Each is served ETag-validated so the frontend can revalidate cheaply and reuse
# its cached copy on a 304. See services.etag_service for the payloads.

def _reference_response(
    request: Request,
    session: Session,
    etag_repository: EtagRepositoryDep,
    unit_of_work: UnitOfWorkDep,
    name: str,
) -> Response:
    return conditional_json_response(
        request,
        etag_repository,
        unit_of_work,
        enum_key(name),
        lambda: build_enum_payload(session, name),
    )


@router.get(
    '/thithi',
    response_model= List[Thithi]
)
def thithi_reference(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    etag_repository: EtagRepositoryDep,
    unit_of_work: UnitOfWorkDep,
) -> Response:
    return _reference_response(request, session, etag_repository, unit_of_work, "thithi")


@router.get(
    '/nakshatra',
    response_model= List[Nakshatra]
)
def nakshatra_reference(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    etag_repository: EtagRepositoryDep,
    unit_of_work: UnitOfWorkDep,
) -> Response:
    return _reference_response(request, session, etag_repository, unit_of_work, "nakshatra")


@router.get(
    '/masa',
    response_model= List[MalayalamMasa]
)
def masa_reference(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    etag_repository: EtagRepositoryDep,
    unit_of_work: UnitOfWorkDep,
) -> Response:
    return _reference_response(request, session, etag_repository, unit_of_work, "masa")


@router.get(
    '/events',
    response_model= List[CompactSanthigiriEvent]
)
def events_reference(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    etag_repository: EtagRepositoryDep,
    unit_of_work: UnitOfWorkDep,
) -> Response:
    return _reference_response(request, session, etag_repository, unit_of_work, "events")


@router.get(
    '/locations',
    response_model= List[LocationInfo]
)
def locations_reference(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    etag_repository: EtagRepositoryDep,
    unit_of_work: UnitOfWorkDep,
) -> Response:
    # The list of locations a client can request via ?location=<code>.
    return _reference_response(request, session, etag_repository, unit_of_work, "locations")

