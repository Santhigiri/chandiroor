from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from datetime import datetime

from api.deps import get_location, get_service, require_role
from schemas.GetMonthlyPanchangamParams import GetMonthlyPanchangamParams
from schemas.GetDayPanchangamParams import GetPanchangamParams
from services.panchangam_service import PanchangamService, YearOutOfRange
from utils.location import Location
from utils.roles import Role


# Public data router — validates any supplied bearer token but allows anonymous
# access (see api/routes/v1/panchangam.py for the rationale).
router = APIRouter(
    prefix='/panchangam',
    dependencies=[Depends(require_role(Role.ANONYMOUS))],
)


@router.get('/')
def panchangam(
    params: Annotated[GetPanchangamParams, Query()],
    service: Annotated[PanchangamService, Depends(get_service)],
    location: Annotated[Location, Depends(get_location)],
):
    try:
        parsed_date = datetime.strptime(str(params.date_str), "%Y-%m-%d").date()
    except ValueError:
        return {'error': 'Invalid Date format. Use YYYY-MM-DD'}, 400

    return service.get_by_date(parsed_date, location)


@router.get('/monthly')
def panchangam_monthly(
    params: Annotated[GetMonthlyPanchangamParams, Query()],
    service: Annotated[PanchangamService, Depends(get_service)],
    location: Annotated[Location, Depends(get_location)],
):
    try:
        return service.get_by_month(
            year=params.year,
            month=params.month,
            location=location,
        )
    except YearOutOfRange as exc:
        raise HTTPException(status_code=422, detail=str(exc))


