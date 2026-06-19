"""
Migrate panchangam data from pickle files into SQLite.

Run once:
    python -m db.migrate [--year YEAR]

Without --year it migrates all available pickle files.
"""

import argparse
import pickle
import sqlite3
import sys
from pathlib import Path
from time import time

from db.database import init_db, get_connection
from db.crud import upsert_panchangam


def migrate_year(year: int, conn: sqlite3.Connection) -> int:
    pkl_path = Path(f"data/panchangam_{year}.pkl")
    if not pkl_path.exists():
        print(f"  Skipping {year}: {pkl_path} not found")
        return 0

    with open(pkl_path, "rb") as f:
        cache = pickle.load(f)

    count = 0
    for dt, data in sorted(cache.items()):
        upsert_panchangam(conn, data)
        count += 1

    return count


def migrate(years: list[int] | None = None) -> None:
    init_db()

    if years is None:
        pkl_files = sorted(Path("data").glob("panchangam_*.pkl"))
        years = []
        for p in pkl_files:
            try:
                years.append(int(p.stem.split("_")[1]))
            except (IndexError, ValueError):
                pass

    if not years:
        print("No pickle files found in data/. Nothing to migrate.")
        return

    start = time()
    total = 0
    with get_connection() as conn:
        for year in years:
            print(f"Migrating {year}...", end=" ", flush=True)
            n = migrate_year(year, conn)
            conn.commit()
            print(f"{n} rows")
            total += n

    elapsed = time() - start
    print(f"\nDone. Migrated {total} rows in {elapsed:.1f}s")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate pickle cache to SQLite")
    parser.add_argument(
        "--year",
        type=int,
        nargs="*",
        help="Year(s) to migrate. Omit to migrate all.",
    )
    args = parser.parse_args()
    migrate(args.year)
