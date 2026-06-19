# CLAUDE.md — panchangam-api

## Project Purpose

This is a FastAPI server that computes traditional Indian Panchangam (almanac) values for any given date. It is built specifically for **Santhigiri Ashram** (Pothencode, Kerala, India) and is the authoritative source of truth for daily and monthly Panchangam data used by the Ashram and its devotees.

The server computes astronomically precise sidereal values — Thithi (lunar day), Nakshatra (star constellation), Kollavarsham (Malayalam calendar), sunrise/sunset, and transition times — and overlays those values with Santhigiri-specific significant events and observances.

Default coordinates for all calculations: **8.645° N, 76.938° E** (Santhigiri Ashram). Default timezone: `Asia/Kolkata`.

---

## Git Workflow

- **Always start from `dev`** — before any work, checkout or pull the latest `dev` branch.
- **All changes merge to `dev` only** — feature branches must be created from `dev` and PRs must target `dev`.
- **Never touch `main`** — do not commit to, push to, or merge into `main` directly. `main` is promoted to only by the project maintainers.

```bash
git checkout dev
git pull origin dev
git checkout -b feature/<your-feature-name>
# ... make changes ...
git push -u origin feature/<your-feature-name>
# Open PR targeting dev
```

---

## Architecture Overview

The codebase uses a **feature-based architecture** with a hard separation between business logic and the API layer. This is a non-negotiable constraint.

```
panchangam-api/
├── main.py                     # App factory: wires lifespan, CORS, routers
├── api/routes/                 # HTTP boundary only — thin, dumb handlers
├── core/
│   ├── astronomy/              # Pure astronomical computation (no HTTP, no Pydantic responses)
│   ├── calendar/               # Domain aggregation: combines astronomy into calendar objects
│   └── constants.py            # Shared domain constants (names, coordinates, timezone)
├── schemas/                    # Pydantic request/response models
├── utils/                      # Enums, cache tooling, event definitions
│   ├── lifespan.py             # Startup: loads 10-year pickle cache into PANCHANGAM_CACHE
│   ├── cache_crud.py           # Reads/writes pickle files on disk
│   ├── cache_common_events.py  # Populates simple (condition-based) Santhigiri events into cache
│   ├── cache_navapoojitham.py  # Populates Navapoojitham (Guru birthday) into cache
│   ├── cache_sishya_bday.py    # Populates Shishyapoojitha birthday into cache
│   ├── cache_chothi_theerthayathra.py  # Populates pilgrimage dates into cache
│   └── santhigiri_events.py    # Event definitions and matching conditions
└── data/panchangam_YYYY.pkl    # Pre-computed yearly caches (2021–2030)
```

### Why this structure exists

**`core/astronomy/`** contains pure astronomical functions. They take `datetime` and coordinate/timezone values as inputs and return floats, ints, or strings. They have zero knowledge of HTTP, Pydantic models, or cache state. They are independently testable.

**`core/calendar/`** aggregates astronomy into meaningful calendar objects. `panchangam.py::get_panchangam_data()` is the single orchestration point: it calls into `core/astronomy/`, builds a `PanchangamData` Pydantic object, and returns it. `monthly_panchangam.py` iterates over a calendar month, checks `PANCHANGAM_CACHE`, and falls back to live computation if a date is missing.

**`api/routes/`** is the HTTP boundary. Route handlers parse and validate query parameters, call into `core/calendar/`, and return the result. They must not contain domain logic, computations, or direct astronomy calls.

**`schemas/`** holds Pydantic models. Request schemas live here (query param validation with defaults). The primary response schema is `PanchangamData` in `schemas/panchangam_data.py` — it is also the type stored in the runtime cache.

**`utils/`** holds domain enums (`Nakshatra`, `Thithi`, `Paksha`, `MalayalamMasa`) and all cache management tooling. Cache scripts (`cache_*.py`) are offline maintenance utilities — they are run manually to rebuild the pickle files, not called at runtime.

---

## Mandatory Conventions

Follow these rules without exception.

### Layer import boundaries

- Route handlers in `api/routes/` must only parse HTTP params and delegate to `core/calendar/`. They must not call `core/astronomy/` directly.
- `core/astronomy/` functions must not import from `api/`, `schemas/`, or `utils/lifespan.py`.
- `core/calendar/` functions must not import from `api/`.
- Pydantic models belong in `schemas/`. Do not define response models inside `core/` or `utils/`.

