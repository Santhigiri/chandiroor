# Panchangam API

A FastAPI server that computes the traditional Indian **Panchangam** (almanac) for any given date. Built for **Santhigiri Ashram** (Pothencode, Kerala, India), it returns astronomically precise sidereal values and overlays them with Santhigiri-specific events and observances.

For each day it computes:

- **Thithi** (lunar day) and **Nakshatra** (star), active at sunrise
- **Kollavarsham** (Malayalam / Kollam Era calendar) date
- **Sunrise / sunset** times and Thithi/Nakshatra **transition** times
- **Santhigiri significant dates** (festivals, birthdays, pilgrimages)

All calculations default to Santhigiri Ashram coordinates (**8.645° N, 76.938° E**) and the `Asia/Kolkata` timezone.

## How it works

Positions of the Sun and Moon are computed with [Skyfield](https://rhodesmill.github.io/skyfield/) using the NASA/JPL `de421.bsp` ephemeris, converted to **sidereal** longitudes via the Lahiri Ayanamsa (Swiss Ephemeris / `pyswisseph`). Ten years of daily values (2021–2030) are pre-computed and seeded into Postgres so responses are fast; any date missing from the database is computed live on demand and not written back.

## Project layout

```
app/
├── main.py                # App factory: wires lifespan, CORS, and routers
├── api/deps.py            # Shared auth/DI dependencies (get_*_service, require_role, ...)
├── features/               # One subpackage per feature: router.py + service.py + schemas.py
├── core/
│   ├── astronomy/          # Pure astronomical computation + its own de421.bsp (fenced off by .importlinter)
│   ├── calendar/           # Domain aggregation into PanchangamData
│   ├── kollavarsham/       # Malayalam (Kollam Era) calendar computation
│   ├── events/             # Event-condition → occurrence-date resolution
│   └── ports/              # Cross-feature Protocols (UnitOfWork, SettingsServicePort, ...)
├── db/                     # Postgres persistence layer (SQLModel models + repositories)
├── schemas/                # Pydantic models shared across features
└── utils/                  # Cross-feature enums and helpers
```

See `CLAUDE.md` for the full architecture reference, including layer import boundaries and per-feature conventions.

## Running locally

Requires Python 3.12.

```bash
pip install -r requirements.txt
cp .env.example .env   # then fill in your Neon DATABASE_URL
uvicorn main:app --reload --port 8000
```

`DATABASE_URL` must be set or startup fails fast. Startup only ensures the Postgres schema exists (`init_db()`); seed it once by applying `db/sql/01_schema.sql` and `db/sql/02_seed.sql` via `psql` (see `db/sql/README.md`). The server is then available at `http://localhost:8000`.

### With Docker

```bash
docker build -t panchangam-api .
docker run -p 8000:8000 panchangam-api
```

## Endpoints

Interactive API docs are available at `http://localhost:8000/docs`.

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/panchangam/day?day=YYYY-MM-DD` | Compact Panchangam for a single day |
| `GET` | `/api/v1/panchangam/instant?day=YYYY-MM-DD&time=HH:MM` | Compact Panchangam active at an arbitrary date/time/location instant |
| `GET` | `/api/v1/panchangam/month?year=YYYY&month=MM` | Compact Panchangam for every day in a month |
| `GET` | `/api/v1/panchangam/year?year=YYYY` | Compact Panchangam for every day in a year (ETag-validated) |

All parameters default to today's date, Santhigiri Ashram coordinates, and `Asia/Kolkata` timezone. See `CLAUDE.md` for the full endpoint list, including reference datasets, event-definition CRUD, and auth.

**Example:**

```bash
curl "http://localhost:8000/api/v1/panchangam/day?day=2026-07-01"
```

## Running tests

```bash
pytest tests/
```

## Tech stack

FastAPI · Uvicorn · Skyfield · pyswisseph · pytz · SQLModel
