"""
Build-time generator for the PostgreSQL seeding SQL files.

Produces (relative to the repo root):
  db/sql/01_schema.sql  — CREATE TABLE / index DDL for the full schema
  db/sql/02_seed.sql    — INSERTs for the lookup tables + 10 years of data

The DDL is emitted from the live SQLModel metadata compiled for the PostgreSQL
dialect, so it always matches the ORM models in db/models/. The data is read
straight from the pickle cache (data/panchangam_*.pkl) via the same enums and
event definitions the runtime seeder uses.

This is a maintenance tool — it is NOT imported at runtime. Run it after
changing the schema, the domain enums, the event definitions, or the pickle
caches:

    python scripts/gen_seed_sql.py
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from sqlalchemy.schema import CreateIndex, CreateTable
from sqlalchemy.dialects import postgresql
from sqlmodel import SQLModel

import db.models  # noqa: F401 — registers all tables on SQLModel.metadata

from utils.cache_crud import load_cache
from utils.location import Location as LocationEnum
from utils.malayalam_masa import MalayalamMasa
from utils.nakshatra import Nakshatra
from utils.paksha import Paksha
from utils.thithi import Thithi
from utils.santhigiri_events import EVENT_DEFINITIONS_BY_ID

OUT = REPO_ROOT / "db" / "sql"
DIALECT = postgresql.dialect()
TVM_ID = LocationEnum.TVM.id


# ── SQL literal helpers ───────────────────────────────────────────────────────

def q(v) -> str:
    """Render a Python value as a Postgres SQL literal."""
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, datetime):
        # Store naive local wall-clock (Asia/Kolkata) — matches the model's
        # tz-naive TIMESTAMP columns.
        return "'" + v.replace(tzinfo=None).isoformat(sep=" ") + "'"
    if hasattr(v, "isoformat"):  # date
        return "'" + v.isoformat() + "'"
    return "'" + str(v).replace("'", "''") + "'"


def insert_block(table: str, columns: list[str], rows: list[tuple], batch: int = 500) -> str:
    """Build one or more multi-row INSERT statements for *rows*."""
    if not rows:
        return f"-- (no rows for {table})\n"
    cols = ", ".join(columns)
    out: list[str] = []
    for i in range(0, len(rows), batch):
        chunk = rows[i:i + batch]
        values = ",\n".join("  (" + ", ".join(q(c) for c in r) + ")" for r in chunk)
        out.append(f"INSERT INTO {table} ({cols}) VALUES\n{values};\n")
    return "\n".join(out)


# ── Schema DDL ────────────────────────────────────────────────────────────────

def build_schema() -> str:
    parts = [
        "-- ============================================================",
        "-- Panchangam API — PostgreSQL schema (Neon)",
        "-- Generated from the SQLModel table definitions in db/models/.",
        "-- Apply this first, then 02_seed.sql.",
        "-- ============================================================",
        "",
    ]
    for table in SQLModel.metadata.sorted_tables:
        parts.append(str(CreateTable(table).compile(dialect=DIALECT)).strip().rstrip() + ";")
        parts.append("")
        for index in sorted(table.indexes, key=lambda ix: ix.name):
            parts.append(str(CreateIndex(index).compile(dialect=DIALECT)).strip().rstrip() + ";")
        if table.indexes:
            parts.append("")
    return "\n".join(parts) + "\n"


# ── Lookup-table seed rows ────────────────────────────────────────────────────

def build_lookup_seed() -> str:
    parts = ["-- ---------- Lookup tables ----------", ""]

    parts.append(insert_block(
        "paksha", ["id", "name", "ml", "en"],
        [(p.id, p.name, p.ml, p.en) for p in Paksha],
    ))
    parts.append(insert_block(
        "nakshatra", ["id", "name", "ml", "en"],
        [(n.id, n.name, n.ml, n.en) for n in Nakshatra],
    ))
    parts.append(insert_block(
        "thithi", ["id", "name", "paksha_id", "day", "ml", "en"],
        [(t.id, t.name, t.paksha.id, t.day, t.ml, t.en) for t in Thithi],
    ))
    parts.append(insert_block(
        "malayalam_masa", ["id", "name", "ml", "en"],
        [(m.id, m.name, m.ml, m.en) for m in MalayalamMasa],
    ))
    parts.append(insert_block(
        "location", ["id", "name", "label", "latitude", "longitude", "timezone"],
        [(l.id, l.code, l.label, l.latitude, l.longitude, l.timezone) for l in LocationEnum],
    ))
    # location.id is a SERIAL column seeded with explicit ids — advance the sequence.
    parts.append(
        "SELECT setval(pg_get_serial_sequence('location', 'id'), "
        "(SELECT MAX(id) FROM location));\n"
    )

    event_rows = []
    for order, event in enumerate(EVENT_DEFINITIONS_BY_ID.values()):
        c = event.event_condition
        event_rows.append((
            event.id, event.name, event.description, order,
            c.nakshatra.id if c.nakshatra else None,
            c.thithi.id if c.thithi else None,
            c.ml_day, c.ml_month.id if c.ml_month else None, c.ml_year,
            c.en_day, c.en_month, c.en_year,
            c.occurance, c.is_poornima, c.last_occurance,
        ))
    parts.append(insert_block(
        "santhigiri_event",
        ["id", "name", "description", "sort_order", "nakshatra_id", "thithi_id",
         "ml_day", "ml_month", "ml_year", "en_day", "en_month", "en_year",
         "occurance", "is_poornima", "last_occurance"],
        event_rows,
    ))
    return "\n".join(parts)


# ── Panchangam data seed rows ─────────────────────────────────────────────────

def build_data_seed(cache) -> str:
    dates = sorted(cache.keys())

    panchangam_rows, kollavarsham_rows, sunrise_rows = [], [], []
    thithi_trans_rows, nak_trans_rows, event_date_rows = [], [], []

    for d in dates:
        p = cache[d]
        # All pre-computed data is for TVM (location_id = 1). The panchangam row
        # and its location-dependent children are keyed by (date, location_id);
        # santhigiri_event_dates is location-independent (date only).
        panchangam_rows.append((p.date, TVM_ID, p.thithi.id, p.nakshatra.id, p.nazhika_from_sunrise))
        kollavarsham_rows.append((p.date, TVM_ID, p.kv.kv_day, p.kv.kv_month, p.kv.kv_year))
        sunrise_rows.append((p.date, TVM_ID, p.sunrise, p.sunset))
        for t in p.thithi_transitions:
            thithi_trans_rows.append((p.date, TVM_ID, t.thithi.id, t.start_time, t.end_time))
        for n in p.nakshatra_transitions:
            nak_trans_rows.append((p.date, TVM_ID, n.nakshatra.id, n.start_time, n.end_time))
        for e in p.santhigiri_significant_dates:
            event_date_rows.append((p.date, e.id))

    return "\n".join([
        f"-- ---------- Panchangam data ({dates[0]} .. {dates[-1]}, {len(dates)} days) ----------",
        "",
        # id omitted on child tables -> SERIAL auto-assigns
        insert_block("panchangam", ["date", "location_id", "thithi_id", "nakshatra_id", "nazhika_from_sunrise"], panchangam_rows),
        insert_block("kollavarsham_date", ["date", "location_id", "kv_day", "kv_month", "kv_year"], kollavarsham_rows),
        insert_block("sunrise_sunset", ["date", "location_id", "sunrise", "sunset"], sunrise_rows),
        insert_block("thithi_transitions", ["panchangam_date", "location_id", "thithi_id", "start_time", "end_time"], thithi_trans_rows),
        insert_block("nakshatra_transitions", ["panchangam_date", "location_id", "nakshatra_id", "start_time", "end_time"], nak_trans_rows),
        insert_block("santhigiri_event_dates", ["panchangam_date", "event_id"], event_date_rows),
    ])


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    (OUT / "01_schema.sql").write_text(build_schema(), encoding="utf-8")
    print("wrote", OUT / "01_schema.sql")

    cache = load_cache()
    seed = [
        "-- ============================================================",
        "-- Panchangam API — seed data (PostgreSQL / Neon)",
        "-- Apply 01_schema.sql first. Insertion order respects FKs.",
        "-- dataset_etag is intentionally left empty (derived/recomputed).",
        "-- ============================================================",
        "",
        "BEGIN;",
        "",
        build_lookup_seed(),
        "",
        build_data_seed(cache),
        "",
        "COMMIT;",
        "",
    ]
    (OUT / "02_seed.sql").write_text("\n".join(seed), encoding="utf-8")
    print("wrote", OUT / "02_seed.sql")


if __name__ == "__main__":
    main()