### Business logic placement

- All astronomical calculations go in `core/astronomy/`.
- All calendar/domain aggregation goes in `core/calendar/`.
- Event definitions go in `utils/santhigiri_events.py`.
- Cache management scripts go in `utils/cache_*.py`.
- No business logic may live inside a route handler.

### Adding a new astronomical value

1. Implement the raw calculation function in the appropriate `core/astronomy/` file.
2. Call it from `core/calendar/panchangam.py::get_panchangam_data()`.
3. Add the field to `schemas/panchangam_data.py::PanchangamData`.
4. The route handler picks it up automatically — do not touch the route.

### Adding a new Santhigiri event

1. Define the event in `utils/santhigiri_events.py` with the appropriate `EventCondition`.
2. If condition-based (fixed English/Malayalam date, Nakshatra, Thithi, or Pournami), add it to `_COMMON_EVENTS` in `utils/cache_common_events.py`.
3. If it uses "last occurrence" logic (like Navapoojitham or Shishyapoojitha birthday), write a dedicated `utils/cache_<event_name>.py` following the pattern in `cache_navapoojitham.py`.
4. Run the appropriate cache script offline to rebuild the pickle files.
5. The event will appear in `PanchangamData.santhigiri_significant_dates` in the API response.

### Adding a new API endpoint

1. Create a new file under `api/routes/<feature>.py`. Do not add endpoints to an existing route file unless they are closely related.
2. Define request params as a Pydantic `BaseModel` in `schemas/`.
3. Register the new router in `main.py` using `app.include_router(...)`.
4. All domain logic the endpoint needs must be implemented in `core/`.

### Enum usage

Use the typed Python enums (`Nakshatra`, `Thithi`, `Paksha`, `MalayalamMasa`) defined in `utils/` for all internal domain logic. Never use raw strings or bare integer IDs when a typed enum is available. All enums support bilingual names (`.en`, `.ml`).

---

## Key Domain Concepts

### Panchangam

A Panchangam is the traditional Indian almanac. Each day is described by five elements (pancha = five, anga = limb): Vara (weekday), Thithi (lunar day), Nakshatra (star), Yoga, and Karana. This implementation focuses on Thithi and Nakshatra as the primary observances for Santhigiri.

### Thithi (Lunar Day)

The Moon's elongation from the Sun, divided into 30 segments of 12° each.

```
elongation = (moon_sidereal_longitude - sun_sidereal_longitude) % 360
thithi_id  = floor(elongation / 12) + 1   # 1–30
```

Thithis 1–15 are Shukla Paksha (waxing moon). Thithis 16–30 are Krishna Paksha (waning moon). Thithi 15 is Pournami (full moon). Thithi 30 is Amavasya (new moon).

**Critical:** The Thithi for a day is the Thithi active at **sunrise**, not midnight.

### Nakshatra (Star Constellation)

The Moon's sidereal longitude divided into 27 segments of 13°20' (≈13.333°) each.

```
nakshatra_id = floor(moon_sidereal_longitude / (360/27))   # 0-indexed; +1 for 1-indexed id
```

The 27 Nakshatras begin with Aswathy (1) and end with Revathi (27). Names follow the Kerala/Malayalam convention.

**Critical:** The Nakshatra for a day is the Nakshatra active at **sunrise**.

### Sidereal Astronomy and Ayanamsa

All longitude calculations are sidereal (relative to fixed stars), not tropical (relative to the vernal equinox). The conversion is:

```
sidereal_longitude = tropical_longitude - ayanamsa
```

The Lahiri Ayanamsa (the standard for Indian Jyotisha) is computed using `pyswisseph`. This is handled in `core/astronomy/ayanamsa.py`.

### Kollavarsham (Malayalam Calendar)

The Kollam Era calendar used in Kerala. The Malayalam month is determined by the Sun's sidereal raasi (zodiac sign) at sunset. The month changes when the Sun moves into a new raasi.

```
kollam_year = english_year - 824   # if current raasi >= Chingam (index 4)
kollam_year = english_year - 825   # otherwise
```

The Malayalam day is computed by walking backwards through sunsets to find when the current raasi began. Implemented in `core/calendar/kollavarsham.py`.

### Nazhika (Traditional Time Unit)

