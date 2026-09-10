"""
``stream_generation_job`` drives an async generator of progress/result models
into the job repository, yielding each as an NDJSON line, and never lets an
exception escape (the request driving it may outlive any particular client
connection, so there may be nothing left to propagate an exception to)."""
import asyncio
import json
from typing import Literal

from pydantic import BaseModel
from sqlmodel import Session

from app.db.unit_of_work import SqlUnitOfWork
from app.features.generation_jobs.repository import GenerationJobRepository
from app.features.generation_jobs.service import stream_generation_job


class _Progress(BaseModel):
    type: Literal["progress"] = "progress"
    completed: int
    total: int


class _Result(BaseModel):
    type: Literal["complete"] = "complete"
    count: int


async def _successful_stream():
    yield _Progress(completed=1, total=2)
    yield _Progress(completed=2, total=2)
    yield _Result(count=2)


async def _failing_stream():
    yield _Progress(completed=1, total=2)
    raise RuntimeError("astronomy blew up")


async def _collect(job_id, events, repo, uow):
    return [line async for line in stream_generation_job(job_id, events, repo, uow)]


def test_stream_generation_job_records_progress_then_result(session: Session):
    repo = GenerationJobRepository(session)
    uow = SqlUnitOfWork(session)
    job = repo.start("panchangam_generate", {}, "admin")
    session.commit()

    lines = asyncio.run(_collect(job.id, _successful_stream(), repo, uow))

    assert [json.loads(line)["type"] for line in lines] == [
        "progress",
        "progress",
        "complete",
    ]
    final = repo.get(job.id)
    assert final.status == "succeeded"
    assert final.result == {"type": "complete", "count": 2}
    assert final.progress == {"type": "progress", "completed": 2, "total": 2}


def test_stream_generation_job_records_failure_without_raising(session: Session):
    repo = GenerationJobRepository(session)
    uow = SqlUnitOfWork(session)
    job = repo.start("panchangam_generate", {}, "admin")
    session.commit()

    lines = asyncio.run(_collect(job.id, _failing_stream(), repo, uow))

    assert json.loads(lines[-1]) == {"type": "error", "detail": "astronomy blew up"}
    final = repo.get(job.id)
    assert final.status == "failed"
    assert "astronomy blew up" in final.error
