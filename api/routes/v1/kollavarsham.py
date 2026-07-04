"""
Admin write endpoints for the editable Kollavarsham (Malayalam-calendar) data of
a panchangam day, mounted under ``/api/v1``:

* ``POST   /api/v1/panchangam/kollavarsham``          — create a record  (admin)
* ``GET    /api/v1/panchangam/kollavarsham/{date}``   — fetch one date's record  (public)
* ``PUT    /api/v1/panchangam/kollavarsham/{date}``   — partial-update a record  (admin)
* ``DELETE /api/v1/panchangam/kollavarsham/{date}``   — delete a record  (admin)

Authorization mirrors the rest of the API: reading Kollavarsham data is public
(the anonymous principal is allowed, any supplied token is still validated),
while every mutation edits the ashram's authoritative calendar data and so
requires the ``admin`` role.

Because a panchangam day is invalid without its Kollavarsham child, ``DELETE``
removes the whole panchangam day for that date (its children cascade); the date
then falls back to live computation. Handlers stay thin: parse the path/body,
delegate to ``KollavarshamService``, and translate its domain errors into HTTP
status codes.
"""
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
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
    response_model=KollavarshamDetail,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role(Role.ADMIN))],
)
def create_kollavarsham(
    payload: KollavarshamCreate,
    service: Annotated[KollavarshamService, Depends(_get_service)],
) -> KollavarshamDetail:
    try:
        row = service.create(payload)
    except KollavarshamAlreadyExists:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"Kollavarsham data for '{payload.date}' already exists.",
        )
    except NoPanchangamDay:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f"No panchangam day exists for '{payload.date}'.",
        )
    return KollavarshamDetail.from_row(row)


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
    "/{day}",
    response_model=KollavarshamDetail,
    dependencies=[Depends(require_role(Role.ADMIN))],
)
def update_kollavarsham(
    day: date,
    payload: KollavarshamUpdate,
    service: Annotated[KollavarshamService, Depends(_get_service)],
) -> KollavarshamDetail:
    try:
        row = service.update(day, payload)
    except KollavarshamNotFound:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=f"Kollavarsham data for '{day}' not found.",
        )
    return KollavarshamDetail.from_row(row)


@router.delete(
    "/{day}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_role(Role.ADMIN))],
)
def delete_kollavarsham(
    day: date,
    service: Annotated[KollavarshamService, Depends(_get_service)],
) -> Response:
    try:
        service.delete(day)
    except KollavarshamNotFound:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=f"Kollavarsham data for '{day}' not found.",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