1 Nazhika = 24 minutes. A full day = 60 Nazhikas. The field `nazhika_from_sunrise` in `PanchangamData` represents how many Nazhikas of the current Nakshatra remain from sunrise. This is used to determine which day an event falls on when a Nakshatra transitions near sunrise (the "7.5 Nazhika rule").

### Transitions

A Thithi or Nakshatra rarely spans exactly one calendar day. Transitions are detected using Skyfield's `find_discrete()` function, which searches a time window for discrete state changes. The search window for each day covers the previous day, current day, and next day, then filters to transitions that overlap the current day. This is the mechanism in `core/astronomy/thithi_transition.py` and `core/astronomy/nakshatra_transition.py`.

The step size for the search (`step_days`) is critical for accuracy. The nakshatra step is configured via `NAKSHATRA_TRANSITION_STEP_DAYS` in `core/constants.py`. The value `0.01` works for most years but may need adjustment (see the comment in `constants.py` for 2028, which requires `0.05`).

### Pournami (Full Moon)

Pournami detection is not simply "is today's Thithi Pournami?" because a Thithi can span across midnight. The implementation checks that:

1. The Thithi at 23:59:59 of **today** is Pournami, AND
2. The Thithi at 23:59:59 of **yesterday** was not Pournami.

This ensures Pournami is attributed to exactly one calendar day. Implemented in `core/astronomy/pournami.py`.

### Santhigiri Events

Santhigiri Ashram observes events tied to specific dates in either the English or Malayalam calendar, or to astronomical conditions (Nakshatra, Thithi, Pournami). Events are modeled as `SanthigiriEvent` with an `EventCondition` that specifies the matching criteria. Events are pre-computed offline and stored in the pickle cache in `PanchangamData.santhigiri_significant_dates`.

Some events use a "last occurrence" rule: for example, Navapoojitham falls on the last Chothi Nakshatra in the month of Chingam (with the 7.5 Nazhika rule to handle edge cases at sunrise). This logic is too dynamic to reduce to a simple `EventCondition` and lives in dedicated cache scripts.

---

## Tech Stack

| Dependency | Purpose |
|---|---|
| `fastapi[standard]` | HTTP framework and request validation |
| `uvicorn` | ASGI server |
| `skyfield` | High-precision astronomical calculations (positions, `find_discrete`) |
| `pyswisseph` | Lahiri Ayanamsa computation via Swiss Ephemeris |
| `pytz` | Timezone handling |
| `pandas` | Data manipulation in cache utilities |
| `de421.bsp` | NASA/JPL ephemeris file (16.8 MB) loaded by Skyfield for Sun/Moon/Earth positions |

The `de421.bsp` file must be present in the project root at startup. It is a binary data file — do not delete it or add it to `.gitignore`.

---

## Running the Project

### Local development

