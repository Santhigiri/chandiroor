from typing import Annotated
from fastapi import APIRouter, Depends, Query
from datetime import datetime

from sqlmodel import Session

from db.database import get_session
from db.repository import PanchangamRepository
from schemas.GetMonthlyPanchangamParams import GetMonthlyPanchangamParams
from schemas.GetDayPanchangamParams import GetPanchangamParams
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
