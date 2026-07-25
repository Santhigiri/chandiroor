"""
Write endpoint for (re)generating Panchangam data, mounted under ``/api/v1``:

* ``POST /api/v1/panchangam/generate`` — compute a date range from the astronomy
  code and write it to the DB, overwriting any existing rows                (admin)

Authorization mirrors the rest of the API: generating overwrites the ashram's
authoritative calendar data, so it requires the ``admin`` role. The handler stays
thin: parse, delegate to ``PanchangamGenerationService``. Invalid ranges are
rejected by the request schema (422); there are no domain errors to translate,
since the panchangam table is the parent — any date is generatable.
"""
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlmodel import Session

from api.deps import get_location, require_role
from db.database import get_session
from schemas.panchangam_generation import (
    PanchangamGenerateRequest,
    PanchangamGenerateResult,
)
from services.panchangam_generation_service import PanchangamGenerationService
from utils.location import Location
from utils.roles import Role

router = APIRouter(prefix="/panchangam", tags=["panchangam-generation"])


def _get_service(
    session: Annotated[Session, Depends(get_session)],
) -> PanchangamGenerationService:
    return PanchangamGenerationService(session)


@router.post(
    "/generate",
    response_model=PanchangamGenerateResult,
    dependencies=[Depends(require_role(Role.ADMIN))],
)
def generate_panchangam(
    payload: PanchangamGenerateRequest,
    service: Annotated[PanchangamGenerationService, Depends(_get_service)],
    location: Annotated[Location, Depends(get_location)],
) -> PanchangamGenerateResult:
    return service.generate(payload, location)
