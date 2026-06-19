"""CRUD operations for the SQLite panchangam database."""

import sqlite3
from datetime import date, datetime
from typing import Optional

from db.database import get_connection
from schemas.panchangam_data import PanchangamData
from core.astronomy.thithi_transition import ThithiTransition
from core.astronomy.nakshatra_transition import NakshatraTransition
from utils.thithi import Thithi
from utils.nakshatra import Nakshatra
from core.calendar.kollavarsham import KollavarshamDate
from utils.santhigiri_events import SanthigiriEvent, SanthigiriEventId, EventCondition


def _dt_to_str(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt is not None else None


def _str_to_dt(s: Optional[str]) -> Optional[datetime]:
    return datetime.fromisoformat(s) if s is not None else None


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------

def upsert_panchangam(conn: sqlite3.Connection, data: PanchangamData) -> None:
    date_str = data.date.isoformat()

    conn.execute(
        """
        INSERT OR REPLACE INTO panchangam
            (date, is_pournami, thithi_id, thithi_name,
             nakshatra_id, nakshatra_name,
             sunrise, sunset, nazhika_from_sunrise,
             kv_day, kv_month, kv_year, kv_month_name_en, kv_month_name_ml)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            date_str,
            int(data.is_pournami),
            data.thithi.id,
            data.thithi.name,
            data.nakshatra.id,
            data.nakshatra.name,
            _dt_to_str(data.sunrise),
            _dt_to_str(data.sunset),
            data.nazhika_from_sunrise,
            data.kv.kv_day,
            data.kv.kv_month,
            data.kv.kv_year,
            data.kv.kv_month_name_en,
            data.kv.kv_month_name_ml,
        ),
    )

    conn.execute("DELETE FROM thithi_transitions WHERE panchangam_date = ?", (date_str,))
    for tt in data.thithi_transitions:
        conn.execute(
            """
            INSERT INTO thithi_transitions
                (panchangam_date, name, thithi_id, thithi_name, start_time, end_time)
            VALUES (?,?,?,?,?,?)
            """,
            (
                date_str,
                tt.name,
                tt.thithi.id,
                tt.thithi.name,
                _dt_to_str(tt.start_time),
                _dt_to_str(tt.end_time),
            ),
        )

    conn.execute("DELETE FROM nakshatra_transitions WHERE panchangam_date = ?", (date_str,))
    for nt in data.nakshatra_transitions:
        conn.execute(
            """
            INSERT INTO nakshatra_transitions
                (panchangam_date, name, nakshatra_id, nakshatra_name, start_time, end_time)
            VALUES (?,?,?,?,?,?)
            """,
            (
                date_str,
                nt.name,
                nt.nakshatra.id,
                nt.nakshatra.name,
                _dt_to_str(nt.start_time),
                _dt_to_str(nt.end_time),
            ),
        )

    conn.execute(
        "DELETE FROM santhigiri_significant_dates WHERE panchangam_date = ?", (date_str,)
    )
    for ev in data.santhigiri_significant_dates:
        conn.execute(
            """
            INSERT INTO santhigiri_significant_dates
                (panchangam_date, event_id, name, description)
            VALUES (?,?,?,?)
            """,
            (date_str, ev.id.value, ev.name, ev.description),
        )


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def get_panchangam_by_date(dt: date) -> Optional[PanchangamData]:
    date_str = dt.isoformat()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM panchangam WHERE date = ?", (date_str,)
        ).fetchone()

        if row is None:
            return None

        thithi_rows = conn.execute(
            "SELECT * FROM thithi_transitions WHERE panchangam_date = ? ORDER BY start_time",
            (date_str,),
        ).fetchall()

        nakshatra_rows = conn.execute(
            "SELECT * FROM nakshatra_transitions WHERE panchangam_date = ? ORDER BY start_time",
            (date_str,),
        ).fetchall()

        event_rows = conn.execute(
            "SELECT * FROM santhigiri_significant_dates WHERE panchangam_date = ?",
            (date_str,),
        ).fetchall()

    thithi_transitions = [
        ThithiTransition(
            name=r["name"],
            thithi=Thithi.from_id(r["thithi_id"]),
            start_time=_str_to_dt(r["start_time"]),  # type: ignore[arg-type]
            end_time=_str_to_dt(r["end_time"]),
        )
        for r in thithi_rows
    ]

    nakshatra_transitions = [
        NakshatraTransition(
            name=r["name"],
            nakshatra=Nakshatra.from_id(r["nakshatra_id"]),
            start_time=_str_to_dt(r["start_time"]),  # type: ignore[arg-type]
            end_time=_str_to_dt(r["end_time"]),
        )
        for r in nakshatra_rows
    ]

    santhigiri_events = [
        SanthigiriEvent(
            id=SanthigiriEventId(r["event_id"]),
            name=r["name"],
            description=r["description"],
            event_condition=EventCondition(),
        )
        for r in event_rows
    ]

    kv = KollavarshamDate(
        date=dt,
        kv_day=row["kv_day"],
        kv_month=row["kv_month"],
        kv_year=row["kv_year"],
        kv_month_name_en=row["kv_month_name_en"],
        kv_month_name_ml=row["kv_month_name_ml"],
    )

    return PanchangamData(
        date=dt,
        kv=kv,
        thithi_transitions=thithi_transitions,
        nakshatra_transitions=nakshatra_transitions,
        is_pournami=bool(row["is_pournami"]),
        thithi=Thithi.from_id(row["thithi_id"]),
        nakshatra=Nakshatra.from_id(row["nakshatra_id"]),
        sunrise=_str_to_dt(row["sunrise"]),  # type: ignore[arg-type]
        sunset=_str_to_dt(row["sunset"]),  # type: ignore[arg-type]
        nazhika_from_sunrise=row["nazhika_from_sunrise"],
        santhigiri_significant_dates=santhigiri_events,
    )


def count_panchangam_rows() -> int:
    with get_connection() as conn:
        row = conn.execute("SELECT COUNT(*) FROM panchangam").fetchone()
        return row[0] if row else 0
