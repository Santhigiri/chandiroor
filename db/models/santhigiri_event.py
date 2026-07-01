from sqlmodel import Field, SQLModel


class SanthigiriEvent(SQLModel, table=True):
    """
    Editable definition of a Santhigiri ashram event type.

    One row per defined event (keyed by the ``SanthigiriEventId`` value), so the
    ``/panchangam/events`` reference endpoint can list *every* event regardless
    of whether it occurs in the loaded date range. Seeded from
    ``utils.santhigiri_events`` but authoritative thereafter: a correction to a
    name/description made in the DB is reflected by the API without a code
    change. ``sort_order`` preserves the original display order.
    """

    __tablename__ = "santhigiri_event" # pyright: ignore[reportAssignmentType]

    id:          str = Field(primary_key=True)   # SanthigiriEventId value, e.g. 'POURNAMI'
    name:        str
    description: str
    sort_order:  int = Field(index=True)
