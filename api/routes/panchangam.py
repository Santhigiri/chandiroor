from typing import Annotated
from fastapi import APIRouter, Depends, Query
from datetime import datetime

from api.deps import get_service
from schemas.get_monthly_panchangam_params import GetMonthlyPanchangamParams
from schemas.get_day_panchangam_params import GetPanchangamParams
from services.panchangam_service import PanchangamService


router = APIRouter(prefix='/panchangam')


@router.get('/')
def panchangam(
    params: Annotated[GetPanchangamParams, Query()],
    service: Annotated[PanchangamService, Depends(get_service)],
):
    try:
        parsed_date = datetime.strptime(str(params.date_str), "%Y-%m-%d").date()
    except ValueError:
        return {'error': 'Invalid Date format. Use YYYY-MM-DD'}, 400

    return service.get_by_date(parsed_date)


@router.get('/monthly')
def panchangam_monthly(
    params: Annotated[GetMonthlyPanchangamParams, Query()],
    service: Annotated[PanchangamService, Depends(get_service)],
):
    return service.get_by_month(
        year=params.year,
        month=params.month,
    )