```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

On startup, the server loads 10 years of pre-computed data from `data/panchangam_YYYY.pkl` (2021–2030). Startup takes a few seconds. Watch for cache validation output — the server logs any missed Nakshatra or Thithi transitions.

### Docker

```bash
docker build -t panchangam-api .
docker run -p 8000:8000 panchangam-api
```

The container exposes port 8000 and runs `uvicorn main:app --host 0.0.0.0 --port 8000`.

### Endpoints

- `GET /panchangam/?date_str=YYYY-MM-DD` — returns full Panchangam for a single day
- `GET /panchangam/monthly?year=YYYY&month=MM` — returns full Panchangam for every day in the month

All parameters default to today's date, Santhigiri Ashram coordinates, and `Asia/Kolkata` timezone.

---

## Running Tests

```bash
pytest tests/
```

Current coverage:

- `tests/test_is_pournami.py` — 24 parametrized test cases verifying full moon detection against known dates for 2022 and 2026.
- `tests/test_panchangam.py` — skeleton (not yet implemented).

When adding new astronomical calculations, add parametrized tests to `tests/` that verify against known Panchangam dates. Cross-check expected values against published physical Panchangams or the Drik Panchang reference.

---

## Caching Strategy

This is the most performance-critical aspect of the system. Understand it before making any changes.

### Runtime cache (`PANCHANGAM_CACHE`)

A module-level `Dict[date, PanchangamData]` defined in `utils/lifespan.py`. It is populated at startup via the FastAPI lifespan context manager, which loads all `data/panchangam_YYYY.pkl` files (currently 2021–2030, ~3650 entries). All monthly endpoint calls read from this cache. If a date is missing, `get_panchangam_data()` computes it live and stores it back.

This cache makes the monthly endpoint essentially free — it serves pre-computed data without any Skyfield calls.

### Function-level LRU caches

Several functions in `core/astronomy/` and `core/calendar/` are decorated with `@lru_cache`. Key examples:

- `get_sunrise_sunset()` in `core/astronomy/sunrise_sunset.py`
- `get_thithi_transition_by_date()` in `core/astronomy/thithi_transition.py`
- `get_kollavarsham_date()` and `get_sunset_raasi()` in `core/calendar/kollavarsham.py`
- `get_sun_sidereal_longitude()` in `core/astronomy/calculations.py`

These are critical for the transition-detection logic, which calls the same function for the previous day, current day, and next day. Without LRU caching these would be redundantly recalculated.

### Offline cache management (pickle files)

The `data/panchangam_YYYY.pkl` files are pre-computed offline using scripts in `utils/`:

1. `cache_crud.py::buildcache(year)` — computes all 365 days for a year and writes a pickle file.
2. `cache_common_events.py::cache_common_events()` — reads all pickle files, matches simple event conditions, and rewrites them with `santhigiri_significant_dates` populated.
3. `cache_navapoojitham.py::cache_navapoojitham()` — same for Guru birthday.
4. `cache_sishya_bday.py::cache_sishya_bday()` — same for Shishyapoojitha birthday.
5. `cache_chothi_theerthayathra.py::cache_chothi_theerthayathra()` — same for Chothi pilgrimage dates.

**When to rebuild:** If you change computation logic in `core/astronomy/` or `core/calendar/`, or add/modify Santhigiri events, regenerate the pickle files offline and commit them. The server reads but does not write pickle files at runtime.

### Cache rebuild order

1. Run `buildcache(year)` for each affected year.
2. Run event caching scripts in any order — they are independent of each other.
3. Verify startup logs show zero transition misses before committing the new pickle files.

---

## Ephemeris File

`de421.bsp` is loaded at module import time in `core/astronomy/ephemeris.py` as a module-level singleton:

```python
ephem = load("de421.bsp")
earth = ephem["earth"]
sun   = ephem["sun"]
moon  = ephem["moon"]
ts    = api.load.timescale()
```

Importing anything from `core/astronomy/` triggers this load. Do not move the load call into individual functions — it is intentionally a module-level singleton. In tests, mock `core.astronomy.ephemeris` if you need to avoid loading the ephemeris.

---

## Known Issues and Active Work

- `core/calendar/santhigiri_significant_dates.py` is an empty placeholder. The live computation path (`get_santhigiri_significant_dates_without_occurances`) is commented out in `panchangam.py` — dates come from the cache only.
- `core/calendar/panchangam.py::get_panchangam()` (the dict-returning version) is a legacy function superseded by `get_panchangam_data()`. Do not add new callers of `get_panchangam()`.
- The daily endpoint (`GET /panchangam/`) accepts `latitude`, `longitude`, and `timezone` as query parameters but does not currently pass them through to `get_panchangam_data()` — it uses hardcoded defaults. This is a known inconsistency.
- `NAKSHATRA_TRANSITION_STEP_DAYS` is `0.01` for 2021–2027 and 2029–2030. For 2028 it must be `0.05`. This is a fragile per-year constant; treat any change with caution and validate with the transition miss checker on startup.

---

## What Not To Do

- Do not put business logic in route handlers. If a route handler is doing anything beyond parsing params and calling a core function, move the logic to `core/`.
- Do not call `core/astronomy/` functions directly from route handlers.
- Do not define new Pydantic models inside `core/` modules.
- Do not modify the pickle files by hand. Always use the cache scripts.
- Do not add new event definitions in `core/` or `api/`. All event definitions belong in `utils/santhigiri_events.py`.
- Do not change `NAKSHATRA_TRANSITION_STEP_DAYS` without re-validating every year's cache with the transition miss checker.
- Do not assume the daily endpoint passes user-supplied coordinates to the computation — check the route handler first.
- Do not hardcode Malayalam or Sanskrit names as string literals in new code. Use `NAKSHATRA_NAMES`, `THITHI_NAMES`, or the appropriate enum from `utils/`.
