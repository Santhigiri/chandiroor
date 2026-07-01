"""
Seed the immutable lookup tables (Paksha, Thithi, Nakshatra, MalayalamMasa,
Location, SanthigiriEvent) from the Python enums / event definitions.

Call seed_lookup_tables(session) once after init_db().  Subsequent calls are
safe — session.merge() is idempotent on rows that already exist.
"""
from sqlmodel import Session, select

from db.models.location import Location as LocationRow
from db.models.malayalam_masa import MalayalamMasa as MalayalamMasaRow
from db.models.nakshatra import Nakshatra as NakshatraRow
from db.models.paksha import Paksha as PakshaRow
from db.models.santhigiri_event import SanthigiriEvent as SanthigiriEventRow
from db.models.thithi import Thithi as ThithiRow
from utils.location import Location
from utils.malayalam_masa import MalayalamMasa
from utils.nakshatra import Nakshatra
from utils.paksha import Paksha
from utils.santhigiri_events import EVENT_DEFINITIONS_BY_ID
from utils.thithi import Thithi


def seed_santhigiri_events(session: Session) -> None:
    """Insert every defined Santhigiri event, preserving its display order.

    Does NOT commit — callers batch this with the rest of a seed transaction.
    """
    for order, event in enumerate(EVENT_DEFINITIONS_BY_ID.values()):
        session.merge(
            SanthigiriEventRow(
                id=event.id.value,
                name=event.name,
                description=event.description,
                sort_order=order,
            )
        )


def seed_santhigiri_events_if_empty(session: Session) -> bool:
    """Seed event definitions only when the table is empty; commit and return True.

    Backfills a DB first populated before the santhigiri_event table existed,
    without clobbering later edits to an already-seeded table.
    """
    if session.exec(select(SanthigiriEventRow).limit(1)).first() is not None:
        return False
    seed_santhigiri_events(session)
    session.commit()
    return True


def seed_lookup_tables(session: Session) -> None:
    """Insert all Paksha, Thithi, Nakshatra, MalayalamMasa, Location, and SanthigiriEvent values."""
    for p in Paksha:
        session.merge(PakshaRow(id=p.id, name=p.name, ml=p.ml, en=p.en))

    for t in Thithi:
        session.merge(
            ThithiRow(
                id=t.id,
                name=t.name,
                paksha_id=t.paksha.id,
                day=t.day,
                ml=t.ml,
                en=t.en,
            )
        )

    for n in Nakshatra:
        session.merge(NakshatraRow(id=n.id, name=n.name, ml=n.ml, en=n.en))

    for m in MalayalamMasa:
        session.merge(MalayalamMasaRow(id=m.id, name=m.name, ml=m.ml, en=m.en))

    for loc in Location:
        session.merge(
            LocationRow(
                id=loc.id,
                name=loc.code,
                label=loc.label,
                latitude=loc.latitude,
                longitude=loc.longitude,
                timezone=loc.timezone,
            )
        )

    seed_santhigiri_events(session)

    session.commit()
