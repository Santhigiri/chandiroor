"""
Regenerate panchangam data and Santhigiri event occurrences for the database's
configured "available year span" (the ``seed_year_range`` admin setting,
2021-2030 by default) directly against Postgres — no running API server or
HTTP round trip required.

Santhigiri event occurrences are regenerated the same way the admin
`/events/generate` endpoint does it: this script builds a real
`SanthigiriEventService` (see `app/api/deps.py` for the reference wiring this
mirrors) and drives its `generate_all_occurrences_streaming` generator
directly, printing one progress line per (year, event) pair to stdout exactly
like the NDJSON stream a client would read.

Base panchangam data is generated differently, on purpose: rather than going
through `PanchangamGenerationService.generate_streaming` (the plain day-by-day
iterator the live `/generate` endpoint uses, kept simple there for the
streaming/progress contract), this script calls
`core.calendar.panchangam.get_panchangam_data_range` directly — the
range-batched computation (one chunked ``find_discrete`` pass for Thithi/
Nakshatra transitions, one pass each for Kollavarsham/Chandra Masa/sunrise-
sunset, instead of redundantly recomputing each per day) that a full
multi-year regeneration benefits from and a single interactive HTTP request
does not need to expose. This is a script-only optimization: it does not
change the `/generate` endpoint or its streaming UI.

Intended to be run by hand or from a manual GitHub Actions workflow (see
`.github/workflows/generate-year-spans.yml`) to keep the seeded range's data
current after an astronomy/calendar code change, without needing an admin to
click through the UI.

Usage:
    DATABASE_URL=postgresql://... python scripts/generate_year_spans.py
    DATABASE_URL=postgresql://... python scripts/generate_year_spans.py --start-year 2021 --end-year 2030
    DATABASE_URL=postgresql://... python scripts/generate_year_spans.py --skip-events
    DATABASE_URL=postgresql://... python scripts/generate_year_spans.py --location tvm

By default, the year range is read from the `seed_year_range` setting stored
in the database; pass --start-year/--end-year to override it. Santhigiri
event occurrences are regenerated for every event across the same range via
`SanthigiriEventService.generate_all_occurrences_streaming`, which requires
the panchangam data for the full range to already be present.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import date
from time import perf_counter

from sqlmodel import Session

from app.core.ports.reference_repository import ReferenceRepositoryPort
from app.core.ports.settings_service import SettingsServicePort
from app.core.ports.unit_of_work import UnitOfWork
from app.db.database import engine
from app.db.reference_repository import ReferenceRepository
from app.db.unit_of_work import SqlUnitOfWork
from app.features.etag.ports import EtagRepositoryPort
from app.features.etag.repository import EtagRepository
from app.features.etag.service import refresh_etags
from app.features.panchangam.ports import PanchangamRepositoryPort
from app.features.panchangam.repository import PanchangamRepository
from app.features.panchangam.service import PanchangamService
from app.features.santhigiri_events.repository import SanthigiriEventRepository
from app.features.santhigiri_events.service import (
    IncompleteYearDataException,
    SanthigiriEventService,
    YearSpanTooLargeException,
)
from app.features.settings.repository import AppSettingRepository
from app.features.settings.service import SettingsService
from app.utils.location import Location


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--start-year", type=int, default=None,
        help="First year to regenerate (default: the seed_year_range setting's start_year).",
    )
    parser.add_argument(
        "--end-year", type=int, default=None,
        help="Last year to regenerate, inclusive (default: the seed_year_range setting's end_year).",
    )
    parser.add_argument(
        "--location", type=str, default=None,
        help="Location code to generate for (default: the default_location_code setting).",
    )
    parser.add_argument(
        "--skip-panchangam", action="store_true",
        help="Skip regenerating base panchangam data (thithi/nakshatra/sunrise-sunset/kollavarsham).",
    )
    parser.add_argument(
        "--skip-events", action="store_true",
        help="Skip regenerating Santhigiri event occurrences.",
    )
    return parser.parse_args()


def _generate_panchangam(
    reference_repository: ReferenceRepositoryPort,
    repository: PanchangamRepositoryPort,
    settings: SettingsServicePort,
    etag_repository: EtagRepositoryPort,
    panchangam_service_for_etag_refresh: PanchangamService,
    unit_of_work: UnitOfWork,
    start_year: int,
    end_year: int,
    location: Location,
) -> None:
    """(Re)compute and write every day's panchangam data for
    ``[start_year, end_year]`` in one range-batched pass — see the module
    docstring for why this bypasses ``PanchangamGenerationService`` and calls
    ``get_panchangam_data_range`` directly instead."""
    # Imported lazily: pulls in the Skyfield/ephemeris stack only when a
    # generate actually runs, keeping the script's argument parsing/help fast.
    from app.core.calendar.panchangam import get_panchangam_data_range

    start_date = date(start_year, 1, 1)
    end_date = date(end_year, 12, 31)

    # +/-1 year padding covers get_panchangam_data_range's own Chandra Masa
    # month-boundary padding, which can spill into an adjacent year — same
    # reasoning as PanchangamGenerationService.generate_streaming's
    # tuning_by_year.
    tuning_by_year = {
        year: settings.get_astronomy_tuning(year)
        for year in range(start_year - 1, end_year + 2)
    }

    print(f"Computing panchangam data for {start_year}-{end_year} (batched range computation)...")
    clock = perf_counter()
    data_by_day = get_panchangam_data_range(
        start_date, end_date, location.latitude, location.longitude, location.timezone,
        lambda year: tuning_by_year[year],
    )
    print(f"  computed {len(data_by_day)} days in {perf_counter() - clock:.1f}s, writing...")

    for day, data in data_by_day.items():
        repository.upsert(data, location)  # does NOT commit

    years = sorted({d.year for d in data_by_day})
    refresh_etags(
        reference_repository, panchangam_service_for_etag_refresh, etag_repository,
        unit_of_work, years, [location],
    )  # commits

    print(f"  done: {len(data_by_day)} days written across {len(years)} years "
          f"({perf_counter() - clock:.1f}s total)")


async def _generate_event_occurrences(
    service: SanthigiriEventService, start_year: int, end_year: int
) -> None:
    print(f"Generating Santhigiri event occurrences for {start_year}-{end_year}...")
    try:
        async for event in service.generate_all_occurrences_streaming(start_year, end_year):
            if event.type == "progress":
                print(
                    f"  {event.completed}/{event.total} ({event.percent}%) - "
                    f"{event.year}/{event.event_id}: {event.status} ({event.count})",
                    end="\r",
                )
            else:
                print(
                    f"\n  done: {event.generated} generated, {event.skipped} skipped, "
                    f"{event.errors} errors across {len(event.years)} years"
                )
    except (IncompleteYearDataException, YearSpanTooLargeException) as exc:
        print(f"\n  FAILED: {exc}", file=sys.stderr)
        raise


async def _main() -> None:
    args = _parse_args()

    with Session(engine) as session:
        uow = SqlUnitOfWork(session)
        settings_repository = AppSettingRepository(session)
        settings = SettingsService(settings_repository, uow)
        panchangam_repository = PanchangamRepository(session=session)
        etag_repository = EtagRepository(session)
        reference_repository = ReferenceRepository(session)
        panchangam_service_for_etag_refresh = PanchangamService(panchangam_repository)

        start_year, end_year = settings.get_seed_year_range()
        if args.start_year is not None:
            start_year = args.start_year
        if args.end_year is not None:
            end_year = args.end_year

        location = (
            Location.from_code(args.location)
            if args.location is not None
            else Location.from_code(settings.get_default_location_code())
        )

        print(f"Regenerating {location.label} data for {start_year}-{end_year}")

        if not args.skip_panchangam:
            _generate_panchangam(
                reference_repository, panchangam_repository, settings, etag_repository,
                panchangam_service_for_etag_refresh, uow, start_year, end_year, location,
            )

        if not args.skip_events:
            event_service = SanthigiriEventService(
                reference_repository=reference_repository,
                event_repository=SanthigiriEventRepository(session=session),
                etag_repository=etag_repository,
                panchangam_repo=panchangam_repository,
                settings=settings,
                panchangam_service_for_etag_refresh=panchangam_service_for_etag_refresh,
                unit_of_work=uow,
            )
            await _generate_event_occurrences(event_service, start_year, end_year)

    print("Done.")


if __name__ == "__main__":
    asyncio.run(_main())
