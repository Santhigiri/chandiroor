import datetime
from typing import Optional

from sqlalchemy import Column
from sqlmodel import JSON, Field, SQLModel

from app.db.models.types import UTCDateTime


class GenerationJob(SQLModel, table=True):
    """
    Bookkeeping row for a background data-generation run (panchangam
    regeneration or Santhigiri event-occurrence regeneration).

    A run is started by inserting a ``status="running"`` row with
    ``lock_key=1`` and executed in a FastAPI background task detached from
    the originating request, so it keeps running (and this row keeps being
    updated) even if the client disconnects. Progress/result/error are
    written back to this same row as the run proceeds, so a client that lost
    its connection can reconnect later and poll ``GET
    /api/v1/generation-jobs/{id}`` (or ``/active`` if it doesn't have the id
    any more) to see how it went.

    ``lock_key`` is the cross-instance "only one generation at a time" lock:
    it is set to the constant ``1`` while ``status="running"`` and cleared to
    ``NULL`` the moment the run finishes (succeeded or failed). The unique
    constraint on this column lets at most one row hold the value ``1``
    (both Postgres and SQLite allow unlimited ``NULL``s through a unique
    constraint) — a second concurrent start, from this process or another
    instance entirely, gets a real ``IntegrityError`` at insert time, which
    the repository translates into ``JobAlreadyRunningException``. This
    relies on nothing but the shared Postgres database, so it works across
    however many API instances are running.
    """

    __tablename__ = "generation_job"  # pyright: ignore[reportAssignmentType]

    id:         str            = Field(primary_key=True)
    job_type:   str            = Field(index=True)
    status:     str            = Field(index=True)  # "running" | "succeeded" | "failed"
    lock_key:   Optional[int]  = Field(default=None, unique=True)

    params:     dict           = Field(sa_column=Column(JSON, nullable=False))
    progress:   Optional[dict] = Field(default=None, sa_column=Column(JSON, nullable=True))
    result:     Optional[dict] = Field(default=None, sa_column=Column(JSON, nullable=True))
    error:      Optional[str]  = None

    started_by: Optional[str]  = None
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
        sa_column=Column(UTCDateTime, nullable=False),
    )
    updated_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
        sa_column=Column(UTCDateTime, nullable=False),
    )
