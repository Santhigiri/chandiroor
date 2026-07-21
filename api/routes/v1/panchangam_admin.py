"""
Admin write endpoints for a single day's Panchangam data.

Mounted under ``/api/v1`` alongside the read-only ``api/routes/v1/panchangam.py``
router (both share the ``/panchangam`` prefix, which FastAPI allows):

* ``POST  /api/v1/panchangam/day/generate`` — compute a day astronomically and
  persist it, overwriting any existing row (fill a gap or force a recompute).
* ``PATCH /api/v1/panchangam/day``          — partial-override an existing day's
  core values (thithi, nakshatra, nazhika, sunrise/sunset).

Both mutate the ashram's authoritative data, so the whole router is gated at the
``admin`` role. Handlers stay thin: parse the query params / body, delegate to
``PanchangamAdminService``, and translate its domain errors into HTTP status
codes. The response is the full ``PanchangamData`` that was persisted, so an admin
sees exactly what landed in the DB.
"""
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session

from api.deps import get_location, require_role
from db.database import get_session
from schemas.panchangam_data import PanchangamData
from schemas.panchangam_edit import PanchangamDayUpdate
from services.panchangam_admin_service import (
    PanchangamAdminService,
    PanchangamDayNotFound,
)
from utils.location import Location
from utils.roles import Role

router = APIRouter(
    prefix="/panchangam",
    tags=["panchangam-admin"],
    dependencies=[Depends(require_role(Role.ADMIN))],
)


def _get_admin_service(
    session: Annotated[Session, Depends(get_session)],
) -> PanchangamAdminService:
    return PanchangamAdminService(session)


@router.post(
    "/day/generate",
    response_model=PanchangamData,
    status_code=status.HTTP_201_CREATED,
)
def generate_day(
    day: Annotated[date, Query()],
    service: Annotated[PanchangamAdminService, Depends(_get_admin_service)],
    location: Annotated[Location, Depends(get_location)],
) -> PanchangamData:
    return service.generate(day, location)


@router.patch(
    "/day",
    response_model=PanchangamData,
)
def edit_day(
    payload: PanchangamDayUpdate,
    day: Annotated[date, Query()],
    service: Annotated[PanchangamAdminService, Depends(_get_admin_service)],
    location: Annotated[Location, Depends(get_location)],
) -> PanchangamData:
    try:
        return service.edit(day, location, payload)
    except PanchangamDayNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc))
