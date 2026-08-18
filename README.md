# Panchangam API

A FastAPI server that computes the traditional Indian **Panchangam** (almanac) for any given date. Built for **Santhigiri Ashram** (Pothencode, Kerala, India), it returns astronomically precise sidereal values and overlays them with Santhigiri-specific events and observances.

For each day it computes:

- **Thithi** (lunar day) and **Nakshatra** (star), active at sunrise
- **Kollavarsham** (Malayalam / Kollam Era calendar) date
- **Sunrise / sunset** times and Thithi/Nakshatra **transition** times
- **Santhigiri significant dates** (festivals, birthdays, pilgrimages)

All calculations default to Santhigiri Ashram coordinates (**8.645° N, 76.938° E**) and the `Asia/Kolkata` timezone.

## How it works

Positions of the Sun and Moon are computed with [Skyfield](https://rhodesmill.github.io/skyfield/) using the NASA/JPL `de421.bsp` ephemeris, converted to **sidereal** longitudes via the Lahiri Ayanamsa (Swiss Ephemeris / `pyswisseph`). Ten years of daily values (2021–2030) are pre-computed and seeded into Postgres so responses are fast; any date missing from the database is computed live on demand.

## Project layout

```
main.py             # App entry: wires lifespan, CORS, and routers
features/           # One subpackage per feature: router.py + service.py + schemas.py
core/astronomy/     # Pure astronomical computation
core/calendar/      # Domain aggregation into calendar/Panchangam objects
core/deps.py        # Shared auth/DI dependencies (get_service, require_role, ...)
db/                 # Postgres persistence layer (SQLModel models + repositories)
services/           # Cross-feature services (ETag, settings) used by 3+ features
schemas/            # Pydantic models shared across features
utils/              # Cross-feature enums and helpers
data/               # Pre-computed yearly caches (panchangam_YYYY.pkl), source for db/sql seeds
de421.bsp           # JPL ephemeris file (required at startup)
```

See `CLAUDE.md` for the full architecture reference, including layer import boundaries and per-feature conventions.

## Running locally

Requires Python 3.10+.

```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Startup loads the pre-computed caches and takes a few seconds. The server is then available at `http://localhost:8000`.

### With Docker

```bash
docker build -t panchangam-api .
docker run -p 8000:8000 panchangam-api
```

## Endpoints

Interactive API docs are available at `http://localhost:8000/docs`.

| Method | Path | Description |
|---|---|---|
| `GET` | `/panchangam/?date_str=YYYY-MM-DD` | Full Panchangam for a single day |
| `GET` | `/panchangam/monthly?year=YYYY&month=MM` | Full Panchangam for every day in a month |

All parameters default to today's date, Santhigiri Ashram coordinates, and `Asia/Kolkata` timezone.

**Example:**

```bash
curl "http://localhost:8000/panchangam/?date_str=2026-07-01"
```

## Running tests

```bash
pytest tests/
```

## Tech stack

FastAPI · Uvicorn · Skyfield · pyswisseph · pytz · SQLModel
