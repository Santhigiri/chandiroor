"""
Write endpoints for the editable Santhigiri event definitions.

Co-located with the read-only ``GET /panchangam/events`` list (defined in
``api/routes/v1/panchangam.py``) on the same collection URI, mounted under
``/api/v1``:

* ``POST   /api/v1/panchangam/events``            — create an event  (admin)
* ``GET    /api/v1/panchangam/events/{event_id}`` — fetch one event's full definition  (public)
* ``PUT    /api/v1/panchangam/events/{event_id}`` — partial-update an event  (admin)
* ``DELETE /api/v1/panchangam/events/{event_id}`` — delete an event  (admin)

Authorization mirrors the rest of the API: reading an event definition is
public (the anonymous principal is allowed, any supplied token is still
validated), while every mutation edits the ashram's authoritative event data
and so requires the ``admin`` role. Handlers stay thin: parse the body, delegate
to ``SanthigiriEventService``, and translate its domain errors into HTTP status
codes.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlmodel import Session

from api.deps import require_role
from db.database import get_session
from schemas.santhigiri_event import (
    SanthigiriEventCreate,
    SanthigiriEventDetail,
    SanthigiriEventUpdate,
)
from services.santhigiri_event_service import (
    EventAlreadyExists,
    EventNotFound,
    InvalidEventReference,
    SanthigiriEventService,
)
from utils.roles import Role

router = APIRouter(prefix="/panchangam/events", tags=["santhigiri-events"])


def _get_service(
    session: Annotated[Session, Depends(get_session)],
) -> SanthigiriEventService:
    return SanthigiriEventService(session)


@router.post(
    "",
    response_model=SanthigiriEventDetail,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role(Role.ADMIN))],
)
def create_event(
    payload: SanthigiriEventCreate,
    service: Annotated[SanthigiriEventService, Depends(_get_service)],
) -> SanthigiriEventDetail:
    try:
        row = service.create(payload)
    except EventAlreadyExists:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"Event '{payload.id}' already exists.",
        )
    except InvalidEventReference as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return SanthigiriEventDetail.model_validate(row)


@router.get(
    "/{event_id}",
    response_model=SanthigiriEventDetail,
    dependencies=[Depends(require_role(Role.ANONYMOUS))],
)
def get_event(
    event_id: str,
    service: Annotated[SanthigiriEventService, Depends(_get_service)],
) -> SanthigiriEventDetail:
    try:
        row = service.get(event_id)
    except EventNotFound:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=f"Event '{event_id}' not found."
        )
    return SanthigiriEventDetail.model_validate(row)


@router.put(
    "/{event_id}",
    response_model=SanthigiriEventDetail,
    dependencies=[Depends(require_role(Role.ADMIN))],
)
def update_event(
    event_id: str,
    payload: SanthigiriEventUpdate,
    service: Annotated[SanthigiriEventService, Depends(_get_service)],
) -> SanthigiriEventDetail:
    try:
        row = service.update(event_id, payload)
    except EventNotFound:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=f"Event '{event_id}' not found."
        )
    except InvalidEventReference as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return SanthigiriEventDetail.model_validate(row)


@router.delete(
    "/{event_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_role(Role.ADMIN))],
)
def delete_event(
    event_id: str,
    service: Annotated[SanthigiriEventService, Depends(_get_service)],
) -> Response:
    try:
        service.delete(event_id)
    except EventNotFound:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=f"Event '{event_id}' not found."
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
