from typing import TYPE_CHECKING, Optional

from sqlalchemy import Column, ForeignKey, Integer, String
from sqlmodel import Field, Relationship, SQLModel

from app.features.santhigiri_events.ports import SanthigiriEventBase, SanthigiriEventGet


from app.core.astronomy.enums.nakshatra import Nakshatra as NakshatraEnum
from app.utils.santhigiri_events import EventCondition
from app.core.astronomy.enums.thithi import Thithi as ThithiEnum
from app.utils.malayalam_masa import MalayalamMasa as MalayalamMasaEnum

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
    


    @classmethod
    def from_dto(cls, event_id: str, event: SanthigiriEventBase) -> "SanthigiriEvent":
        ec = event.event_condition
        nakshatra_id : Optional[int] = ec.nakshatra.id if ec.nakshatra is not None else None
        thithi_id : Optional[int] = ec.thithi.id if ec.thithi is not None else None
        ml_month: Optional[int] = ec.ml_month.id if ec.ml_month is not None else None
        yields_to_event_id: Optional[str] = event.yields_to_event_id
        return SanthigiriEvent(
            id = event_id,
            name = event.name,
            description= event.description,
            sort_order= event.sort_order,
            nakshatra_id= nakshatra_id,
            thithi_id = thithi_id,
            ml_day=ec.ml_day,
            ml_month=ml_month,
            ml_year=ec.ml_year,
            en_day=ec.en_day,
            en_month=ec.en_month,
            en_year=ec.en_year,
            occurance=ec.occurance,
            is_poornima=ec.is_poornima,
            last_occurance=ec.last_occurance,
            day_offset=ec.day_offset,
            yields_to_event_id=yields_to_event_id,
        )

    def to_dto(self)-> SanthigiriEventGet:
        return SanthigiriEventGet(
            id=self.id,
            name=self.name,
            description=self.description,
            sort_order=self.sort_order,
            event_condition= EventCondition(
            nakshatra=NakshatraEnum.from_id(self.nakshatra_id) if self.nakshatra_id is not None else None,
            thithi=ThithiEnum.from_id(self.thithi_id) if self.thithi_id is not None else None,
            ml_day=self.ml_day,
            ml_month=MalayalamMasaEnum.from_id(self.ml_month) if self.ml_month is not None else None,
            ml_year=self.ml_year,
            en_day=self.en_day,
            en_month=self.en_month,
            en_year=self.en_year,
            occurance=self.occurance,
            is_poornima=self.is_poornima,
            last_occurance=self.last_occurance,
            day_offset=self.day_offset,
            ),
            yields_to_event_id=self.yields_to_event_id,
        )
