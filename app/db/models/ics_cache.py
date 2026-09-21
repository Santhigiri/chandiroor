import datetime

from sqlalchemy import Column, Text
from sqlmodel import Field, SQLModel

from app.db.models.types import UTCDateTime


class IcsCache(SQLModel, table=True):
    """
    Persisted, already-built iCalendar (RFC 5545) document for the Santhigiri
    events feed (``GET /panchangam/events/calendar.ics``).

    A singleton row (``key="events"``) — there is only one ICS document, unlike
    ``dataset_etag`` which is keyed per (location, year)/enum dataset. Storing
    the built body here (not just its ETag) lets the read path serve it with a
    single indexed row fetch instead of re-scanning the full seed year range
    and re-serializing on every request. Refreshed atomically alongside the
    ``events``/year ETags whenever event data changes (see
    ``features.santhigiri_events.service``).
    """

    __tablename__ = "ics_cache"  # pyright: ignore[reportAssignmentType]

    key:        str               = Field(primary_key=True)
    body:       str                = Field(sa_column=Column(Text, nullable=False))
    etag:       str
    updated_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
        sa_column=Column(UTCDateTime, nullable=False),
    )
