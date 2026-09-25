"""
v2 Santhigiri event endpoints — the 5 non-streaming, non-.ics endpoints from
``features/santhigiri_events/router.py`` (v1), wrapped in the
``{success, message, data}`` envelope (``app/api/envelope.py``):

* ``POST   /api/v2/panchangam/events``                       — create an event  (admin)
* ``GET    /api/v2/panchangam/events/{event_id}``             — fetch one event's full definition  (public)
* ``PUT    /api/v2/panchangam/events/{event_id}``             — partial-update an event  (admin)
* ``DELETE /api/v2/panchangam/events/{event_id}``             — delete an event  (admin)
* ``POST   /api/v2/panchangam/events/{event_id}/occurrences`` — (re)generate one event's occurrences  (admin)

Deliberately excludes ``calendar.ics`` (a text/calendar response, not JSON) and
the two streaming NDJSON endpoints (``.../occurrences/stream``, ``.../generate``)
— wrapping a per-line NDJSON stream in this envelope would either double-nest
each line inside ``data`` or collapse the progress/result/error type
distinction consumers already switch on; out of scope for this pass.

``DELETE`` diverges from v1's spec-correct ``204 No Content`` (which cannot
carry a body): v2 returns ``200 OK`` with an enveloped ``data: null`` body
instead, so every v2 response — including this one — is uniformly enveloped.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from app.api.deps import get_santhigiri_event_service, require_role
from app.api.envelope import AppHTTPException, ok
from app.features.santhigiri_events.ports import EventNotFoundException
from app.features.santhigiri_events.schemas import (
    SanthigiriEventCreate,
    SanthigiriEventDetail,
    SanthigiriEventOccurrences,
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
from app.schemas.api_response import ApiResponse, MessageCode
from app.utils.roles import Role

router = APIRouter(prefix="/panchangam/events", tags=["santhigiri-events"])

ServiceDep = Annotated[SanthigiriEventService, Depends(get_santhigiri_event_service)]


@router.post(
    "",
    response_model=ApiResponse[SanthigiriEventDetail],
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role(Role.ADMIN))],
)
def create_event_v2(payload: SanthigiriEventCreate, service: ServiceDep) -> JSONResponse:
    try:
        event = service.create_event(payload)
    except EventAlreadyExistsException:
        raise AppHTTPException(
            status.HTTP_409_CONFLICT,
            f"Event '{payload.id}' already exists.",
            MessageCode.EVENT_ALREADY_EXISTS,
        )
    except InvalidEventReferenceException as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return ok(data=event, message=MessageCode.EVENT_CREATED, status_code=status.HTTP_201_CREATED)


@router.get(
    "/{event_id}",
    response_model=ApiResponse[SanthigiriEventDetail],
    dependencies=[Depends(require_role(Role.ANONYMOUS))],
)
def get_event_v2(event_id: str, service: ServiceDep) -> JSONResponse:
    try:
        event = service.get_event_by_id(event_id)
    except EventNotFoundException:
        raise AppHTTPException(
            status.HTTP_404_NOT_FOUND, f"Event '{event_id}' not found.", MessageCode.EVENT_NOT_FOUND
        )
    return ok(data=event, message=MessageCode.EVENT_FETCHED)


@router.put(
    "/{event_id}",
    response_model=ApiResponse[SanthigiriEventDetail],
    dependencies=[Depends(require_role(Role.ADMIN))],
)
def update_event_v2(
    event_id: str, payload: SanthigiriEventUpdate, service: ServiceDep
) -> JSONResponse:
    try:
        event = service.update(event_id, payload)
    except EventNotFoundException:
        raise AppHTTPException(
            status.HTTP_404_NOT_FOUND, f"Event '{event_id}' not found.", MessageCode.EVENT_NOT_FOUND
        )
    except InvalidEventReferenceException as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return ok(data=event, message=MessageCode.EVENT_UPDATED)


@router.delete(
    "/{event_id}",
    response_model=ApiResponse[None],
    dependencies=[Depends(require_role(Role.ADMIN))],
)
def delete_event_v2(event_id: str, service: ServiceDep) -> JSONResponse:
    try:
        service.delete(event_id)
    except EventNotFoundException:
        raise AppHTTPException(
            status.HTTP_404_NOT_FOUND, f"Event '{event_id}' not found.", MessageCode.EVENT_NOT_FOUND
        )
    return ok(data=None, message=MessageCode.EVENT_DELETED)


@router.post(
    "/{event_id}/occurrences",
    response_model=ApiResponse[SanthigiriEventOccurrences],
    dependencies=[Depends(require_role(Role.ADMIN))],
)
def generate_event_occurrences_v2(
    event_id: str, payload: SanthigiriEventsGenerateRequest, service: ServiceDep
) -> JSONResponse:
    try:
        occurrences = service.generate_occurrences(
            event_id, payload.start_year, payload.end_year
        )
    except EventNotFoundException:
        raise AppHTTPException(
            status.HTTP_404_NOT_FOUND, f"Event '{event_id}' not found.", MessageCode.EVENT_NOT_FOUND
        )
    except IncompleteYearDataException as exc:
        year = exc.args[0]
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Panchangam data for {year} is not fully seeded.",
        )
    except (UnsupportedEventCondition, OccurrenceComputationError, YearSpanTooLargeException) as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return ok(
        data=SanthigiriEventOccurrences(
            event_id=event_id,
            start_year=payload.start_year,
            end_year=payload.end_year,
            occurrences=occurrences,
        ),
        message=MessageCode.EVENT_OCCURRENCES_GENERATED,
    )
