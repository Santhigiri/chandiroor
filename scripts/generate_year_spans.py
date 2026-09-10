"""
Regenerate panchangam data and Santhigiri event occurrences for the database's
configured "available year span" (the ``seed_year_range`` admin setting,
2021-2030 by default) directly against Postgres — no running API server or
HTTP round trip required.

This is the offline counterpart to the admin `/generate` / `/events/generate`
endpoints: it builds the same `PanchangamGenerationService` /
`SanthigiriEventService` used by those routes (see `app/api/deps.py` for the
reference wiring this mirrors) and drives their streaming generators directly,
printing one progress line per day/year to stdout exactly like the NDJSON
stream a client would read. Intended to be run by hand or from a scheduled/
manual GitHub Actions workflow (see `.github/workflows/generate-year-spans.yml`)
to keep the seeded range's data current after an astronomy/calendar code
change, without needing an admin to click through the UI.

Usage:
    DATABASE_URL=postgresql://... python scripts/generate_year_spans.py
    DATABASE_URL=postgresql://... python scripts/generate_year_spans.py --start-year 2021 --end-year 2030
    DATABASE_URL=postgresql://... python scripts/generate_year_spans.py --skip-events
    DATABASE_URL=postgresql://... python scripts/generate_year_spans.py --location tvm

By default, the year range is read from the `seed_year_range` setting stored
in the database; pass --start-year/--end-year to override it. Panchangam data
is (re)computed one calendar year at a time (each year is its own call to
`PanchangamGenerationService.generate_streaming`, the same day-by-day iterator
the `/generate` endpoint uses) so the run stays within the admin-configured
`max_generate_span_days` cap regardless of how wide the overall span is.
Santhigiri event occurrences are then regenerated for every event across the
same range via `SanthigiriEventService.generate_all_occurrences_streaming`,
which requires the panchangam data for the full range to already be present.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import date

from sqlmodel import Session

from app.db.database import engine
from app.db.reference_repository import ReferenceRepository
from app.db.unit_of_work import SqlUnitOfWork
from app.features.etag.repository import EtagRepository
from app.features.panchangam.generation_service import PanchangamGenerationService, SpanTooLarge
from app.features.panchangam.repository import PanchangamRepository
from app.features.panchangam.schemas.panchangam_generation import PanchangamGenerateRequest
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


async def _generate_panchangam(
    service: PanchangamGenerationService, start_year: int, end_year: int, location: Location
) -> None:
    for year in range(start_year, end_year + 1):
        req = PanchangamGenerateRequest(start_date=date(year, 1, 1), end_date=date(year, 12, 31))
        print(f"Generating panchangam data for {year}...")
        try:
            async for event in service.generate_streaming(req, location):
                if event.type == "progress":
                    print(
                        f"  [{year}] {event.completed}/{event.total} "
                        f"({event.percent}%) - {event.current_date}",
                        end="\r",
                    )
                else:
                    print(f"\n  [{year}] done: {event.count} days written")
        except SpanTooLarge as exc:
            print(f"\n  [{year}] FAILED: {exc}", file=sys.stderr)
            raise


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
            generation_service = PanchangamGenerationService(
                reference_repository=reference_repository,
                repository=panchangam_repository,
                settings=settings,
                etag_repository=etag_repository,
                panchangam_service_for_etag_refresh=panchangam_service_for_etag_refresh,
                unit_of_work=uow,
            )
            await _generate_panchangam(generation_service, start_year, end_year, location)

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
