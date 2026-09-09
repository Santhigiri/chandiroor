"""
Read-only endpoints for polling background data-generation jobs, mounted
under ``/api/v1``:

* ``GET /api/v1/generation-jobs/active``    — the currently running job, if any
* ``GET /api/v1/generation-jobs/{job_id}``  — one job's status/progress/result

A job is started by ``POST /api/v1/panchangam/generate``,
``POST /api/v1/panchangam/events/{event_id}/occurrences``, or
``POST /api/v1/panchangam/events/generate`` (see their routers) — each
returns a ``GenerationJobStarted`` (202) with the new job's id and continues
the run in a background task. ``/active`` exists so a client that navigated
away or reloaded mid-run (losing the job id) can find it again and keep
showing progress; ``/{job_id}`` is the steady-state polling endpoint.

Gated at the ``admin`` role, same as the endpoints that start a job — this is
internal ops visibility, not ashram-facing reference data.
"""
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_generation_job_repository, require_role
from app.features.generation_jobs.ports import (
    GenerationJobRepositoryPort,
    JobNotFoundException,
)
from app.features.generation_jobs.schemas import GenerationJobStatus
from app.utils.roles import Role

router = APIRouter(
    prefix="/generation-jobs",
    tags=["generation-jobs"],
    dependencies=[Depends(require_role(Role.ADMIN))],
)

RepositoryDep = Annotated[
    GenerationJobRepositoryPort, Depends(get_generation_job_repository)
]


@router.get("/active", response_model=Optional[GenerationJobStatus])
def get_active_job(repository: RepositoryDep) -> Optional[GenerationJobStatus]:
    job = repository.get_active()
    return GenerationJobStatus(**job.__dict__) if job else None


@router.get("/{job_id}", response_model=GenerationJobStatus)
def get_job(job_id: str, repository: RepositoryDep) -> GenerationJobStatus:
    try:
        job = repository.get(job_id)
    except JobNotFoundException:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=f"Generation job '{job_id}' not found."
        )
    return GenerationJobStatus(**job.__dict__)
