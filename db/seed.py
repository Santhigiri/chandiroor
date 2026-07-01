"""
Seed the immutable lookup tables (Paksha, Thithi, Nakshatra, MalayalamMasa, Location) from the Python enums.

Call seed_lookup_tables(session) once after init_db().  Subsequent calls are
safe — session.merge() is idempotent on rows that already exist.
"""
from sqlmodel import Session

from db.models.location import Location as LocationRow
from db.models.malayalam_masa import MalayalamMasa as MalayalamMasaRow
from db.models.nakshatra import Nakshatra as NakshatraRow
from db.models.paksha import Paksha as PakshaRow
from db.models.thithi import Thithi as ThithiRow
from utils.location import Location
from utils.malayalam_masa import MalayalamMasa
from utils.nakshatra import Nakshatra
from utils.paksha import Paksha
from utils.thithi import Thithi


def seed_lookup_tables(session: Session) -> None:
    """Insert all Paksha, Thithi, Nakshatra, MalayalamMasa, and Location values into their lookup tables."""
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

    session.commit()
