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
from utils.thithi import Thithi


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


@router.get('/v2')
def panchangam_v2(
    params: Annotated[GetPanchangamParams, Query()],
    service: Annotated[PanchangamService, Depends(_get_service)],
):
    try:
        parsed_date = datetime.strptime(str(params.date_str), "%Y-%m-%d").date()
    except ValueError:
        return {'error': 'Invalid Date format. Use YYYY-MM-DD'}, 400

    data = service.get_by_date(parsed_date)
    return CompactPanchangamData.from_panchangam_data(data)


@router.get('/v2/monthly')
def panchangam_v2_monthly(
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
