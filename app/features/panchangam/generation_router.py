"""
Write endpoint for (re)generating Panchangam data, mounted under ``/api/v1``:

* ``POST /api/v1/panchangam/generate`` — recompute a date range from the astronomy
  code and write it to the DB, overwriting any existing rows                (admin)

Authorization mirrors the rest of the API: generating overwrites the ashram's
authoritative calendar data, so it requires the ``admin`` role. The handler stays
thin: parse, delegate to ``PanchangamGenerationService``. Invalid ranges are
rejected by the request schema (422) before a job is ever created.

The response is a live NDJSON stream (``application/x-ndjson``, one JSON object
per line) of ``PanchangamGenerateProgress``/``PanchangamGenerateResult`` lines as
the range is (re)computed — the job's id and type are available immediately via
the ``X-Job-Id``/``X-Job-Type`` response headers, sent before the body starts.
The underlying run is never tied to this particular HTTP connection staying
open: ``ResilientStreamingResponse`` (see ``features/generation_jobs/streaming.py``)
keeps driving it to completion even if the client disconnects, and every event
is persisted into the ``generation_job`` row as it happens (see
``features/generation_jobs/service.py::stream_generation_job``) — so a client
that navigated away, lost the connection, or never reconnects still gets a
finished run. Poll ``GET /api/v1/generation-jobs/{job_id}`` (or
``GET /api/v1/generation-jobs/active`` if the id was lost) to pick progress back
up without the live stream. A ``generation_job`` row with ``status="running"``
also acts as a cross-instance lock — see ``db/models/generation_job.py`` — so
only one generation run (of any kind: this endpoint or the Santhigiri
event-occurrence endpoints in ``features/santhigiri_events/router.py``) can be
in flight at a time, even across multiple API instances sharing the same
database. A second call while one is running gets ``409 Conflict``.

The run needs its own DB session — the request-scoped one may be torn down by
FastAPI before dependency cleanup would otherwise let it survive as long as the
stream does. ``_build_generation_service`` re-wires a
``PanchangamGenerationService`` from a freshly opened session, exactly like
``api/deps.py::get_panchangam_generation_service`` does for the request-scoped
one, and ``_stream_and_close`` makes sure that session is closed once the run
(succeeded or failed) is done.
"""
from typing import Annotated, AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, status
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
from app.features.generation_jobs.service import stream_generation_job
from app.features.generation_jobs.streaming import ResilientStreamingResponse
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


async def _stream_and_close(
    job_id: str,
    session: Session,
    service: PanchangamGenerationService,
    payload: PanchangamGenerateRequest,
    location: Location,
) -> AsyncIterator[str]:
    try:
        events = service.generate_streaming(payload, location)
        job_repository = get_generation_job_repository(session)
        async for line in stream_generation_job(
            job_id, events, job_repository, get_unit_of_work(session)
        ):
            yield line
    finally:
        session.close()


@router.post(
    "/generate",
    dependencies=[Depends(require_role(Role.ADMIN))],
)
def generate_panchangam(
    payload: PanchangamGenerateRequest,
    location: Annotated[Location, Depends(get_location)],
    principal: Annotated[Principal, Depends(get_current_principal)],
    request_session: SessionDep,
) -> ResilientStreamingResponse:
    # A brand-new Session bound to the SAME engine as the request-scoped one
    # (never the request-scoped Session itself, which FastAPI may tear down
    # before this stream — potentially long-running — is done).
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

    return ResilientStreamingResponse(
        _stream_and_close(job.id, session, service, payload, location),
        media_type="application/x-ndjson",
        headers={"X-Job-Id": job.id, "X-Job-Type": job.job_type},
    )
