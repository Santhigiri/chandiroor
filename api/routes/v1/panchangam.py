from typing import Annotated, Dict, List
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from datetime import date, datetime

from sqlmodel import Session

from api.deps import get_location, get_service, require_role
from db.database import get_session
from schemas.compact_panchangam_data import CompactPanchangamData, CompactSanthigiriEvent
from schemas.GetMonthlyPanchangamParams import GetMonthlyPanchangamParams
from schemas.GetSunriseSunsetParams import GetSunriseSunsetParams
from schemas.GetYearlyPanchangamParams import GetYearlyPanchangamParams
from schemas.location import LocationInfo
from schemas.SunriseSunsetResponse import SunriseSunsetResponse
from services.etag_service import (
    build_enum_payload,
    build_year_payload,
    conditional_json_response,
    enum_key,
    year_key,
)
from services.panchangam_service import PanchangamService, YearOutOfRange
from utils.location import Location
from utils.malayalam_masa import MalayalamMasa
from utils.nakshatra import Nakshatra
from utils.roles import Role
from utils.thithi import Thithi


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
    service: Annotated[PanchangamService, Depends(get_service)],
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
    service: Annotated[PanchangamService, Depends(get_service)],
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
    '/month',
    response_model=Dict[date, CompactPanchangamData]
)
def panchangam_monthly(
    params: Annotated[GetMonthlyPanchangamParams, Query()],
    service: Annotated[PanchangamService, Depends(get_service)],
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
    service: Annotated[PanchangamService, Depends(get_service)],
    location: Annotated[Location, Depends(get_location)],
    session: Annotated[Session, Depends(get_session)],
) -> Response:
    # ETag-validated: unchanged years return 304 so the frontend skips the
    # full-year download. The ETag key includes the location code so different
    # locations don't collide. The stored ETag is refreshed whenever the data is
    # reloaded (see services.etag_service), or computed lazily on first request.
    try:
        return conditional_json_response(
            request,
            session,
            year_key(params.year, location.code),
            lambda: build_year_payload(service, params.year, location),
        )
    except YearOutOfRange as exc:
        raise HTTPException(status_code=422, detail=str(exc))



# The enum reference datasets are read from the database (not the Python enums)
# so DB edits — e.g. to Santhigiri event names/descriptions — are reflected.
# Each is served ETag-validated so the frontend can revalidate cheaply and reuse
# its cached copy on a 304. See services.etag_service for the payloads.

def _reference_response(request: Request, session: Session, name: str) -> Response:
    return conditional_json_response(
        request, session, enum_key(name), lambda: build_enum_payload(session, name)
    )


@router.get(
    '/thithi',
    response_model= List[Thithi]
)
def thithi_reference(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> Response:
    return _reference_response(request, session, "thithi")


@router.get(
    '/nakshatra',
    response_model= List[Nakshatra]
)
def nakshatra_reference(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> Response:
    return _reference_response(request, session, "nakshatra")


@router.get(
    '/masa',
    response_model= List[MalayalamMasa]
)
def masa_reference(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> Response:
    return _reference_response(request, session, "masa")


@router.get(
    '/events',
    response_model= List[CompactSanthigiriEvent]
)
def events_reference(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> Response:
    return _reference_response(request, session, "events")


@router.get(
    '/locations',
    response_model= List[LocationInfo]
)
def locations_reference(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> Response:
    # The list of locations a client can request via ?location=<code>.
    return _reference_response(request, session, "locations")

