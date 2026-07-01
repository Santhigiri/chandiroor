from typing import Annotated
from fastapi import APIRouter, Depends, Query, Request, Response
from datetime import datetime

from sqlmodel import Session

from db.database import get_session
from db.repository import PanchangamRepository
from schemas.compact_panchangam_data import CompactPanchangamData
from schemas.GetMonthlyPanchangamParams import GetMonthlyPanchangamParams
from schemas.GetYearlyPanchangamParams import GetYearlyPanchangamParams
from schemas.GetDayPanchangamParams import GetPanchangamParams
from services.etag_service import (
    build_year_payload,
    conditional_json_response,
    year_key,
)
from services.panchangam_service import PanchangamService


router = APIRouter(prefix='/panchangam')


def _get_service(session: Annotated[Session, Depends(get_session)]) -> PanchangamService:
    return PanchangamService(PanchangamRepository(session))


@router.get('/day')
def panchangam(
    params: Annotated[GetPanchangamParams, Query()],
    service: Annotated[PanchangamService, Depends(_get_service)],
):
    try:
        parsed_date = datetime.strptime(str(params.date_str), "%Y-%m-%d").date()
    except ValueError:
        return {'error': 'Invalid Date format. Use YYYY-MM-DD'}, 400

    data = service.get_by_date(parsed_date)
    return CompactPanchangamData.from_panchangam_data(data)


@router.get('/month')
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
