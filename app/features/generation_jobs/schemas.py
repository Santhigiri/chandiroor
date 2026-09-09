"""Response schemas for the read-only ``/api/v1/generation-jobs`` endpoints."""
from __future__ import annotations

import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel


class GenerationJobStarted(BaseModel):
    """Returned immediately (HTTP 202) by a ``POST .../generate*`` endpoint
    once the job row is created — the run itself continues in the
    background. Poll ``GET /api/v1/generation-jobs/{job_id}`` for progress."""

    job_id: str
    job_type: str
    status: str


class GenerationJobStatus(BaseModel):
    id: str
    job_type: str
    status: str
    params: Dict[str, Any]
    progress: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    started_by: Optional[str] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime
