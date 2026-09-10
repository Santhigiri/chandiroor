"""
Free functions orchestrating a resumable data-generation job — not a
class-based service, since (like ``features/etag/service.py``) there is no
per-job state to hold beyond what's already threaded through as parameters.
Every generation endpoint (``panchangam/generation_router.py``,
``santhigiri_events/router.py``) imports this module directly.

The actual generation work (astronomy computation, event-occurrence
resolution) stays entirely inside each feature's own write-path service —
``PanchangamGenerationService.generate_streaming``/
``SanthigiriEventService.generate_occurrences_streaming``/
``generate_all_occurrences_streaming``. Those are async generators that yield
one progress model per unit of work and a final result model, discriminated
by a ``type`` field (``"progress"`` / ``"complete"``) — exactly the shape
``stream_generation_job`` below expects.

``stream_generation_job`` drives that generator to completion, persisting
each yielded model into the job row (so a client that lost its live
connection can still see progress via ``GET /generation-jobs/{job_id}``)
*and* yielding the same model as one NDJSON line per event, for a caller
that streams it straight over HTTP. The generation endpoints wrap this in
``streaming.ResilientStreamingResponse``, which keeps driving this generator
to completion even after the client disconnects — the DB writes are the
part that matters for durability; losing the connection only loses the live
push, never the run itself.
"""
from __future__ import annotations

import json
from typing import Any, AsyncIterator, Protocol

from app.core.ports.unit_of_work import UnitOfWork
from app.features.generation_jobs.ports import GenerationJobRepositoryPort


class _ProgressOrResult(Protocol):
    type: str

    def model_dump(self, *, mode: str = ...) -> dict: ...
    def model_dump_json(self) -> str: ...


async def stream_generation_job(
    job_id: str,
    events: AsyncIterator[_ProgressOrResult],
    job_repository: GenerationJobRepositoryPort,
    unit_of_work: UnitOfWork,
) -> AsyncIterator[str]:
    """Drive *events* to completion, persisting progress/result/failure into
    *job_id*'s row as it goes, and yielding each event as one NDJSON line
    (a JSON object followed by ``"\\n"``).

    *job_repository* and *unit_of_work* must be built from a session opened
    for this run alone (never the request-scoped one — see
    ``streaming.ResilientStreamingResponse``, which keeps this generator
    running to completion even after the client that opened the request has
    disconnected, so the request-scoped session may already be gone by then).

    Never raises: any exception from *events* (including one from the
    underlying generation service) is caught, recorded as the job's failure,
    and yielded as a final ``{"type": "error", ...}`` line, since there may
    be no live client left to propagate it to.
    """
    try:
        async for event in events:
            payload: Any = event.model_dump(mode="json")
            if payload.get("type") == "progress":
                job_repository.update_progress(job_id, payload)
            else:
                job_repository.mark_succeeded(job_id, payload)
            unit_of_work.commit()
            yield event.model_dump_json() + "\n"
    except Exception as exc:
        unit_of_work.rollback()
        job_repository.mark_failed(job_id, str(exc))
        unit_of_work.commit()
        yield json.dumps({"type": "error", "detail": str(exc)}) + "\n"
