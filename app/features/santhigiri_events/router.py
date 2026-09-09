"""
Write endpoints for the editable Santhigiri event definitions.

Co-located with the read-only ``GET /panchangam/events`` list (defined in
``features/panchangam/router.py``) on the same collection URI, mounted under
``/api/v1``:

* ``POST   /api/v1/panchangam/events``                       — create an event  (admin)
* ``GET    /api/v1/panchangam/events/{event_id}``             — fetch one event's full definition  (public)
* ``PUT    /api/v1/panchangam/events/{event_id}``             — partial-update an event  (admin)
* ``DELETE /api/v1/panchangam/events/{event_id}``             — delete an event  (admin)
* ``POST   /api/v1/panchangam/events/{event_id}/occurrences`` — start a background job (re)generating one event's occurrence dates over a year range  (admin)
* ``POST   /api/v1/panchangam/events/generate``               — start a background job (re)generating every event's occurrence dates over a year range  (admin)

Authorization mirrors the rest of the API: reading an event definition is
public (the anonymous principal is allowed, any supplied token is still
validated), while every mutation edits the ashram's authoritative event data
and so requires the ``admin`` role. Handlers stay thin: parse the body, delegate
to ``SanthigiriEventService``, and translate its domain errors into HTTP status
codes.

Both occurrence-generation endpoints take the same ``{start_year, end_year}``
body (``SanthigiriEventsGenerateRequest``, an inclusive range) and — like
``POST /panchangam/generate`` (``features/panchangam/generation_router.py``) —
return immediately with a ``GenerationJobStarted`` (202) and run the actual
computation in a background task, detached from the request. This is what
lets a wide range (one event scanning every day of a year, sometimes with a
live Pournami check; the all-events endpoint doing that once per event
definition) keep running to completion even if the admin who started it
closes the tab. Poll ``GET /api/v1/generation-jobs/{job_id}`` (or
``GET /api/v1/generation-jobs/active`` if the id was lost) for progress and
the final result — see ``features/generation_jobs/``. A ``generation_job``
row with ``status="running"`` is a cross-instance lock shared with the
panchangam-generate endpoint: only one generation run of any kind can be in
flight at a time, even across multiple API instances sharing the same
database, so a second call while one is running gets ``409 Conflict``.
"""
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, status
from sqlmodel import Session

from app.api.deps import (
    SessionDep,
    get_app_setting_repository,
    get_current_principal,
    get_etag_repository,
    get_generation_job_repository,
    get_panchangam_repository,
    get_panchangam_service_for_etag_refresh,
    get_reference_repository,
    get_santhigiri_event_repository,
    get_santhigiri_event_service,
    get_settings_service,
    get_unit_of_work,
    require_role,
    Principal,
)
from app.features.generation_jobs.ports import JobAlreadyRunningException
from app.features.generation_jobs.schemas import GenerationJobStarted
from app.features.generation_jobs.service import run_generation_job
from app.features.santhigiri_events.ports import EventNotFoundException
from app.features.santhigiri_events.schemas import (
    SanthigiriEventCreate,
    SanthigiriEventDetail,
    SanthigiriEventsGenerateRequest,
    SanthigiriEventUpdate,
)
from app.features.santhigiri_events.service import (
    EventAlreadyExistsException,
    InvalidEventReferenceException,
    SanthigiriEventService,
    YearSpanTooLargeException,
)
from app.utils.roles import Role

router = APIRouter(prefix="/panchangam/events", tags=["santhigiri-events"])

ServiceDep = Annotated[SanthigiriEventService, Depends(get_santhigiri_event_service)]

SINGLE_EVENT_JOB_TYPE = "event_occurrences"
ALL_EVENTS_JOB_TYPE = "event_occurrences_all"


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


# ── Background occurrence generation ──────────────────────────────────────────

def _build_event_service(session: Session) -> SanthigiriEventService:
    panchangam_repository = get_panchangam_repository(session)
    settings_service = get_settings_service(
        get_app_setting_repository(session), get_unit_of_work(session)
    )
    return SanthigiriEventService(
        reference_repository=get_reference_repository(session),
        event_repository=get_santhigiri_event_repository(session),
        etag_repository=get_etag_repository(session),
        panchangam_repo=panchangam_repository,
        settings=settings_service,
        panchangam_service_for_etag_refresh=get_panchangam_service_for_etag_refresh(
            panchangam_repository
        ),
        unit_of_work=get_unit_of_work(session),
    )


