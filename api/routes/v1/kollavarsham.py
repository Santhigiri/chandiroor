"""
Admin write endpoints for the editable Kollavarsham (Malayalam-calendar) data of
panchangam days, mounted under ``/api/v1``:

* ``POST /api/v1/panchangam/kollavarsham``        — create records over a date range  (admin)
* ``GET  /api/v1/panchangam/kollavarsham/{date}`` — fetch one date's record  (public)
* ``PUT  /api/v1/panchangam/kollavarsham``        — partial-update records over a date range  (admin)

``POST`` and ``PUT`` are range-oriented: the request body carries a
``start_date`` and an optional ``end_date`` (omit it for a single day) and the
values apply to every date in the inclusive span. There is deliberately **no
delete** — a panchangam day is invalid without its Kollavarsham child, so the
data can be created or edited but never removed here.

Authorization mirrors the rest of the API: reading is public (the anonymous
principal is allowed, any supplied token is still validated), while every
mutation edits the ashram's authoritative calendar data and so requires the
``admin`` role. Handlers stay thin: parse the path/body, delegate to
``KollavarshamService``, and translate its domain errors into HTTP status codes.
"""
from datetime import date
from typing import Annotated, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from api.deps import require_role
from db.database import get_session
from schemas.kollavarsham import (
    KollavarshamCreate,
    KollavarshamDetail,
    KollavarshamUpdate,
)
from services.kollavarsham_service import (
    KollavarshamAlreadyExists,
    KollavarshamNotFound,
    KollavarshamService,
    NoPanchangamDay,
)
from utils.roles import Role

router = APIRouter(prefix="/panchangam/kollavarsham", tags=["kollavarsham"])


def _get_service(
    session: Annotated[Session, Depends(get_session)],
) -> KollavarshamService:
    return KollavarshamService(session)


@router.post(
    "",
    response_model=List[KollavarshamDetail],
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role(Role.ADMIN))],
)
def create_kollavarsham(
    payload: KollavarshamCreate,
    service: Annotated[KollavarshamService, Depends(_get_service)],
) -> List[KollavarshamDetail]:
    try:
        rows = service.create(payload)
    except KollavarshamAlreadyExists as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"Kollavarsham data already exists for: "
            f"{', '.join(str(d) for d in exc.dates)}.",
        )
    except NoPanchangamDay as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f"No panchangam day exists for: "
            f"{', '.join(str(d) for d in exc.dates)}.",
        )
    return [KollavarshamDetail.from_row(r) for r in rows]


@router.get(
    "/{day}",
    response_model=KollavarshamDetail,
    dependencies=[Depends(require_role(Role.ANONYMOUS))],
)
def get_kollavarsham(
    day: date,
    service: Annotated[KollavarshamService, Depends(_get_service)],
) -> KollavarshamDetail:
    try:
        row = service.get(day)
    except KollavarshamNotFound:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=f"Kollavarsham data for '{day}' not found.",
        )
    return KollavarshamDetail.from_row(row)


@router.put(
    "",
    response_model=List[KollavarshamDetail],
    dependencies=[Depends(require_role(Role.ADMIN))],
)
def update_kollavarsham(
    payload: KollavarshamUpdate,
    service: Annotated[KollavarshamService, Depends(_get_service)],
) -> List[KollavarshamDetail]:
    try:
        rows = service.update(payload)
    except KollavarshamNotFound:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail="No Kollavarsham data found in the given date range.",
        )
    return [KollavarshamDetail.from_row(r) for r in rows]
