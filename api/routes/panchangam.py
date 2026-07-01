from typing import Annotated
from fastapi import APIRouter, Depends, Query
from datetime import datetime

from sqlmodel import Session

from db.database import get_session
from db.repository import PanchangamRepository
from schemas.compact_panchangam_data import CompactPanchangamData
from schemas.GetMonthlyPanchangamParams import GetMonthlyPanchangamParams
from schemas.GetDayPanchangamParams import GetPanchangamParams
from services.panchangam_service import PanchangamService
from utils.malayalam_masa import MalayalamMasa
from utils.nakshatra import Nakshatra
from utils.santhigiri_events import EVENT_DEFINITIONS_BY_ID
from utils.thithi import Thithi


router = APIRouter(prefix='/panchangam')
v1_router = APIRouter(prefix='/api/v1/panchangam')


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


@v1_router.get('/')
def panchangam_v1(
    params: Annotated[GetPanchangamParams, Query()],
    service: Annotated[PanchangamService, Depends(_get_service)],
):
    try:
        parsed_date = datetime.strptime(str(params.date_str), "%Y-%m-%d").date()
    except ValueError:
        return {'error': 'Invalid Date format. Use YYYY-MM-DD'}, 400

    data = service.get_by_date(parsed_date)
    return CompactPanchangamData.from_panchangam_data(data)


@v1_router.get('/monthly')
def panchangam_v1_monthly(
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


@router.get('/thithi')
def thithi_reference():
    return [t.to_dict() for t in Thithi]


@router.get('/nakshatra')
def nakshatra_reference():
    return [n.to_dict() for n in Nakshatra]


@router.get('/masa')
def masa_reference():
    return [m.to_dict() for m in MalayalamMasa]


@router.get('/events')
def events_reference():
    return [
        {"id": e.id.value, "name": e.name, "description": e.description}
        for e in EVENT_DEFINITIONS_BY_ID.values()
    ]
