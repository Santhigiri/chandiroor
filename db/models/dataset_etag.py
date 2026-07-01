import datetime

from sqlmodel import Field, SQLModel


class DatasetEtag(SQLModel, table=True):
    """
    Persisted ETag for a named dataset served by the API.

    One row per addressable dataset, keyed by a stable string such as
    ``"year:2026"`` or ``"enum:thithi"``. The ETag is recomputed and written
    whenever the underlying data changes (see ``services.etag_service`` and
    ``db.migrate``), so it survives process restarts, is shared across instances
    via the database, and carries over unchanged to a future Postgres backend.
    """

    __tablename__ = "dataset_etag" # pyright: ignore[reportAssignmentType]

    key:        str               = Field(primary_key=True)
    etag:       str
    updated_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
