from typing import TYPE_CHECKING, Optional

from sqlalchemy import Column, ForeignKey, Integer
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from db.models.nakshatra import Nakshatra
    from db.models.thithi import Thithi


class SanthigiriEvent(SQLModel, table=True):
    """
    Editable definition of a Santhigiri ashram event type.

    One row per defined event (keyed by the ``SanthigiriEventId`` value), so the
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

    id:          str = Field(primary_key=True)   # SanthigiriEventId value, e.g. 'POURNAMI'
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

    nakshatra: Optional["Nakshatra"] = Relationship()
    thithi:    Optional["Thithi"]    = Relationship()
