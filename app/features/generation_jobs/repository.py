"""
GenerationJobRepository — concrete adapter for ``GenerationJobRepositoryPort``,
implementing it against SQLModel's ``generation_job`` table.
"""
from __future__ import annotations

import datetime
import uuid
from typing import Any, Dict, Optional

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.db.models.generation_job import GenerationJob
from app.features.generation_jobs.ports import (
    GenerationJobGet,
    JobAlreadyRunningException,
    JobNotFoundException,
)


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _to_dto(row: GenerationJob) -> GenerationJobGet:
    return GenerationJobGet(
        id=row.id,
        job_type=row.job_type,
        status=row.status,
        params=row.params,
        progress=row.progress,
        result=row.result,
        error=row.error,
        started_by=row.started_by,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class GenerationJobRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def start(
        self, job_type: str, params: Dict[str, Any], started_by: Optional[str]
    ) -> GenerationJobGet:
        now = _now()
        row = GenerationJob(
            id=uuid.uuid4().hex,
            job_type=job_type,
            status="running",
            lock_key=1,
            params=params,
            started_by=started_by,
            created_at=now,
            updated_at=now,
        )
        self._s.add(row)
        try:
            self._s.flush()
        except IntegrityError:
            self._s.rollback()
            raise JobAlreadyRunningException()
        return _to_dto(row)

    def update_progress(self, job_id: str, progress: Dict[str, Any]) -> None:
        row = self._get_row(job_id)
        row.progress = progress
        row.updated_at = _now()
        self._s.add(row)

    def mark_succeeded(self, job_id: str, result: Dict[str, Any]) -> None:
        row = self._get_row(job_id)
        row.status = "succeeded"
        row.result = result
        row.lock_key = None
        row.updated_at = _now()
        self._s.add(row)

    def mark_failed(self, job_id: str, error: str) -> None:
        row = self._get_row(job_id)
        row.status = "failed"
        row.error = error
        row.lock_key = None
        row.updated_at = _now()
        self._s.add(row)

    def get(self, job_id: str) -> GenerationJobGet:
        return _to_dto(self._get_row(job_id))

    def get_active(self) -> Optional[GenerationJobGet]:
        row = self._s.exec(
            select(GenerationJob).where(GenerationJob.status == "running")
        ).first()
        return _to_dto(row) if row else None

    def _get_row(self, job_id: str) -> GenerationJob:
        row = self._s.get(GenerationJob, job_id)
        if row is None:
            raise JobNotFoundException(job_id)
        return row
