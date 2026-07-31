"""
Write (and single-date read) endpoints for the Kollavarsham data, mounted under
``/api/v1``:

* ``POST /api/v1/panchangam/kollavarsham/generate``   — (re)compute a date range  (admin)
* ``GET  /api/v1/panchangam/kollavarsham/{date}``      — read one date's row        (public)
* ``PUT  /api/v1/panchangam/kollavarsham/{date}``      — manual override of one date (admin)

Authorization mirrors the rest of the API: reading is public (the anonymous
principal is allowed, any supplied token is still validated), while every
mutation edits the ashram's authoritative calendar data and so requires the
``admin`` role. Handlers stay thin: parse, delegate to ``KollavarshamService``,
and translate its domain errors into HTTP status codes.
"""
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from api.deps import get_location, require_role
from db.database import get_session
from schemas.kollavarsham import (
    KollavarshamDateRead,
    KollavarshamDateUpdate,
    KollavarshamGenerateRequest,
    KollavarshamGenerateResult,
)
from services.kollavarsham_service import (
    KollavarshamDateNotFound,
    KollavarshamService,
    SpanTooLarge,
    UngeneratableDates,
)
from utils.location import Location
from utils.malayalam_masa import MalayalamMasa
from utils.roles import Role

router = APIRouter(prefix="/panchangam/kollavarsham", tags=["kollavarsham"])


def _get_service(
    session: Annotated[Session, Depends(get_session)],
) -> KollavarshamService:
    return KollavarshamService(session)


def _to_read(row) -> KollavarshamDateRead:
    masa = MalayalamMasa.from_id(row.kv_month)
    return KollavarshamDateRead(
        date=row.date,
        kv_day=row.kv_day,
        kv_month=row.kv_month,
        kv_year=row.kv_year,
        kv_month_name_en=masa.en,
        kv_month_name_ml=masa.ml,
    )


@router.post(
    "/generate",
    response_model=KollavarshamGenerateResult,
    dependencies=[Depends(require_role(Role.ADMIN))],
)
def generate_kollavarsham(
    payload: KollavarshamGenerateRequest,
    service: Annotated[KollavarshamService, Depends(_get_service)],
    location: Annotated[Location, Depends(get_location)],
) -> KollavarshamGenerateResult:
    try:
        return service.generate(payload, location)
    except UngeneratableDates as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "No panchangam row exists for some dates in the range; "
                "seed panchangam data for these dates first.",
                "missing_dates": [d.isoformat() for d in exc.dates],
            },
        )
    except SpanTooLarge as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


@router.get(
    "/{date}",
    response_model=KollavarshamDateRead,
    dependencies=[Depends(require_role(Role.ANONYMOUS))],
)
def get_kollavarsham(
    date: date,
    service: Annotated[KollavarshamService, Depends(_get_service)],
    location: Annotated[Location, Depends(get_location)],
) -> KollavarshamDateRead:
    try:
        row = service.get(date, location)
    except KollavarshamDateNotFound:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=f"No Kollavarsham data for {date.isoformat()}.",
        )
    return _to_read(row)


@router.put(
    "/{date}",
    response_model=KollavarshamDateRead,
    dependencies=[Depends(require_role(Role.ADMIN))],
)
def update_kollavarsham(
    date: date,
    payload: KollavarshamDateUpdate,
    service: Annotated[KollavarshamService, Depends(_get_service)],
    location: Annotated[Location, Depends(get_location)],
) -> KollavarshamDateRead:
    try:
        row = service.update(date, payload, location)
    except KollavarshamDateNotFound:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=f"No Kollavarsham data for {date.isoformat()}.",
        )
    return _to_read(row)