def _start_job(
    request_session: Session,
    job_type: str,
    params: dict,
    principal: Principal,
    start_year: int,
    end_year: int,
    event_id: str | None = None,
) -> tuple[Session, SanthigiriEventService, GenerationJobStarted]:
    """Open a fresh session bound to the SAME engine as *request_session*
    (never *request_session* itself, which FastAPI tears down once this
    response finishes sending), run every cheap pre-check that doesn't need
    a full year's data (event existence, year span), and insert the job row
    — in that order, so a ``404``/``422`` never leaves a ``"running"`` job
    row behind holding the lock. Everything that DOES need a full year's
    data (incomplete-year, unsupported condition, computation errors) is
    still only discoverable once the background job actually runs — it
    surfaces as the job's ``failed`` status/``error``, not an HTTP error
    here. Raises ``HTTPException`` (404 for an unknown *event_id*, 422 for
    an oversized span, 409 if another job is already running); the caller
    owns closing the session on any failure path."""
    session = Session(request_session.get_bind())
    try:
        service = _build_event_service(session)
        if event_id is not None:
            try:
                service.event_repository.get_event_by_id(event_id)
            except EventNotFoundException:
                raise HTTPException(
                    status.HTTP_404_NOT_FOUND, detail=f"Event '{event_id}' not found."
                )
        try:
            service.validate_year_span(start_year, end_year)
        except YearSpanTooLargeException as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

        job_repository = get_generation_job_repository(session)
        try:
            job = job_repository.start(job_type, params, principal.username)
            session.commit()
        except JobAlreadyRunningException:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail="A data-generation job is already running. Wait for it to finish.",
            )
    except Exception:
        session.close()
        raise
    return session, service, GenerationJobStarted(
        job_id=job.id, job_type=job.job_type, status=job.status
    )


async def _run_and_close(job_id: str, session: Session, events) -> None:
    try:
        job_repository = get_generation_job_repository(session)
        await run_generation_job(job_id, events, job_repository, get_unit_of_work(session))
    finally:
        session.close()


@router.post(
    "/{event_id}/occurrences",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=GenerationJobStarted,
    dependencies=[Depends(require_role(Role.ADMIN))],
)
def generate_event_occurrences(
    event_id: str,
    payload: SanthigiriEventsGenerateRequest,
    principal: Annotated[Principal, Depends(get_current_principal)],
    background_tasks: BackgroundTasks,
    request_session: SessionDep,
) -> GenerationJobStarted:
    """Start a background job (re)computing *event_id*'s occurrence dates
    across ``[payload.start_year, payload.end_year]`` from the DB's
    panchangam data, replacing whatever was stored for that event in each of
    those years. Poll ``GET /api/v1/generation-jobs/{job_id}`` for progress."""
    params = {"event_id": event_id, **payload.model_dump(mode="json")}
    session, service, started = _start_job(
        request_session,
        SINGLE_EVENT_JOB_TYPE,
        params,
        principal,
        payload.start_year,
        payload.end_year,
        event_id=event_id,
    )
    events = service.generate_occurrences_streaming(
        event_id, payload.start_year, payload.end_year
    )
    background_tasks.add_task(_run_and_close, started.job_id, session, events)
    return started


@router.post(
    "/generate",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=GenerationJobStarted,
    dependencies=[Depends(require_role(Role.ADMIN))],
)
def generate_all_event_occurrences(
    payload: SanthigiriEventsGenerateRequest,
    principal: Annotated[Principal, Depends(get_current_principal)],
    background_tasks: BackgroundTasks,
    request_session: SessionDep,
) -> GenerationJobStarted:
    """Start a background job (re)computing every event definition's
    occurrence dates across ``[payload.start_year, payload.end_year]``. Poll
    ``GET /api/v1/generation-jobs/{job_id}`` for progress."""
    session, service, started = _start_job(
        request_session,
        ALL_EVENTS_JOB_TYPE,
        payload.model_dump(mode="json"),
        principal,
        payload.start_year,
        payload.end_year,
    )
    events = service.generate_all_occurrences_streaming(
        payload.start_year, payload.end_year
    )
    background_tasks.add_task(_run_and_close, started.job_id, session, events)
    return started
