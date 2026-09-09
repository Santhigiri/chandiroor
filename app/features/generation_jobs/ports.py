"""
Repository port for background data-generation jobs (``generation_job`` table).

This is a genuinely cross-feature dependency: ``features/panchangam/generation_router.py``
and ``features/santhigiri_events/router.py`` both start/track jobs through it, so it
gets its own small feature (``features/generation_jobs/``) rather than living inside
either of those, following the same "ports.py defines the Protocol + DTOs + domain
exceptions" shape as ``features/auth/ports.py``.

There is deliberately no ``job_type``-specific behaviour here — a job is just
``{id, job_type, status, lock_key, params, progress, result, error, started_by,
created_at, updated_at}``; the caller supplies whatever ``params``/``progress``/
``result`` payloads make sense for its own job type; see
``features/generation_jobs/service.py::run_generation_job`` for how a job's
underlying async generator feeds those fields.
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Any, Dict, Optional, Protocol


class JobAlreadyRunningException(Exception):
    """Raised by ``start`` when another job is already running — anywhere,
    not just for the same ``job_type`` — since only one generation run is
    allowed at a time across every API instance sharing the database."""


class JobNotFoundException(Exception):
    """Raised when a job id does not exist."""

    def __init__(self, job_id: str) -> None:
        self.job_id = job_id
        super().__init__(f"Generation job '{job_id}' not found.")


@dataclass(frozen=True)
class GenerationJobGet:
    id: str
    job_type: str
    status: str  # "running" | "succeeded" | "failed"
    params: Dict[str, Any]
    progress: Optional[Dict[str, Any]]
    result: Optional[Dict[str, Any]]
    error: Optional[str]
    started_by: Optional[str]
    created_at: datetime.datetime
    updated_at: datetime.datetime


class GenerationJobRepositoryPort(Protocol):
    def start(
        self, job_type: str, params: Dict[str, Any], started_by: Optional[str]
    ) -> GenerationJobGet:
        """Insert a new ``status="running"`` row and return it.

        Raises :class:`JobAlreadyRunningException` if a job is already
        running — enforced by the DB's unique constraint on ``lock_key``, so
        this is safe even if two API instances race to start a job at the
        same time. Does NOT commit; the caller commits once the insert has
        succeeded (see ``run_generation_job``)."""

    def update_progress(self, job_id: str, progress: Dict[str, Any]) -> None:
        """Overwrite *job_id*'s ``progress`` field. Does NOT commit."""

    def mark_succeeded(self, job_id: str, result: Dict[str, Any]) -> None:
        """Mark *job_id* ``succeeded`` with *result* and free the lock.
        Does NOT commit."""

    def mark_failed(self, job_id: str, error: str) -> None:
        """Mark *job_id* ``failed`` with *error* and free the lock.
        Does NOT commit."""

    def get(self, job_id: str) -> GenerationJobGet:
        """Raises :class:`JobNotFoundException` if *job_id* does not exist."""

    def get_active(self) -> Optional[GenerationJobGet]:
        """Return the currently running job, if any — lets a client that
        lost its job id (e.g. reloaded the page mid-run) find it again."""
