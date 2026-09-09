"""
GenerationJobRepository tests: the create/update/get lifecycle, and — the
whole point of this table — that ``start`` enforces at most one running job
at a time via the unique constraint on ``lock_key``, and that finishing a job
(succeeded or failed) frees the lock for the next one.
"""
import pytest
from sqlmodel import Session

from app.features.generation_jobs.ports import (
    JobAlreadyRunningException,
    JobNotFoundException,
)
from app.features.generation_jobs.repository import GenerationJobRepository


@pytest.fixture
def repo(session: Session) -> GenerationJobRepository:
    return GenerationJobRepository(session)


def test_start_creates_a_running_job(repo: GenerationJobRepository):
    job = repo.start("panchangam_generate", {"start_date": "2026-01-01"}, "admin")

    assert job.status == "running"
    assert job.job_type == "panchangam_generate"
    assert job.params == {"start_date": "2026-01-01"}
    assert job.started_by == "admin"
    assert job.progress is None
    assert job.result is None


def test_second_start_while_running_conflicts(repo: GenerationJobRepository, session: Session):
    repo.start("panchangam_generate", {}, "admin")
    session.commit()

    with pytest.raises(JobAlreadyRunningException):
        repo.start("event_occurrences", {"event_id": "POURNAMI"}, "admin")


def test_starting_a_new_job_after_success_is_allowed(
    repo: GenerationJobRepository, session: Session
):
    first = repo.start("panchangam_generate", {}, "admin")
    session.commit()

    repo.mark_succeeded(first.id, {"count": 10})
    session.commit()

    second = repo.start("event_occurrences", {"event_id": "POURNAMI"}, "admin")
    session.commit()
    assert second.status == "running"


def test_starting_a_new_job_after_failure_is_allowed(
    repo: GenerationJobRepository, session: Session
):
    first = repo.start("panchangam_generate", {}, "admin")
    session.commit()

    repo.mark_failed(first.id, "boom")
    session.commit()

    second = repo.start("event_occurrences", {"event_id": "POURNAMI"}, "admin")
    session.commit()
    assert second.status == "running"


def test_update_progress_and_get(repo: GenerationJobRepository, session: Session):
    job = repo.start("panchangam_generate", {}, "admin")
    session.commit()

    repo.update_progress(job.id, {"completed": 5, "total": 10})
    session.commit()

    fetched = repo.get(job.id)
    assert fetched.status == "running"
    assert fetched.progress == {"completed": 5, "total": 10}


def test_mark_failed_records_error_and_frees_lock(
    repo: GenerationJobRepository, session: Session
):
    job = repo.start("panchangam_generate", {}, "admin")
    session.commit()

    repo.mark_failed(job.id, "something went wrong")
    session.commit()

    fetched = repo.get(job.id)
    assert fetched.status == "failed"
    assert fetched.error == "something went wrong"
    assert repo.get_active() is None


def test_get_active_returns_the_running_job(repo: GenerationJobRepository, session: Session):
    assert repo.get_active() is None

    job = repo.start("panchangam_generate", {}, "admin")
    session.commit()

    active = repo.get_active()
    assert active is not None
    assert active.id == job.id


def test_get_unknown_job_raises(repo: GenerationJobRepository):
    with pytest.raises(JobNotFoundException):
        repo.get("does-not-exist")
