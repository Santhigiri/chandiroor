"""
Seed the immutable lookup tables (Paksha, Thithi, Nakshatra, MalayalamMasa,
Location, SanthigiriEvent) from the Python enums / event definitions. Only
structural columns are populated; the localized display-name columns (ml, en)
are left NULL — production DBs fill them from ``db/sql/02_seed.sql``.

Call seed_lookup_tables(session) once after init_db().  Subsequent calls are
safe — session.merge() is idempotent on rows that already exist.
"""
from sqlmodel import Session, select

from app.db.models.app_setting import AppSetting as AppSettingRow
from app.db.models.location import Location as LocationRow
from app.db.models.malayalam_masa import MalayalamMasa as MalayalamMasaRow
from app.db.models.nakshatra import Nakshatra as NakshatraRow
from app.db.models.paksha import Paksha as PakshaRow
from app.db.models.santhigiri_event import SanthigiriEvent as SanthigiriEventRow
from app.db.models.thithi import Thithi as ThithiRow
from app.utils.location import Location
from app.core.kollavarsham.enums.masa import MalayalamMasa
from app.core.astronomy.enums.nakshatra import Nakshatra
from app.core.astronomy.enums.paksha import Paksha
from app.utils.santhigiri_events import EVENT_DEFINITIONS_BY_ID
from app.utils.settings_keys import SettingKey
from app.core.astronomy.enums.thithi import Thithi
from app.schemas.app_setting import (
    AstronomyEpsilonsValue,
    DefaultLocationCodeValue,
    EventCutoffsValue,
    MaxEventGenerateYearSpanValue,
    MaxGenerateSpanDaysValue,
    NakshatraStepDaysValue,
    SeedYearRangeValue,
)


def seed_santhigiri_events(session: Session) -> None:
    """Insert every defined Santhigiri event, preserving its display order.

    Does NOT commit — callers batch this with the rest of a seed transaction.
    """
    for order, event in enumerate(EVENT_DEFINITIONS_BY_ID.values()):
        c = event.event_condition
        session.merge(
            SanthigiriEventRow(
                id=event.id,
                name=event.name,
                description=event.description,
                sort_order=order,
                nakshatra_id=c.nakshatra.id if c.nakshatra else None,
                thithi_id=c.thithi.id if c.thithi else None,
                ml_day=c.ml_day,
                ml_month=c.ml_month.id if c.ml_month else None,
                ml_year=c.ml_year,
                en_day=c.en_day,
                en_month=c.en_month,
                en_year=c.en_year,
                occurance=c.occurance,
                is_poornima=c.is_poornima,
                last_occurance=c.last_occurance,
                day_offset=c.day_offset,
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


def seed_app_settings(session: Session) -> None:
    """Insert every known app setting with its default value — identical to
    today's hardcoded constants, so applying this is behaviorally a no-op
    until an admin edits a value (see ``features.settings.service``).

    Does NOT commit — callers batch this with the rest of a seed transaction.
    """
    defaults = {
        SettingKey.SEED_YEAR_RANGE: SeedYearRangeValue(),
        SettingKey.DEFAULT_LOCATION_CODE: DefaultLocationCodeValue(),
        SettingKey.MAX_GENERATE_SPAN_DAYS: MaxGenerateSpanDaysValue(),
        SettingKey.MAX_EVENT_GENERATE_YEAR_SPAN: MaxEventGenerateYearSpanValue(),
        SettingKey.EVENT_CUTOFFS: EventCutoffsValue(),
        SettingKey.NAKSHATRA_TRANSITION_STEP_DAYS: NakshatraStepDaysValue(),
        SettingKey.ASTRONOMY_EPSILONS: AstronomyEpsilonsValue(),
    }
    for key, value in defaults.items():
        session.merge(AppSettingRow(key=key.value, value=value.model_dump()))


def seed_app_settings_if_empty(session: Session) -> bool:
    """Seed default app settings only when the table is empty; commit and
    return True. Backfills a DB first populated before the app_setting table
    existed, without clobbering an admin's later edits to an already-seeded
    table."""
    if session.exec(select(AppSettingRow).limit(1)).first() is not None:
        return False
    seed_app_settings(session)
    session.commit()
    return True


def seed_lookup_tables(session: Session) -> None:
    """Insert all Paksha, Thithi, Nakshatra, MalayalamMasa, Location, SanthigiriEvent,
    and default AppSetting values."""
    # Only structural data is seeded from the enums (id / name / paksha / day).
    # Localized display text (ml, en) is left NULL here — real databases get it
    # from db/sql/02_seed.sql; nothing in the app reads it off these rows in
    # test/dev.
    for p in Paksha:
        session.merge(PakshaRow(id=p.id, name=p.name))

    for t in Thithi:
        session.merge(
            ThithiRow(
                id=t.id,
                name=t.name,
                paksha_id=t.paksha.id,
                day=t.day,
            )
        )

    for n in Nakshatra:
        session.merge(NakshatraRow(id=n.id, name=n.name))

    for m in MalayalamMasa:
        session.merge(MalayalamMasaRow(id=m.id, name=m.name))

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
    seed_app_settings(session)

    session.commit()
