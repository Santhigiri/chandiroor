"""Custom SQLAlchemy column types shared across ``db/models/``."""
import datetime

from sqlalchemy.types import DateTime, TypeDecorator


class UTCDateTime(TypeDecorator):
    """A ``DateTime(timezone=True)`` that always round-trips as UTC-aware.

    Forces UTC on read regardless of the connection's session ``TimeZone``,
    and works correctly under the test suite's SQLite in-memory engine, which
    has no native tz-aware storage and would otherwise silently drop tzinfo.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if value.tzinfo is None:
            raise ValueError("UTCDateTime requires a timezone-aware datetime")
        return value.astimezone(datetime.timezone.utc)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if value.tzinfo is None:
            return value.replace(tzinfo=datetime.timezone.utc)
        return value.astimezone(datetime.timezone.utc)
