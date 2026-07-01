from typing import Annotated
from fastapi import APIRouter, Depends, Query, Request, Response
from datetime import datetime

from sqlmodel import Session

from db.database import get_session
from db.repository import PanchangamRepository
from schemas.GetMonthlyPanchangamParams import GetMonthlyPanchangamParams
from schemas.GetDayPanchangamParams import GetPanchangamParams
from services.etag_service import (
    build_enum_payload,
    conditional_json_response,
    enum_key,
)
from services.panchangam_service import PanchangamService


router = APIRouter(prefix='/panchangam')


def _get_service(session: Annotated[Session, Depends(get_session)]) -> PanchangamService:
    return PanchangamService(PanchangamRepository(session))


@router.get('/')
def panchangam(
    params: Annotated[GetPanchangamParams, Query()],
    service: Annotated[PanchangamService, Depends(_get_service)],
):
    try:
        parsed_date = datetime.strptime(str(params.date_str), "%Y-%m-%d").date()
    except ValueError:
        return {'error': 'Invalid Date format. Use YYYY-MM-DD'}, 400

    return service.get_by_date(parsed_date)


@router.get('/monthly')
def panchangam_monthly(
    params: Annotated[GetMonthlyPanchangamParams, Query()],
    service: Annotated[PanchangamService, Depends(_get_service)],
):
    return service.get_by_month(
        year=params.year,
        month=params.month,
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
