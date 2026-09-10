"""
Write endpoints for the editable Santhigiri event definitions.

Co-located with the read-only ``GET /panchangam/events`` list (defined in
``features/panchangam/router.py``) on the same collection URI, mounted under
``/api/v1``:

* ``POST   /api/v1/panchangam/events``                            — create an event  (admin)
* ``GET    /api/v1/panchangam/events/{event_id}``                  — fetch one event's full definition  (public)
* ``PUT    /api/v1/panchangam/events/{event_id}``                  — partial-update an event  (admin)
* ``DELETE /api/v1/panchangam/events/{event_id}``                  — delete an event  (admin)
* ``POST   /api/v1/panchangam/events/{event_id}/occurrences``      — (re)generate an event's occurrence dates over a year range  (admin)
* ``POST   /api/v1/panchangam/events/{event_id}/occurrences/stream`` — same, streamed one line per year  (admin)
* ``POST   /api/v1/panchangam/events/generate``                    — (re)generate every event's occurrence dates over a year range, streamed  (admin)

Authorization mirrors the rest of the API: reading an event definition is
public (the anonymous principal is allowed, any supplied token is still
validated), while every mutation edits the ashram's authoritative event data
and so requires the ``admin`` role. Handlers stay thin: parse the body, delegate
to ``SanthigiriEventService``, and translate its domain errors into HTTP status
codes.

All three occurrence-generation endpoints take the same ``{start_year, end_year}``
body (``SanthigiriEventsGenerateRequest``, an inclusive range). Plain
``.../{event_id}/occurrences`` replaces occurrences for one event across
every year in the range and returns a single JSON object keyed by year — fine
for a small range, but a wide one can scan a lot of dates (occasionally with
live Pournami checks) before any response is sent. ``.../{event_id}/occurrences/stream``
computes the same thing but streams newline-delimited JSON (NDJSON): one
``SanthigiriEventGenerateProgress`` line per year, then a final
``SanthigiriEventGenerateResult`` line (or a ``SanthigiriEventsGenerateError``
line if the run fails, e.g. mid-range). ``.../generate`` covers every event
definition the same way, one ``SanthigiriEventsGenerateProgress`` line per
``(year, event)`` pair, then a final ``SanthigiriEventsGenerateResult`` line
(or a ``SanthigiriEventsGenerateError`` line if the run fails before any
event-level result exists) — mirrors ``POST /panchangam/generate``
(``features/panchangam/generation_router.py``). See ``features/santhigiri_events/schemas.py``
for all the line shapes. The request-scoped session is captured into the
closure and used for the whole stream — FastAPI keeps a ``yield``-based
dependency open until the response finishes sending.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from starlette.responses import StreamingResponse

from app.api.deps import get_santhigiri_event_service, require_role
from app.features.santhigiri_events.ports import EventNotFoundException
from app.features.santhigiri_events.schemas import (
    SanthigiriEventCreate,
    SanthigiriEventDetail,
    SanthigiriEventOccurrences,
    SanthigiriEventsGenerateError,
    SanthigiriEventsGenerateRequest,
    SanthigiriEventUpdate,
)
from app.features.santhigiri_events.service import (
    EventAlreadyExistsException,
    IncompleteYearDataException,
    InvalidEventReferenceException,
    OccurrenceComputationError,
    SanthigiriEventService,
    UnsupportedEventCondition,
    YearSpanTooLargeException,
)
from app.utils.roles import Role

router = APIRouter(prefix="/panchangam/events", tags=["santhigiri-events"])

ServiceDep = Annotated[SanthigiriEventService, Depends(get_santhigiri_event_service)]


@router.post(
    "",
    response_model=SanthigiriEventDetail,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role(Role.ADMIN))],
)
def create_event(payload: SanthigiriEventCreate, service: ServiceDep) -> SanthigiriEventDetail:
    try:
        return service.create_event(payload)
    except EventAlreadyExistsException:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"Event '{payload.id}' already exists.",
        )
    except InvalidEventReferenceException as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get(
    "/{event_id}",
    response_model=SanthigiriEventDetail,
    dependencies=[Depends(require_role(Role.ANONYMOUS))],
)
def get_event(event_id: str, service: ServiceDep) -> SanthigiriEventDetail:
    try:
        return service.get_event_by_id(event_id)
    except EventNotFoundException:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=f"Event '{event_id}' not found."
        )


@router.put(
    "/{event_id}",
    response_model=SanthigiriEventDetail,
    dependencies=[Depends(require_role(Role.ADMIN))],
)
def update_event(
    event_id: str, payload: SanthigiriEventUpdate, service: ServiceDep
) -> SanthigiriEventDetail:
    try:
        return service.update(event_id, payload)
    except EventNotFoundException:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=f"Event '{event_id}' not found."
        )
    except InvalidEventReferenceException as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.delete(
    "/{event_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_role(Role.ADMIN))],
)
def delete_event(event_id: str, service: ServiceDep) -> Response:
    try:
        service.delete(event_id)
    except EventNotFoundException:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=f"Event '{event_id}' not found."
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{event_id}/occurrences",
    response_model=SanthigiriEventOccurrences,
    dependencies=[Depends(require_role(Role.ADMIN))],
)
def generate_event_occurrences(
    event_id: str, payload: SanthigiriEventsGenerateRequest, service: ServiceDep
) -> SanthigiriEventOccurrences:
    """(Re)compute *event_id*'s occurrence dates across
    ``[payload.start_year, payload.end_year]`` from the DB's panchangam data
    and replace whatever was stored for that event in each of those years."""
    try:
        occurrences = service.generate_occurrences(
            event_id, payload.start_year, payload.end_year
        )
    except EventNotFoundException:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=f"Event '{event_id}' not found."
        )
    except IncompleteYearDataException as exc:
        year = exc.args[0]
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Panchangam data for {year} is not fully seeded.",
        )
    except (UnsupportedEventCondition, OccurrenceComputationError, YearSpanTooLargeException) as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return SanthigiriEventOccurrences(
        event_id=event_id,
        start_year=payload.start_year,
        end_year=payload.end_year,
        occurrences=occurrences,
    )


@router.post(
    "/{event_id}/occurrences/stream",
    dependencies=[Depends(require_role(Role.ADMIN))],
)
async def generate_event_occurrences_streaming(
    event_id: str, payload: SanthigiriEventsGenerateRequest, service: ServiceDep
) -> StreamingResponse:
    """Streaming sibling of ``POST /{event_id}/occurrences``: (re)compute
    *event_id*'s occurrence dates across ``[payload.start_year, payload.end_year]``,
    streaming a progress line per year for ranges that scan a lot of dates."""
    # Validated before the stream opens so an oversized range gets a real 422
    # instead of a 200 with an NDJSON error line — once StreamingResponse
    # starts, the status code can no longer change.
    try:
        service.validate_year_span(payload.start_year, payload.end_year)
    except YearSpanTooLargeException as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    async def _stream():
        try:
            async for event in service.generate_occurrences_streaming(
                event_id, payload.start_year, payload.end_year
            ):
                yield event.model_dump_json() + "\n"
        except EventNotFoundException:
            service.unit_of_work.rollback()
            yield SanthigiriEventsGenerateError(
                detail=f"Event '{event_id}' not found."
            ).model_dump_json() + "\n"
        except IncompleteYearDataException as exc:
            service.unit_of_work.rollback()
            year = exc.args[0]
            yield SanthigiriEventsGenerateError(
                detail=f"Panchangam data for {year} is not fully seeded."
            ).model_dump_json() + "\n"
        except (UnsupportedEventCondition, OccurrenceComputationError) as exc:
            service.unit_of_work.rollback()
            yield SanthigiriEventsGenerateError(detail=str(exc)).model_dump_json() + "\n"
        except Exception as exc:
            service.unit_of_work.rollback()
            yield SanthigiriEventsGenerateError(detail=str(exc)).model_dump_json() + "\n"

    return StreamingResponse(_stream(), media_type="application/x-ndjson")


@router.post(
    "/generate",
    dependencies=[Depends(require_role(Role.ADMIN))],
)
async def generate_all_event_occurrences(
    payload: SanthigiriEventsGenerateRequest, service: ServiceDep
) -> StreamingResponse:
    """(Re)compute every event definition's occurrence dates across
    ``[payload.start_year, payload.end_year]`` from the DB's panchangam data,
    streaming a progress line per (year, event) pair."""
    # Validated before the stream opens so an oversized range gets a real 422
    # instead of a 200 with an NDJSON error line — once StreamingResponse
    # starts, the status code can no longer change.
    try:
        service.validate_year_span(payload.start_year, payload.end_year)
    except YearSpanTooLargeException as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    async def _stream():
        try:
            async for event in service.generate_all_occurrences_streaming(
                payload.start_year, payload.end_year
            ):
                yield event.model_dump_json() + "\n"
        except IncompleteYearDataException as exc:
            service.unit_of_work.rollback()
            year = exc.args[0]
            yield SanthigiriEventsGenerateError(
                detail=f"Panchangam data for {year} is not fully seeded."
            ).model_dump_json() + "\n"
        except Exception as exc:
            service.unit_of_work.rollback()
            yield SanthigiriEventsGenerateError(detail=str(exc)).model_dump_json() + "\n"

    return StreamingResponse(_stream(), media_type="application/x-ndjson")
