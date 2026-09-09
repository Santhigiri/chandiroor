"""
Write endpoint for (re)generating Panchangam data, mounted under ``/api/v1``:

* ``POST /api/v1/panchangam/generate`` — start a background job that computes a
  date range from the astronomy code and writes it to the DB, overwriting any
  existing rows                                                            (admin)

Authorization mirrors the rest of the API: generating overwrites the ashram's
authoritative calendar data, so it requires the ``admin`` role. The handler stays
thin: parse, delegate to ``PanchangamGenerationService``. Invalid ranges are
rejected by the request schema (422) before a job is ever created.

The run itself happens in a FastAPI ``BackgroundTasks`` callback, detached from
this request — it keeps going even if the client that started it disconnects,
navigates away, or the frontend is simply never reopened. The response returns
immediately (202) with a job id; poll ``GET /api/v1/generation-jobs/{job_id}``
(or ``GET /api/v1/generation-jobs/active`` if the id was lost) for progress and
the final result. A ``generation_job`` row with ``status="running"`` acts as a
cross-instance lock — see ``db/models/generation_job.py`` — so only one
generation run (of any kind: this endpoint or the Santhigiri event-occurrence
endpoints in ``features/santhigiri_events/router.py``) can be in flight at a
time, even across multiple API instances sharing the same database. A second
call while one is running gets ``409 Conflict``.

The background run needs its own DB session — the request-scoped one is torn
down once the response finishes, which for a long generation run could happen
before the work is done. ``_build_generation_service`` re-wires a
``PanchangamGenerationService`` from a freshly opened session, exactly like
``api/deps.py::get_panchangam_generation_service`` does for the request-scoped
one, and ``_run_and_close`` makes sure that session is closed once the run
(succeeded or failed) is done.
"""
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlmodel import Session

from app.api.deps import (
    SessionDep,
    get_app_setting_repository,
    get_current_principal,
    get_etag_repository,
    get_generation_job_repository,
    get_location,
    get_panchangam_repository,
    get_panchangam_service_for_etag_refresh,
    get_reference_repository,
    get_settings_service,
    get_unit_of_work,
    require_role,
    Principal,
)
from app.features.generation_jobs.ports import JobAlreadyRunningException
from app.features.generation_jobs.schemas import GenerationJobStarted
from app.features.generation_jobs.service import run_generation_job
from app.features.panchangam.generation_service import PanchangamGenerationService, SpanTooLarge
from app.features.panchangam.schemas.panchangam_generation import PanchangamGenerateRequest
from app.utils.location import Location
from app.utils.roles import Role

router = APIRouter(prefix="/panchangam", tags=["panchangam-generation"])

JOB_TYPE = "panchangam_generate"


def _build_generation_service(session: Session) -> PanchangamGenerationService:
    panchangam_repository = get_panchangam_repository(session)
    settings_service = get_settings_service(
        get_app_setting_repository(session), get_unit_of_work(session)
    )
    return PanchangamGenerationService(
        reference_repository=get_reference_repository(session),
        repository=panchangam_repository,
        settings=settings_service,
        etag_repository=get_etag_repository(session),
        panchangam_service_for_etag_refresh=get_panchangam_service_for_etag_refresh(
            panchangam_repository
        ),
        unit_of_work=get_unit_of_work(session),
    )


async def _run_and_close(job_id: str, session: Session, service: PanchangamGenerationService,
                          payload: PanchangamGenerateRequest, location: Location) -> None:
    try:
        events = service.generate_streaming(payload, location)
        job_repository = get_generation_job_repository(session)
        await run_generation_job(job_id, events, job_repository, get_unit_of_work(session))
    finally:
        session.close()


@router.post(
    "/generate",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=GenerationJobStarted,
    dependencies=[Depends(require_role(Role.ADMIN))],
)
def generate_panchangam(
    payload: PanchangamGenerateRequest,
    location: Annotated[Location, Depends(get_location)],
    principal: Annotated[Principal, Depends(get_current_principal)],
    background_tasks: BackgroundTasks,
    request_session: SessionDep,
) -> GenerationJobStarted:
    # A brand-new Session bound to the SAME engine as the request-scoped one
    # (never the request-scoped Session itself, which FastAPI tears down once
    # this response finishes sending — before a long generation run is done).
    session = Session(request_session.get_bind())
    try:
        service = _build_generation_service(session)
        try:
            service.validate_span(payload)
        except SpanTooLarge as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

        job_repository = get_generation_job_repository(session)
        try:
            job = job_repository.start(
                JOB_TYPE,
                payload.model_dump(mode="json"),
                principal.username,
            )
            session.commit()
        except JobAlreadyRunningException:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail="A data-generation job is already running. Wait for it to finish.",
            )
    except Exception:
        session.close()
        raise

    background_tasks.add_task(_run_and_close, job.id, session, service, payload, location)
    return GenerationJobStarted(job_id=job.id, job_type=job.job_type, status=job.status)
