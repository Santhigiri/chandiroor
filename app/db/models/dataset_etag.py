import datetime

from sqlalchemy import Column
from sqlmodel import Field, SQLModel

from app.db.models.types import UTCDateTime


class DatasetEtag(SQLModel, table=True):
    """
    Persisted ETag for a named dataset served by the API.

    One row per addressable dataset, keyed by a stable string such as
    ``"year:2026"`` or ``"enum:thithi"``. The ETag is recomputed and written
    whenever the underlying data changes (see ``features.etag.service``), so it
    survives process restarts and is shared across instances via the Postgres
    database.
    """

    __tablename__ = "dataset_etag" # pyright: ignore[reportAssignmentType]

    key:        str               = Field(primary_key=True)
    etag:       str
    updated_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
        sa_column=Column(UTCDateTime, nullable=False),
    )
