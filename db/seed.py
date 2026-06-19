"""
Seed the immutable lookup tables (Paksha, Thithi, Nakshatra) from the Python enums.

Call seed_lookup_tables(session) once after init_db().  Subsequent calls are
safe — session.merge() is idempotent on rows that already exist.
"""
from sqlmodel import Session

from db.models.nakshatra import Nakshatra as NakshatraRow
from db.models.paksha import Paksha as PakshaRow
from db.models.thithi import Thithi as ThithiRow
from utils.nakshatra import Nakshatra
from utils.paksha import Paksha
from utils.thithi import Thithi


def seed_lookup_tables(session: Session) -> None:
    """Insert all Paksha, Thithi, and Nakshatra values into their lookup tables."""
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

    session.commit()
