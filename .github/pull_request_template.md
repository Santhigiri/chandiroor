## Description

<!-- Summarize the change and the motivation behind it. Link any related issues (e.g. "Closes #123"). -->

## Type of change

<!-- Check all that apply. -->

- [ ] Bug fix (non-breaking change that fixes an issue)
- [ ] New feature (non-breaking change that adds functionality)
- [ ] Breaking change (fix or feature that changes existing behavior)
- [ ] Astronomical calculation change (`core/astronomy/` or `core/calendar/`)
- [ ] New/changed Santhigiri event
- [ ] New API endpoint or schema change
- [ ] Documentation / tooling / chore

## Layer & architecture checklist

<!-- The codebase enforces a hard separation between the API, service, core, and db layers. See CLAUDE.md. -->

- [ ] Route handlers only parse params and delegate to `PanchangamService` (no domain/DB/astronomy logic)
- [ ] Astronomical calculations live in `core/astronomy/`; calendar aggregation in `core/calendar/`
- [ ] Pydantic models live in `schemas/` (not in `core/` or `db/`)
- [ ] Event definitions live in `utils/santhigiri_events.py`
- [ ] Typed enums (`Nakshatra`, `Thithi`, `Paksha`, `MalayalamMasa`) used instead of raw strings/ints

## Cache & data

<!-- Fill in if you changed computation logic or events. -->

- [ ] N/A — no computation or event changes
- [ ] Rebuilt the affected `data/panchangam_YYYY.pkl` files with the `cache_*.py` scripts
- [ ] Re-ran `db/migrate.py` and committed the refreshed `data/panchangam.db`
- [ ] Validated transition misses on startup (no missed Nakshatra/Thithi transitions logged)

## Testing

<!-- Describe how you verified the change. -->

- [ ] `pytest tests/` passes
- [ ] Added/updated tests for new astronomical calculations (cross-checked against a published Panchangam or Drik Panchang)
- [ ] Manually exercised the affected endpoint(s)

## Git workflow

- [ ] This PR targets `develop` (not `main`)
- [ ] PR title and description match the actual diff on the branch

## Additional notes

<!-- Screenshots, sample API responses, edge cases, or anything reviewers should know. -->
