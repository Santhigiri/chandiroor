"""
Free functions orchestrating a background generation job — not a class-based
service, since (like ``features/etag/service.py``) there is no per-job state
to hold beyond what's already threaded through as parameters. Every
generation endpoint (``panchangam/generation_router.py``,
``santhigiri_events/router.py``) imports this module directly.

The actual generation work (astronomy computation, event-occurrence
resolution) stays entirely inside each feature's own write-path service —
``PanchangamGenerationService.generate_streaming``/
``SanthigiriEventService.generate_occurrences_streaming``/
``generate_all_occurrences_streaming``. Those are async generators that yield
one progress model per unit of work and a final result model, discriminated
by a ``type`` field (``"progress"`` / ``"complete"``) — exactly the shape
``run_generation_job`` below expects. It just drives that generator to
completion, writing each yielded model into the job row instead of streaming
it over HTTP, so the run keeps going even if nothing is left to read the
response.
"""
from __future__ import annotations

from typing import Any, AsyncIterator, Protocol

from app.core.ports.unit_of_work import UnitOfWork
from app.features.generation_jobs.ports import GenerationJobRepositoryPort


class _ProgressOrResult(Protocol):
    type: str

    def model_dump(self, *, mode: str = ...) -> dict: ...


async def run_generation_job(
    job_id: str,
    events: AsyncIterator[_ProgressOrResult],
    job_repository: GenerationJobRepositoryPort,
    unit_of_work: UnitOfWork,
) -> None:
    """Drive *events* to completion, persisting progress/result/failure into
    *job_id*'s row as it goes. Intended to run as a FastAPI ``BackgroundTasks``
    callback, detached from the request that started it — *job_repository*
    and *unit_of_work* must be built from a session opened for this run alone
    (never the request-scoped one, which may already be closed by the time a
    long-running job gets here).

    Never raises: any exception from *events* (including one from the
    underlying generation service) is caught and recorded as the job's
    failure, since there is no request left to propagate it to.
    """
    try:
        async for event in events:
            payload: Any = event.model_dump(mode="json")
            if payload.get("type") == "progress":
                job_repository.update_progress(job_id, payload)
            else:
                job_repository.mark_succeeded(job_id, payload)
            unit_of_work.commit()
    except Exception as exc:
        unit_of_work.rollback()
        job_repository.mark_failed(job_id, str(exc))
        unit_of_work.commit()
