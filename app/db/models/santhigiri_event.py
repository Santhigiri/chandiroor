from typing import TYPE_CHECKING, Optional

from sqlalchemy import Column, ForeignKey, Integer, String
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.db.models.nakshatra import Nakshatra
    from app.db.models.thithi import Thithi


class SanthigiriEvent(SQLModel, table=True):
    """
    Editable definition of a Santhigiri ashram event type.

    One row per defined event (keyed by its string ``id``), so the
    ``/panchangam/events`` reference endpoint can list *every* event regardless
    of whether it occurs in the loaded date range. Seeded from
    ``utils.santhigiri_events`` but authoritative thereafter: a correction to a
    name/description made in the DB is reflected by the API without a code
    change. ``sort_order`` preserves the original display order.

    The condition columns (nakshatra_id … last_occurance) encode the matching
    rule for when this event falls on a given day — formerly a separate
    ``santhigiri_event_condition`` table.  All condition columns are nullable;
    NULL means "any" / "not applicable".
    """

    __tablename__ = "santhigiri_event" # pyright: ignore[reportAssignmentType]

    id:          str = Field(primary_key=True)   # event id, e.g. 'POURNAMI'
    name:        str
    description: str
    sort_order:  int = Field(index=True)

    # Condition columns — NULL means "any"
    nakshatra_id: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, ForeignKey("nakshatra.id"), nullable=True),
    )
    thithi_id: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, ForeignKey("thithi.id"), nullable=True),
    )

    ml_day:         Optional[int]  = None
    ml_month:       Optional[int]  = None
    ml_year:        Optional[int]  = None

    en_day:         Optional[int]  = None
    en_month:       Optional[int]  = None
    en_year:        Optional[int]  = None

    occurance:      Optional[int]  = None
    is_poornima:    Optional[bool] = None
    last_occurance: Optional[bool] = None

    # Shift the day the other condition columns match by N days. NULL/0 =
    # no shift; positive = N days after; negative = N days before. See
    # utils.santhigiri_events.EventCondition.day_offset and
    # core.calendar.santhigiri_event_occurrences.compute_occurrences.
    day_offset: Optional[int] = None

    # Cross-event precedence: when generating THIS event's occurrences, any
    # date that also matches yields_to_event_id's condition is dropped from
    # this event's occurrence set (see
    # SanthigiriEventService._excluded_dates_for_yield). NULL means "yields
    # to nothing" — the default, unaffected behavior. ON DELETE SET NULL so
    # deleting the referenced event self-heals the referencing event back to
    # normal rather than being blocked or cascading.
    yields_to_event_id: Optional[str] = Field(
        default=None,
        sa_column=Column(
            String,
            ForeignKey("santhigiri_event.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    nakshatra: Optional["Nakshatra"] = Relationship()
    thithi:    Optional["Thithi"]    = Relationship()
