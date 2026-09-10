"""
Write endpoint for (re)generating Panchangam data, mounted under ``/api/v1``:

* ``POST /api/v1/panchangam/generate`` — compute a date range from the astronomy
  code and write it to the DB, overwriting any existing rows                (admin)

Authorization mirrors the rest of the API: generating overwrites the ashram's
authoritative calendar data, so it requires the ``admin`` role. The handler stays
thin: parse, delegate to ``PanchangamGenerationService``. Invalid ranges are
rejected by the request schema (422) before the stream ever starts; there are no
other domain errors to translate, since the panchangam table is the parent — any
date is generatable.

The response is streamed as newline-delimited JSON (NDJSON) rather than a single
JSON object, since a large range can take a while: one ``PanchangamGenerateProgress``
line per day, then a final ``PanchangamGenerateResult`` line (or a
``PanchangamGenerateError`` line if something fails partway through — see
``schemas/panchangam_generation.py`` for the line shapes). The request-scoped
session from ``Depends(get_session)`` is captured into the closure and used for
the whole stream — FastAPI keeps a ``yield``-based dependency open until the
response finishes sending (including a streamed one), so it's still valid for
the duration of the generator.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session
from starlette.responses import StreamingResponse

from app.api.deps import get_location, get_panchangam_generation_service, require_role
from app.db.database import get_session
from app.features.panchangam.generation_service import PanchangamGenerationService, SpanTooLarge
from app.features.panchangam.schemas.panchangam_generation import (
    PanchangamGenerateError,
    PanchangamGenerateRequest,
)
from app.utils.location import Location
from app.utils.roles import Role

router = APIRouter(prefix="/panchangam", tags=["panchangam-generation"])


@router.post(
    "/generate",
    dependencies=[Depends(require_role(Role.ADMIN))],
)
async def generate_panchangam(
    payload: PanchangamGenerateRequest,
    session: Annotated[Session, Depends(get_session)],
    location: Annotated[Location, Depends(get_location)],
    service: Annotated[PanchangamGenerationService, Depends(get_panchangam_generation_service)],
) -> StreamingResponse:
    # Validated before the stream opens so an oversized range gets a real 422
    # instead of a 200 with an NDJSON error line — once StreamingResponse
    # starts, the status code can no longer change.
    try:
        service.validate_span(payload)
    except SpanTooLarge as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    async def _stream():
        try:
            async for event in service.generate_streaming(payload, location):
                yield event.model_dump_json() + "\n"
        except SpanTooLarge as exc:
            # The stream's response already started with a 200 by the time this
            # can be raised (span is only known once generate_streaming starts
            # iterating), so — like every other mid-stream failure — it surfaces
            # as an error line rather than a true 422; clients must check `type`
            # on the last line.
            session.rollback()
            yield PanchangamGenerateError(detail=str(exc)).model_dump_json() + "\n"
        except Exception as exc:
            session.rollback()
            yield PanchangamGenerateError(detail=str(exc)).model_dump_json() + "\n"

    return StreamingResponse(_stream(), media_type="application/x-ndjson")
