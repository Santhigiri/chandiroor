from typing import Annotated, Dict
from fastapi import APIRouter, Depends, Query, Request, Response
from datetime import date, datetime

from sqlmodel import Session

from db.database import get_session
from db.repository import PanchangamRepository
from schemas.compact_panchangam_data import CompactPanchangamData
from schemas.GetMonthlyPanchangamParams import GetMonthlyPanchangamParams
from schemas.GetYearlyPanchangamParams import GetYearlyPanchangamParams
from schemas.GetDayPanchangamParams import GetPanchangamParams
from services.etag_service import (
    build_enum_payload,
    build_year_payload,
    conditional_json_response,
    enum_key,
    year_key,
)
from services.panchangam_service import PanchangamService


router = APIRouter(prefix='/panchangam')


def _get_service(session: Annotated[Session, Depends(get_session)]) -> PanchangamService:
    return PanchangamService(PanchangamRepository(session))


@router.get(
    '/day',
    response_model=CompactPanchangamData
)
def panchangam(
    day: Annotated[date, Query()],
    service: Annotated[PanchangamService, Depends(_get_service)],
):

    data = service.get_by_date(day)
    return CompactPanchangamData.from_panchangam_data(data)


@router.get(
    '/month',
    response_model=Dict[date, CompactPanchangamData]
)
def panchangam_monthly(
    params: Annotated[GetMonthlyPanchangamParams, Query()],
    service: Annotated[PanchangamService, Depends(_get_service)],
):
    data = service.get_by_month(
        year=params.year,
        month=params.month,
    )
    return {
        day: CompactPanchangamData.from_panchangam_data(value)
        for day, value in data.items()
    }


@router.get('/year')
def panchangam_yearly(
    request: Request,
    params: Annotated[GetYearlyPanchangamParams, Query()],
    service: Annotated[PanchangamService, Depends(_get_service)],
    session: Annotated[Session, Depends(get_session)],
) -> Response:
    # ETag-validated: unchanged years return 304 so the frontend skips the
    # full-year download. The stored ETag is refreshed whenever the data is
    # reloaded (see db.migrate / services.etag_service).
    return conditional_json_response(
        request,
        session,
        year_key(params.year),
        lambda: build_year_payload(service, params.year),
    )



# The enum reference datasets are read from the database (not the Python enums)
# so DB edits — e.g. to Santhigiri event names/descriptions — are reflected.
# Each is served ETag-validated so the frontend can revalidate cheaply and reuse
# its cached copy on a 304. See services.etag_service for the payloads.

def _reference_response(request: Request, session: Session, name: str) -> Response:
    return conditional_json_response(
        request, session, enum_key(name), lambda: build_enum_payload(session, name)
    )


@router.get('/thithi')
def thithi_reference(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> Response:
    return _reference_response(request, session, "thithi")


@router.get('/nakshatra')
def nakshatra_reference(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> Response:
    return _reference_response(request, session, "nakshatra")


@router.get('/masa')
def masa_reference(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> Response:
    return _reference_response(request, session, "masa")


@router.get('/events')
def events_reference(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> Response:
    return _reference_response(request, session, "events")

