# CLAUDE.md — panchangam-api

## Project Purpose

This is a FastAPI server that computes traditional Indian Panchangam (almanac) values for any given date. It is built specifically for **Santhigiri Ashram** (Pothencode, Kerala, India) and is the authoritative source of truth for daily and monthly Panchangam data used by the Ashram and its devotees.

The server computes astronomically precise sidereal values — Thithi (lunar day), Nakshatra (star constellation), Kollavarsham (Malayalam calendar), sunrise/sunset, and transition times — and overlays those values with Santhigiri-specific significant events and observances.

Default coordinates for all calculations: **8.645° N, 76.938° E** (Santhigiri Ashram). Default timezone: `Asia/Kolkata`.

---

## Git Workflow

- **Always start from `develop`** — before any work, checkout or pull the latest `develop` branch.
- **All changes merge to `develop` only** — feature branches must be created from `develop` and PRs must target `develop`.
- **Never touch `main`** — do not commit to, push to, or merge into `main` directly. `main` is promoted to only by the project maintainers.
- **Keep the PR title and description in sync with the diff** — before merging a PR, re-check that its title and description still accurately describe the actual changes on the branch (commits are often added after the PR was opened). Update both if they've drifted before merging.

```bash
git checkout develop
git pull origin develop
git checkout -b feature/<your-feature-name>
# ... make changes ...
git push -u origin feature/<your-feature-name>
# Open PR targeting develop
```

---

## Architecture Overview

The codebase uses a **feature-based (vertical-slice) architecture** with a hard separation between business logic and the API layer. This is a non-negotiable constraint.

Each feature owns its own router, service, and request/response schemas under `features/<name>/`. Only pieces that are genuinely shared across *multiple* features — the persistence layer (`db/`), the astronomy/calendar domain logic (`core/`), and cross-cutting schemas (`schemas/`) — live outside a feature folder. There is no `services/` folder: every feature's service lives in that feature's own `service.py`, and a service needed by 3+ other features' services is still consumed cross-feature only via a `Protocol` in `core/ports/` (see "Ports & adapters" below) — never by another feature importing its `service.py` module directly.

Everything below lives under `app/` (the on-disk package root). Paths elsewhere
in this document are given relative to `app/` unless a leading `app/` is shown.
The pure astronomical layer lives at `app/core/astronomy/` and is fenced off by
an import-linter contract (see "The astronomy package" below).

```
panchangam-api/
├── .importlinter                # import-linter contract fencing app/core/astronomy/ off from the rest of app/
└── app/
    ├── main.py                     # App factory: wires lifespan, CORS, routers
    ├── api/
    │   └── deps.py                 # Shared Depends: get_*_service, get_location, get_current_principal, require_role — also where every port gets bound to its concrete adapter
    ├── features/                   # One subpackage per feature — the HTTP boundary + orchestration for that feature
    │   ├── panchangam/                  # Migrated to ports & adapters (see "Ports & adapters" below)
    │   │   ├── router.py               # Compact panchangam reads (day/instant/month/year/sunrise-sunset), mounted at /api/v1
    │   │   ├── generation_router.py    # POST /api/v1/panchangam/generate (admin)
    │   │   ├── service.py              # PanchangamService — reads through PanchangamRepositoryPort; live-computation fallback on a DB miss
    │   │   ├── generation_service.py   # PanchangamGenerationService — write path, depends on the port + UnitOfWork, commits with an ETag refresh
    │   │   ├── ports.py                 # PanchangamRepositoryPort (Protocol) — no new DTOs, see below
    │   │   ├── repository.py            # PanchangamRepository — concrete adapter implementing the port against SQLModel
    │   │   └── schemas/                # Panchangam-only request/response schemas (one file per schema, as before)
    │   ├── santhigiri_events/           # Migrated to ports & adapters (see "Ports & adapters" below)
    │   │   ├── ports.py      # SanthigiriEventsRepositoryPort (Protocol) + DTOs (SanthigiriEventGet/Create/Udpate) + EventNotFoundException
    │   │   ├── repository.py # SanthigiriEventRepository — concrete adapter implementing the port against SQLModel
    │   │   ├── router.py     # Admin CRUD + occurrence-generation endpoints for editable Santhigiri event definitions
    │   │   ├── service.py    # SanthigiriEventService — depends on the port + UnitOfWork, not the concrete adapter
    │   │   └── schemas.py    # Flat request/response schemas (HTTP boundary shape, distinct from ports.py's nested DTOs)
    │   ├── auth/                        # Migrated to ports & adapters (the canonical example — see below)
    │   │   ├── ports.py           # AuthRepositoryPort (Protocol) + DTOs (UserGet/Create/Update/WithCredentials) + UserNotFoundException
    │   │   ├── auth_repository.py # AuthRepository — concrete adapter implementing the port against SQLModel
    │   │   ├── router.py    # login / refresh / me / users / Google sign-in (JWT auth)
    │   │   ├── service.py   # AuthService — depends on AuthRepositoryPort + UnitOfWork, not the concrete adapter
    │   │   └── schemas.py
    │   ├── guruvani/                    # Migrated to ports & adapters, same shape as auth
    │   │   ├── ports.py      # GuruvaniRepositoryPort (Protocol) + DTOs (GuruvaniGet/Create/Update) + GuruvaniNotFoundException
    │   │   ├── repository.py # GuruvaniRepository — concrete adapter implementing the port against SQLModel
    │   │   ├── router.py
    │   │   ├── service.py    # GuruvaniService — depends on GuruvaniRepositoryPort + UnitOfWork, not the concrete adapter
    │   │   └── schemas.py
    │   ├── reference/                   # No ports.py of its own — see core/ports/reference_repository.py below
    │   │   └── router.py     # thithi/nakshatra/masa/events/locations reads, mounted under the /panchangam URL
    │   │                      # prefix for backward compatibility even though it's its own feature package.
    │   │                      # Depends on core/ports/reference_repository.py's ReferenceRepositoryPort (bound to
    │   │                      # db/reference_repository.py::ReferenceRepository in api/deps.py) and on
    │   │                      # features/etag/service.py's build_enum_payload/conditional_json_response — no
    │   │                      # service.py of its own, same as how panchangam/router.py calls etag/service.py
    │   │                      # directly for its /year endpoint.
    │   ├── settings/                    # Migrated to ports & adapters — service.py now lives here too, see below
    │   │   ├── ports.py      # AppSettingRepositoryPort (Protocol) + AppSettingGet DTO
    │   │   ├── repository.py # AppSettingRepository — concrete adapter implementing the port against SQLModel
    │   │   ├── router.py     # Admin CRUD for app_setting
    │   │   └── service.py    # SettingsService — reads/writes app_setting; consumed cross-feature only via
    │   │                      # core/ports/settings_service.py's SettingsServicePort, never imported directly
    │   └── etag/                        # Migrated to ports & adapters — the payload/ETag functions now live in service.py too
    │       ├── ports.py      # EtagRepositoryPort (Protocol) — no DTO, the boundary value is a bare ETag string
    │       ├── repository.py # EtagRepository — concrete adapter implementing the port against SQLModel (dataset_etag table)
    │       └── service.py    # Canonical payload builders + ETag compute/refresh (conditional_json_response, refresh_etags, …).
    │                          # Plain functions, not a class — every router/service that needs them imports this module
    │                          # directly (they're already parametrized by EtagRepositoryPort/UnitOfWork, so there's nothing
    │                          # to abstract behind a port). Depends on features/etag/ports.py's EtagRepositoryPort + UnitOfWork
    │                          # for ETag persistence, never the concrete adapter — and on core/ports/panchangam_service.py's
    │                          # PanchangamServicePort (injected by the caller) to rebuild a year's payload, never importing
    │                          # features.panchangam.service/repository directly. build_enum_payload takes a
    │                          # core/ports/reference_repository.py's ReferenceRepositoryPort, never importing
    │                          # db.reference_repository directly.
    ├── db/                         # Postgres persistence layer (SQLModel) — unchanged by the feature-folder move
    │   ├── database.py             # Engine (reads DATABASE_URL from env), session factory, init_db()
    │   ├── unit_of_work.py         # SqlUnitOfWork — the one concrete UnitOfWork adapter (see "Ports & adapters" below)
    │   ├── reference_repository.py # ReferenceRepository — concrete adapter implementing ReferenceRepositoryPort
    │   │                            # (core/ports/reference_repository.py) against SQLModel; reads the enum/reference
    │   │                            # datasets (thithi, nakshatra, masa, events, locations)
    │   ├── kollavarsham_repository.py
    │   ├── seed.py                 # Seeds lookup tables (Thithi, Nakshatra, Paksha, MalayalamMasa, Location, SanthigiriEvent)
    │   ├── sql/                    # Standalone schema + seed SQL applied to Neon/Postgres via psql
    │   └── models/                 # SQLModel table definitions
    ├── core/                        # Unchanged by the feature-folder move — shared by every feature
    │   ├── astronomy/              # Pure astronomical functions + vendored enums + de421.bsp — fenced off by .importlinter (see "The astronomy package" below)
    │   ├── calendar/               # Domain aggregation: panchangam.py combines core/astronomy/ + core/kollavarsham/ + core/events/ into a PanchangamData
    │   ├── kollavarsham/           # Malayalam-calendar (Kollavarsham) computation: kollavarsham.py, kollavarsham_models.py, and the MalayalamMasa enum under enums/masa.py
    │   ├── events/                 # Event-condition → occurrence-date resolution: event_occurrences.py (year-range) + significant_dates.py (single-day live-fallback matcher)
    │   ├── ports/
    │   │   ├── unit_of_work.py     # UnitOfWork (Protocol) — the transaction boundary every migrated feature's service depends on
    │   │   ├── settings_service.py # SettingsServicePort (Protocol) — the typed-getter subset of SettingsService that
    │   │   │                        # other features' service.py modules depend on instead of importing SettingsService directly
    │   │   ├── panchangam_service.py # PanchangamServicePort (Protocol) — the get_by_year subset of PanchangamService that
    │   │   │                          # features/etag/service.py depends on instead of importing PanchangamService directly
    │   │   └── reference_repository.py # ReferenceRepositoryPort (Protocol) — list_thithis/list_nakshatras/list_masas/
    │   │                                # list_locations/list_events, the subset of db/reference_repository.py::ReferenceRepository
    │   │                                # that features/etag/service.py and features/reference/router.py depend on. Lives here
    │   │                                # rather than features/reference/ports.py because ReferenceRepository is a genuine
    │   │                                # cross-feature dependency — also consumed directly by features/etag/service.py — same
    │   │                                # reasoning as SettingsServicePort.
    │   ├── security.py             # Password hashing + JWT mint/decode (no HTTP)
    │   └── config.py               # Settings (JWT_SECRET_KEY etc.) via pydantic-settings
    ├── schemas/                     # Only schemas used by 2+ features, or by db/ or core/, stay here
    │   ├── location.py              # LocationInfo — used by features/panchangam/repository.py, core/calendar/, and multiple features
    │   ├── panchangam_data.py       # PanchangamData — returned by features/panchangam/repository.py and core/calendar/panchangam.py
    │   ├── compact_panchangam_data.py  # Used by features/etag/service.py, db/reference_repository.py, and multiple features
    │   └── app_setting.py           # Used by features/settings/service.py *and* features/santhigiri_events/service.py
    └── utils/                      # Domain enums, roles, and cross-cutting helpers with no feature to own them
        ├── roles.py                # Role enum (anonymous < user < admin) for authorization
        ├── lifespan.py             # Startup: init_db() ensures the Postgres schema exists (no runtime seeding)
        └── santhigiri_events.py    # Event definitions and matching conditions — stays here (not features/) since
                                     # core/calendar/, core/events/, and db/ import it directly and must not depend on features/
```

### The astronomy package

`core/astronomy/` (i.e. `app/core/astronomy/`) is a self-contained computation
layer with **zero dependency on the rest of `app/`** — it has no imports from
`schemas/`, `db/`, `features/`, `api/`, `utils/`, `core/calendar/`,
`core/kollavarsham/`, `core/events/`, `core/ports/`, `core/config.py`, or
`core/security.py`. This is not just a
convention: the `.importlinter` contract `astronomy-isolation` (a `forbidden`
contract listing every sibling under `app/`) fails the build if any module
under `core/astronomy/` imports one of them. Run it locally with
`lint-imports` (`pip install -r requirements-dev.txt`); CI runs it on every
push/PR to `develop` via `.github/workflows/lint.yml`. **If you add a new
`app/core/<sibling>` package, add it to `forbidden_modules` in `.importlinter`.**

It holds the pure astronomical functions (Thithi, Nakshatra, sunrise/sunset,
ayanamsa, transitions): they take `datetime` and coordinate/timezone values as
inputs and return floats, ints, or plain dataclasses/Pydantic value objects.
They have zero knowledge of HTTP or persistence, and are independently
testable. It vendors its own copies of the domain enums it needs
(`core/astronomy/enums/nakshatra.py`, `thithi.py`, `paksha.py` — plain stdlib
`Enum` classes) and its own `constants.py` (Santhigiri's default
coordinates/timezone, `NAKSHATRA_BOUNDARIES`, `NAKSHATRA_TRANSITION_STEP_DAYS`).
The rest of `app/` imports these same enums from `app.core.astronomy.enums.*`
rather than duplicating them — there is no separate
`app/utils/nakshatra.py`/`thithi.py`/`paksha.py`. The enums carry only
structural data — `id`, plus `paksha`/`day` on `Thithi` — and their `.name` is
the stable slug used everywhere internally. They hold **no display text**:
localized (`en`/`ml`) names live in the DB reference tables
(`thithi`/`nakshatra`/`paksha`/`malayalam_masa`), whose `ml`/`en` columns are
nullable and populated only by `db/sql/02_seed.sql` on real databases.
`db/seed.py` (test/dev seeding) fills just the structural columns from the
enums and leaves `ml`/`en` NULL; nothing in the app reads display text off
those rows outside the `/panchangam/thithi|nakshatra|masa` reference endpoints.
Additional languages are added on the DB side, not in code.
`core/astronomy/ephemeris.py` resolves `de421.bsp` (bundled alongside it, at
`app/core/astronomy/de421.bsp`) relative to its own module location via a
`skyfield.api.Loader`, not the process's current working directory — so it
loads correctly regardless of where the app is run from. `core/calendar/`,
`core/kollavarsham/`, and `core/events/` (below) are the layers that couple
astronomy output to the app's `PanchangamData`/DB-backed world; `core/astronomy/`
itself has no equivalent
coupling — the import contract keeps it that way, so it could still be
extracted into its own repo/package by moving the folder and flipping its
imports back to a top-level package name.

### Why this structure exists

**`core/calendar/`** aggregates astronomy into meaningful calendar objects. `panchangam.py::get_panchangam_data()` is the single orchestration point: it calls into `core/astronomy/` and `core/kollavarsham/`, builds a `PanchangamData` Pydantic object, and returns it. It is used directly by `features/panchangam/service.py` as the live-computation fallback for any date not yet in the DB.

**`core/kollavarsham/`** holds the Malayalam solar-calendar computation: `kollavarsham.py` (`get_kollavarsham_date`, `get_madhyahnam_raasi`), the import-light `kollavarsham_models.py::KollavarshamDate` value object (no Skyfield imports, so `schemas/` and `db/` can import it freely), and the `MalayalamMasa` enum at `enums/masa.py` (moved out of `utils/` since it is only used here and by the DB/reference layers that back it).

**`core/events/`** resolves an `EventCondition` to occurrence dates: `event_occurrences.py::compute_occurrences()` over a whole year range (single-day / last-occurrence / transition-series), and `significant_dates.py::match_condition_based_events()` for the single-day live-fallback overlay `PanchangamService` applies to dates with no DB occurrence row. Both are pure — they import only domain/schema/astronomy types, never `db/` or `api/`.

**`features/<name>/`** is a vertical slice: its `router.py` is the HTTP boundary (parses/validates query params, obtains a service via FastAPI `Depends`, delegates to it, translates domain errors to HTTP status codes) and its `service.py` sits between the router and persistence. `PanchangamService.get_by_date()`/`get_by_month()` read through the `PanchangamRepositoryPort`, falling back to `get_panchangam_data()` only when a date is missing from the database. Every feature owns its own `service.py`, including `settings` (`features/settings/service.py::SettingsService`) — a service consumed by 3+ other features' own services is still not imported directly cross-feature; the consumer depends on a `Protocol` in `core/ports/` instead (see "Ports & adapters" below). A feature that has been migrated to ports & adapters (see below) never imports a concrete `db/` repository from its `service.py`/`router.py` at all — only its own `ports.py` and the concrete adapter bound in `api/deps.py`.

**`db/`** is the Postgres persistence layer (SQLModel), untouched by the feature-folder split because several of its modules back more than one feature. The engine is built in `db/database.py` from a `DATABASE_URL` connection string read from the environment (a Neon Postgres URL, e.g. `postgresql://user:password@host/db?sslmode=require`) — no credentials are hardcoded. `PanchangamRepository` (in `features/panchangam/repository.py`, the concrete adapter for `PanchangamRepositoryPort`) is the only place that talks to the database for panchangam data — getters (`get_by_date`, `get_by_date_range`, `get_by_month`) and setters (`upsert`, `upsert_many`). `db/database.py::init_db()` ensures the schema exists at startup (idempotent); the database is seeded out-of-band by applying `db/sql/01_schema.sql` and `db/sql/02_seed.sql` to Neon/Postgres via `psql`. The server does not seed itself at runtime.

**`features/panchangam/router.py`** is the only panchangam router now — the unversioned legacy router was removed once all consumers moved to `/api/v1`. Route handlers parse and validate query parameters, obtain a service via FastAPI `Depends`, and delegate to it. They must not contain domain logic, computations, or direct astronomy/DB calls.

**`schemas/`** holds only the Pydantic models shared across features (or consumed by `db/`/`core/calendar/`, which don't import from `features/`). Everything else lives in the owning feature's `schemas.py`/`schemas/` package. The primary response schema is `PanchangamData` in `schemas/panchangam_data.py` — it is also the type returned by both the repository and the live-computation fallback.

**`utils/`** holds `roles.py`, `lifespan.py`, and `santhigiri_events.py` — anything imported by `core/`/`db/` (which must not depend on `features/`) or genuinely shared across features. `Nakshatra`, `Thithi`, and `Paksha` live in `core/astronomy/enums/`, and `MalayalamMasa` lives in `core/kollavarsham/enums/masa.py` — imported from there by `app/` code that needs them, not duplicated in `utils/`.

### Ports & adapters

The target pattern for every feature going forward is **ports and adapters**: a feature's service depends only on an abstract `Protocol` describing what it needs from persistence (and, where a service itself is a cross-feature dependency, what it needs from that service), never on a concrete SQLModel repository class or another feature's concrete service class. `features/auth/` is the canonical, fully-migrated example — read it before migrating another feature. `features/santhigiri_events/` is migrated the same way.

`features/settings/` is migrated with its `ports.py`/`repository.py`/`service.py` all living under `features/settings/`, same as `auth`. What's different is that `SettingsService` is a dependency of 3+ other features' own services (`panchangam`, its generation path, `santhigiri_events`), not just its own router — so those other services do not import `features.settings.service.SettingsService` directly (that would violate the layer-boundary rule against importing another feature's `service.py`). Instead they depend on `core/ports/settings_service.py::SettingsServicePort`, a `Protocol` covering just the typed getters those services actually call (`get_seed_year_range`, `get_max_generate_span_days`, `get_max_event_generate_year_span`, `get_event_cutoffs`, `get_astronomy_tuning`) — `SettingsService` satisfies it structurally, with no explicit `implements` needed. This port lives in `core/ports/` (next to `unit_of_work.py`) rather than in `features/settings/ports.py`, because unlike a repository port (which only the owning feature's own service consumes) it's the seam other features' services depend on directly. `api/deps.py` still wires the concrete `SettingsService` for every consumer, whether the consumer's parameter is typed as `SettingsServicePort` or as `SettingsService` itself (`features/settings/router.py`, which owns the feature, uses the concrete class).

`features/etag/` also has its `ports.py`/`repository.py`/`service.py` all living under `features/etag/`, but with a wrinkle: `features/etag/service.py` isn't a class-based service at all — it's the shared payload-builder/ETag-compute module every feature's router or service calls into, so there's no single `EtagService` dataclass to hold a port, and no `EtagServicePort` either. Instead, `conditional_json_response()` and `refresh_etags()` take `etag_repository: EtagRepositoryPort` and `unit_of_work: UnitOfWork` as plain parameters, resolved by the caller (a router via `api/deps.py`'s `EtagRepositoryDep`/`UnitOfWorkDep`, or a feature's own `service.py` that already holds those fields, e.g. `SanthigiriEventService`) — every consumer imports the module's functions directly, the same as it would import any other feature-owned utility module whose functions are already parametrized by ports rather than by state. `features/etag/ports.py` has no DTO — unlike `AppSettingGet`/`UserGet`, the value crossing the boundary is a bare ETag string keyed by dataset name, so there is no row shape to translate.

`refresh_etags()`/`build_year_payload()` also need to rebuild a year's compact payload, which means calling into `PanchangamService.get_by_year()` — a genuinely stateful, cross-feature service, unlike the settings getters. Rather than `features/etag/service.py` importing `features.panchangam.service.PanchangamService` (and the concrete `PanchangamRepository` adapter to build one) directly, it depends on `core/ports/panchangam_service.py::PanchangamServicePort` and takes an already-constructed instance as a `panchangam_service` parameter. The binding `api/deps.py::get_panchangam_service_for_etag_refresh` gives write-path callers (`PanchangamGenerationService`, `SanthigiriEventService`) is deliberately built *without* a `SettingsServicePort` — the same settings-free `PanchangamService` construction `refresh_etags` used to do inline — so refreshing a year's ETag right after a write never fails with `YearOutOfRange` just because that year sits outside the currently configured `seed_year_range` (unlike a normal `/year` read, which does go through the full range-checked `PanchangamService` from `get_panchangam_service`). Both write-path services carry this as a `panchangam_service_for_etag_refresh: PanchangamServicePort` field, injected by `api/deps.py` alongside their other ports, and pass it straight through to `refresh_etags()`.

`features/panchangam/` is migrated too, with its own wrinkle: `ports.py`'s `PanchangamRepositoryPort` has no new DTOs at all. `PanchangamData` (`schemas/panchangam_data.py`) and `SanthigiriEvent` (`utils/santhigiri_events.py`) are already plain, framework-independent Pydantic/dataclass domain objects — not SQLModel rows — so `PanchangamRepository` (`features/panchangam/repository.py`) returns and accepts them directly rather than translating to/from a separate boundary type. `PanchangamService` (`features/panchangam/service.py`) depends on `PanchangamRepositoryPort` and (optionally) `SettingsServicePort`, same as a canonical migrated feature. `PanchangamGenerationService` (`features/panchangam/generation_service.py`), the write-path sibling built for the admin `/generate` endpoint, is shaped like `SanthigiriEventService`: a frozen `@dataclass` holding `PanchangamRepositoryPort`, `SettingsServicePort`, `EtagRepositoryPort`, `PanchangamServicePort` (the settings-free binding — see the `etag` entry above), and `UnitOfWork` as fields, plus the raw `Session` that `features/etag/service.py::refresh_etags` still needs to build enum payloads — wired up by `api/deps.py::get_panchangam_generation_service` and injected into `generation_router.py` via `Depends`, never constructed by hand in the router. `SanthigiriEventService` carries the same `PanchangamServicePort` field for the same reason — its own `_commit_with_etags` also calls `refresh_etags()`.

`settings`, `etag`, `panchangam`, and `guruvani` are otherwise built exactly like a migrated feature's service: depending on ports + `UnitOfWork`, never a concrete adapter or another feature's concrete service class. Every feature has now been migrated to this pattern.

The pieces, using `features/auth/` as the reference:

- **`ports.py`** defines three things: the repository `Protocol` (`AuthRepositoryPort`), frozen `@dataclass` DTOs for data crossing the boundary (`UserGet`, `UserCreate`, `UserUpdate`, `UserWithCredentials`), and any domain exceptions the port can raise (`UserNotFoundException`). Nothing in `ports.py` imports SQLModel or a session.
- **The adapter** (`features/auth/auth_repository.py`, or `features/santhigiri_events/repository.py`) is a concrete class implementing the port against SQLModel: it takes a `Session`, and every method translates ORM rows to/from the port's DTOs (e.g. `AuthRepository._user_row_to_user_get`) — mirroring the `to_dto`/`from_dto` convention already used on `db/models/santhigiri_event.py`.
- **`service.py`** is a frozen `@dataclass` (not a plain `__init__`) holding the port and a `UnitOfWork` (`core/ports/unit_of_work.py`) as fields — e.g. `AuthService(auth_repository: AuthRepositoryPort, uow: UnitOfWork)`. It imports the port's Protocol and DTOs, never the concrete adapter class or `Session`. Request-schema → DTO conversion (and the reverse, DTO → response-schema) happens inside `service.py` methods (e.g. `AuthService._user_get_to_get_user_response`), not in the router.
- **`db/unit_of_work.py::SqlUnitOfWork`** is the one concrete `UnitOfWork` adapter, wrapping a `Session`. A mutation wraps the repository call(s) in `with self.unit_of_work as uow: ...; uow.commit()` (or lets a shared commit helper like `features/etag/service.py::refresh_etags` do the commit, if the mutation must land atomically with an ETag refresh).
- **`api/deps.py`** is where every concrete adapter gets bound to its port and injected — e.g. `get_auth_repository(session) -> AuthRepositoryPort: return AuthRepository(session)`, then `get_auth_service(auth_repository: AuthRepositoryDep, uow: UnitOfWorkDep) -> AuthService`. A feature's `router.py` depends on the service factory from `api/deps.py`; it never constructs a concrete adapter or service by hand.

Match this granularity exactly when migrating a new feature — one `ports.py` per feature, one adapter class, no finer-grained ports (no separate read/write port classes, no per-method protocols).

### Versioning without a `v1/` directory

Versioning is applied externally: a feature's `router.py` (or `generation_router.py`, etc.) declares only its feature-local prefix (e.g. `/panchangam/events`), and `main.py` mounts it with `app.include_router(router, prefix="/api/v1")`. To add a `v2` of one feature's endpoints, add `features/<name>/router_v2.py` alongside the existing `router.py` and mount it with `prefix="/api/v2"` in `main.py` — no directory reshuffle needed.

### Authentication & Authorization

The API uses **JWT bearer authentication** with a three-tier role hierarchy: `anonymous` < `user` < `admin` (`utils/roles.py::Role`). All auth wiring lives in `api/deps.py`; the crypto lives in `core/security.py` (password hashing + access/refresh token mint and decode) and settings in `core/config.py`.

- **`get_current_principal`** resolves the request's bearer token into a `Principal` (`role`, `username`). No token → the `anonymous` principal. A malformed/expired/wrong-type token, or one naming an unknown or deactivated user → `401` (it is **not** downgraded to anonymous).
- **`require_role(minimum)`** is a dependency factory that gates an endpoint at a minimum role. Anonymous callers to a protected endpoint get `401`; authenticated callers with an insufficient role get `403`. It returns the resolved `Principal` so handlers can read the current user.
- **Public endpoints still declare a guard** — the panchangam data routers depend on `require_role(Role.ANONYMOUS)`, which permits anonymous access but still validates (and rejects) any bearer token that *is* supplied.

Auth endpoints live in `features/auth/router.py` (`/api/v1/auth/login`, `/refresh`, `/me`, `/users`). Users are stored via the `AuthRepositoryPort` adapter (`features/auth/auth_repository.py`); an initial admin can be seeded at startup by setting `INITIAL_ADMIN_USERNAME`/`INITIAL_ADMIN_PASSWORD`. Route handlers remain thin — credential checking, hashing, and token minting are delegated to `core/security.py`.

### Editable Santhigiri event definitions

The `santhigiri_event` table is the **authoritative, editable** definition store for event types (name, description, matching condition), seeded from `utils/santhigiri_events.py` but authoritative thereafter. It is read for the `GET /panchangam/events` reference list (via `db/reference_repository.py`) and written through the `SanthigiriEventsRepositoryPort` adapter (`features/santhigiri_events/repository.py`). `features/santhigiri_events/service.py` orchestrates create/update/delete against that port: each mutation commits **atomically with an ETag refresh** (`features/etag/service.py`) — always the `events` reference dataset, plus every `year` dataset whose cascade-deleted occurrences changed on a delete — so cached clients revalidate correctly. Editing a definition does **not** by itself recompute which dates the event falls on — that's a separate step, either the offline cache pipeline (see "Adding a new Santhigiri event") or the live DB-driven `POST /panchangam/events/{event_id}/occurrences` / `POST /panchangam/events/generate` endpoints (`SanthigiriEventService.generate_occurrences`/`generate_all_occurrences_streaming`), which (re)compute an event's (or every event's) occurrence dates over a year range directly from the DB's panchangam data and overwrite `santhigiri_event_dates` for that range.

An event definition may also set `yields_to_event_id`, pointing at another event it defers to: when generating this event's occurrences via the live path above, any date where the referenced event's condition also matches is dropped from this event's own occurrence set. This is resolved live against the same year's panchangam data on every generation run (not a static precomputed exclusion), and only affects the live generation path — it has no offline-pipeline equivalent. Used to resolve same-date collisions between events that can both plausibly claim a day, e.g. `JANMAGRIHA_THEERTHA_YATHRA` (every Chothi Nakshatra transition) yields to `NAVAPOOJITHAM` (the last Chothi-in-Chingam day) since a year's Navapoojitham date is also, incidentally, a routine Chothi transition.

---

## Mandatory Conventions

Follow these rules without exception.

### Layer import boundaries

- Route handlers in `features/<name>/router.py` must only parse HTTP params and delegate to that feature's `service.py`. They must not call a `db/` repository or `core/astronomy/`/`core/calendar/`/`core/kollavarsham/`/`core/events/` directly.
- `core/astronomy/` functions must not import from anything else under `app/` — not `api/`, `features/`, `schemas/`, `db/`, `utils/`, `core/calendar/`, `core/kollavarsham/`, `core/events/`, `core/ports/`, `core/config.py`, or `core/security.py`. This is enforced by the `astronomy-isolation` contract in `.importlinter` (`lint-imports`); a new `app/core/<sibling>` must be added to its `forbidden_modules` list.
- `core/calendar/`, `core/kollavarsham/`, and `core/events/` functions must not import from `api/` or `features/`.
- `db/` (models, `reference_repository.py`, etc.) must not import from `api/` or `features/` — with one narrow, deliberate exception: a table model backing a migrated feature (e.g. `db/models/santhigiri_event.py`) may import that feature's `ports.py` for its `to_dto`/`from_dto` conversion, since the port's DTOs *are* that row's serialization contract. Nothing else in `db/` gets this exception.
- Pydantic models belong in `schemas/` (if shared across features) or `features/<name>/schemas.py` (if feature-local). Do not define response models inside `core/` or `utils/`.
- A feature's `service.py` may import `db/` and, for a module of free functions already parametrized by ports rather than by state (e.g. `features/etag/service.py`), another feature's `service.py` module directly. But other features must not import one feature's stateful `service.py` class, `router.py`, or `schemas.py` directly — a cross-feature dependency on another feature's stateful service goes through a `Protocol` in `core/ports/` instead (see "Ports & adapters" above), never a direct import of the concrete class.
- A feature migrated to ports & adapters (see "Ports & adapters" above) must not have its `service.py` or `router.py` import a concrete repository/adapter class, or another feature's concrete stateful service class, directly — depend on the port (`Protocol`) and get the concrete instance via `api/deps.py`.

### Business logic placement

- All astronomical calculations go in `core/astronomy/`.
- Calendar/domain aggregation goes in `core/calendar/`; Malayalam-calendar computation in `core/kollavarsham/`; event-condition → occurrence-date resolution in `core/events/`.
- Event definitions go in `utils/santhigiri_events.py`.
- No business logic may live inside a route handler.

### Adding a new astronomical value

1. Implement the raw calculation function in the appropriate `core/astronomy/` file.
2. Call it from `core/calendar/panchangam.py::get_panchangam_data()`.
3. Add the field to `schemas/panchangam_data.py::PanchangamData`.
4. The route handler picks it up automatically — do not touch the route.

### Adding a new Santhigiri event

1. Create the event definition via the admin `POST /api/v1/panchangam/events` endpoint (or directly through `SanthigiriEventService`), with the appropriate `EventCondition`. This is now the authoritative source — `utils/santhigiri_events.py` only seeds the initial rows.
2. `core/events/event_occurrences.py::classify_condition()` must be able to resolve the condition to a set of days: a single-day pin, a `last_occurance` condition (with a Malayalam-month + Nakshatra fallback), or a bare-Nakshatra transition series. Any other shape raises `UnsupportedEventCondition`.
3. Call `POST /api/v1/panchangam/events/{event_id}/occurrences` (or `POST /api/v1/panchangam/events/generate` to recompute every event) to (re)compute the event's occurrence dates over a year range directly from the DB's panchangam data and write them to `santhigiri_event_dates`, refreshing ETags atomically.
4. The event will appear in `PanchangamData.santhigiri_significant_dates` in the API response.

### Adding a new API endpoint

1. If the endpoint belongs to an existing feature, add it to that feature's `features/<name>/router.py` (or a new `features/<name>/<sub>_router.py` alongside it, as `panchangam` does for `generation_router.py`). For a genuinely new feature, create `features/<name>/` with `router.py` (+ `service.py`/`schemas.py`/`schemas/` as needed) following the layout of an existing feature. Do not add endpoints to an existing router file unless they are closely related to that feature.
2. Define request params as a Pydantic `BaseModel` in `features/<name>/schemas.py` (feature-local), or in top-level `schemas/` only if the schema must also be consumed by `db/`, `core/calendar/`, or another feature.
3. Register the new router in `main.py` using `app.include_router(...)`. For a versioned router, pass the version prefix at inclusion time, e.g. `app.include_router(router, prefix="/api/v1")` — routers themselves should not hardcode the version segment (see "Versioning without a `v1/` directory" above).
4. All domain logic the endpoint needs must be implemented in `core/` or the feature's own `service.py` orchestrator — never in the handler. A cross-feature dependency on another feature's service goes through a `Protocol` in `core/ports/` (see "Ports & adapters" above), not a direct import.
5. **Choose an authorization level with `require_role`.** Read endpoints that expose public panchangam data use `require_role(Role.ANONYMOUS)` (permits anonymous, still validates any supplied token). Any endpoint that **mutates** state must be gated at the appropriate role — event-definition writes and user management require `require_role(Role.ADMIN)`. Apply the guard per-endpoint via the decorator's `dependencies=[...]` when a router mixes privilege levels, or at the router level when they are uniform.

### Enum usage

Use the typed Python enums (`Nakshatra`, `Thithi`, `Paksha` from `app.core.astronomy.enums.*`; `MalayalamMasa` from `app.core.kollavarsham.enums.masa`) for all internal domain logic. Never use raw strings or bare integer IDs when a typed enum is available. The enums carry only `id` (+ `paksha`/`day` on `Thithi`); their `.name` is the stable slug. They do **not** carry display text — localized `en`/`ml` names come from the DB reference tables (nullable `ml`/`en` columns, seeded by `db/sql/02_seed.sql`), exposed via the `GET /api/v1/panchangam/thithi|nakshatra|masa` endpoints. Compact API responses carry the slug/id; the client resolves display names from those reference datasets.

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

The Kollam Era calendar used in Kerala. The Malayalam month is determined by the Sun's sidereal raasi (zodiac sign) relative to **Modyana**. The daytime (sunrise → sunset) is split into five equal parts; Modyana is the **third part** (spanning 40%–60% of the daytime). The month changes on the day of the Sankramanam (the Sun's entry into a new raasi) if that entry occurs **before or during** Modyana, otherwise the next day. Sampling the raasi at the **end of Modyana** (`sunrise + 3·(sunset − sunrise)/5`, the 60% point) is the exact realization of this rule.

A Kollam year runs Chingam..Karkidakam and straddles two Gregorian years: its
Chingam..Dhanu months fall in Aug–Dec of Gregorian year `Y`, and its
Makaram..Karkidakam months fall in Jan–Aug of `Y + 1`. The year number therefore
only increments at Chingam (mid-August), and is constant across every masa within
the year — including the Meenam→Medam step and Dhanu's Dec/Jan straddle (the
Gregorian month disambiguates Dhanu's December from its January tail):

```
# raasi index: 0=Medam … 4=Chingam … 8=Dhanu … 11=Meenam
kollam_year = english_year - 824   # if 4 <= raasi <= 8 (Chingam..Dhanu) and month >= 8 (Aug..Dec)
kollam_year = english_year - 825   # otherwise
```

The Malayalam day is computed by walking backwards through days' end-of-Modyana samples to find when the current raasi began. Implemented in `core/kollavarsham/kollavarsham.py`.

### Nazhika (Traditional Time Unit)

1 Nazhika = 24 minutes. A full day = 60 Nazhikas. The field `nazhika_from_sunrise` in `PanchangamData` represents how many Nazhikas of the current Nakshatra remain from sunrise. This is used to determine which day an event falls on when a Nakshatra transitions near sunrise (the "7.5 Nazhika rule").

### Transitions

A Thithi or Nakshatra rarely spans exactly one calendar day. Transitions are detected using Skyfield's `find_discrete()` function, which searches a time window for discrete state changes. The search window for each day covers the previous day, current day, and next day, then filters to transitions that overlap the current day. This is the mechanism in `core/astronomy/thithi_transition.py` and `core/astronomy/nakshatra_transition.py`.

The step size for the search (`step_days`) is critical for accuracy. The nakshatra step is configured via `NAKSHATRA_TRANSITION_STEP_DAYS` in `core/astronomy/constants.py`. The value `0.01` works for most years but may need adjustment (see the comment in `constants.py` for 2028, which requires `0.05`).

### Pournami (Full Moon)

Pournami detection is not simply "is today's Thithi Pournami?" because a Thithi can span across midnight. The implementation checks that:

1. The Thithi at 23:59:59 of **today** is Pournami, AND
2. The Thithi at 23:59:59 of **yesterday** was not Pournami.

This ensures Pournami is attributed to exactly one calendar day. Implemented in `core/astronomy/pournami.py`.

### Santhigiri Events

Santhigiri Ashram observes events tied to specific dates in either the English or Malayalam calendar, or to astronomical conditions (Nakshatra, Thithi, Pournami). Events are modeled as `SanthigiriEvent` with an `EventCondition` that specifies the matching criteria. Occurrence dates are computed against the DB's panchangam data via `core/events/event_occurrences.py` and stored in `santhigiri_event_dates`, surfaced in `PanchangamData.santhigiri_significant_dates`.

Some events use a "last occurrence" rule: for example, Navapoojitham falls on the last Chothi Nakshatra in the month of Chingam (with the 7.5 Nazhika rule to handle edge cases at sunrise). `compute_last_occurrence()` in `core/events/event_occurrences.py` handles this generically off the event's `EventCondition`.

---

## Tech Stack

| Dependency | Purpose |
|---|---|
| `fastapi` | HTTP framework and request validation |
| `uvicorn[standard]` | ASGI server (uvloop/httptools for production) |
| `python-multipart` | Parses the OAuth2 form login (`features/auth/router.py`) |
| `skyfield` | High-precision astronomical calculations (positions, `find_discrete`) |
| `pyswisseph` | Lahiri Ayanamsa computation via Swiss Ephemeris |
| `sqlmodel` | ORM / table definitions over SQLAlchemy for the persistence layer |
| `psycopg2-binary` | PostgreSQL driver (Neon) |
| `python-dotenv` | Loads `DATABASE_URL` from a local `.env` during development |
| `python-jose[cryptography]` | Mint/verify JWT access & refresh tokens (`core/security.py`) |
| `bcrypt` | Password hashing for user credentials |
| `pydantic-settings` | Typed settings (JWT config) in `core/config.py` |
| `google-auth` | Verifies Google ID tokens (`core/security.py::verify_google_id_token`) — currently unused by any router; see the `POST /auth/google` gap below |
| `pytz` | Timezone handling |
| `de421.bsp` | NASA/JPL ephemeris file (16.8 MB) loaded by Skyfield for Sun/Moon/Earth positions |

`pytest` and `httpx` (test-only) live in `requirements-dev.txt`; the runtime image
installs `requirements.txt` alone.

The `de421.bsp` file must be present in the project root at startup. It is a binary data file — do not delete it or add it to `.gitignore`.

---

## Running the Project

### Local development

```bash
pip install -r requirements-dev.txt   # runtime deps + pytest/httpx (use requirements.txt for runtime only)
cp .env.example .env   # then fill in your Neon DATABASE_URL
uvicorn main:app --reload --port 8000
```

`DATABASE_URL` must be set (in the environment or a local `.env`) or startup fails fast — it points at a Neon/Postgres database. Startup only ensures the schema exists (`init_db()`); it does not load any data. Seed the database once by applying `db/sql/01_schema.sql` and `db/sql/02_seed.sql` with `psql` (10 years of pre-computed data, 2021–2030). See `db/sql/README.md`.

Set `JWT_SECRET_KEY` to a long random secret for auth (the app falls back to an insecure development default and logs a warning if unset). Optionally set `INITIAL_ADMIN_USERNAME`/`INITIAL_ADMIN_PASSWORD` to seed an admin at startup (idempotent). See `.env.example` for all auth variables and their defaults.

### Docker

```bash
docker build -t panchangam-api .
docker run -p 8000:8000 panchangam-api
```

The container exposes port 8000 and runs `uvicorn main:app --host 0.0.0.0 --port 8000`.

### Endpoints

Panchangam data (public — anonymous allowed, any supplied token still validated):

- `GET /api/v1/panchangam/day?day=YYYY-MM-DD` — main version; returns the compact Panchangam for a single day
- `GET /api/v1/panchangam/instant?day=YYYY-MM-DD&time=HH:MM&latitude=..&longitude=..&timezone=..` — main version; returns the compact Panchangam active at an arbitrary date/time/location instant (always live-computed, no DB lookup)
- `GET /api/v1/panchangam/month?year=YYYY&month=MM` — main version; returns the compact Panchangam for every day in the month
- `GET /api/v1/panchangam/year?year=YYYY` — main version; ETag-validated (returns `304` on `If-None-Match`)

Reference datasets (public, ETag-validated, read from the DB):

- `GET /api/v1/panchangam/thithi` · `/nakshatra` · `/masa` · `/events`

Santhigiri event definitions (read public; writes require the `admin` role):

- `POST   /api/v1/panchangam/events` — create an event definition (admin)
- `GET    /api/v1/panchangam/events/{event_id}` — fetch one event's full definition (public)
- `PUT    /api/v1/panchangam/events/{event_id}` — partial-update an event definition (admin)
- `DELETE /api/v1/panchangam/events/{event_id}` — delete an event definition (admin)

Authentication:

- `POST /api/v1/auth/login` — form login (`username`, `password`) → access + refresh tokens
- `POST /api/v1/auth/refresh` — exchange a refresh token for a new token pair (rotation)
- `GET  /api/v1/auth/me` — the current user (requires `user` or `admin`)
- `POST /api/v1/auth/users` — create a user (admin only)

Guruvani quotes (read public; writes require the `admin` role):

- `GET    /api/v1/guruvani` — list every quote, ordered by `sort_order` (public)
- `GET    /api/v1/guruvani/random` — fetch one quote at random (public)
- `GET    /api/v1/guruvani/{id}` — fetch one quote (public)
- `POST   /api/v1/guruvani` — create a quote (admin)
- `PUT    /api/v1/guruvani/{id}` — partial-update a quote (admin)
- `DELETE /api/v1/guruvani/{id}` — delete a quote (admin)

Panchangam parameters default to today's date, Santhigiri Ashram coordinates, and `Asia/Kolkata` timezone.

---

## Running Tests

```bash
pytest tests/
```

`tests/` mirrors the `app/` layout: `tests/core/<subpackage>/` for `core/` unit tests, `tests/db/` for the shared persistence layer, and `tests/features/<name>/` for a feature's router/service/repository tests, one test module per source module (e.g. `app/features/auth/router.py` ↔ `tests/features/auth/test_router.py`). A test that exercises a whole request across feature boundaries (e.g. an admin setting changing what a read endpoint returns) lives under the feature it's conceptually about, suffixed `_integration`.

Current coverage:

- `tests/core/astronomy/test_pournami.py` — 24 parametrized test cases verifying full moon detection against known dates for 2022 and 2026.
- `tests/core/astronomy/test_lazy_astronomy.py` — the heavy Skyfield/ephemeris stack loads lazily, not at app import.
- `tests/core/calendar/` — the `core/calendar/panchangam.py` skeleton.
- `tests/core/kollavarsham/` — Kollavarsham coordinate/Modyana rules.
- `tests/core/events/` — the event occurrence/significant-dates matchers.
- `tests/db/` — shared persistence-layer unit tests (round-trips, cascade deletes, seeding) for the schema and `ReferenceRepository`.
- `tests/features/auth/test_router.py` — JWT login/refresh, token-type enforcement, and the `require_role` guards (401/403).
- `tests/features/auth/test_google_auth.py` — skipped; see its module docstring for the dropped `/auth/google` feature.
- `tests/features/etag/` — `stable_hash`/`If-None-Match` helpers plus end-to-end conditional-request behaviour of the year and enum-reference endpoints.
- `tests/features/panchangam/` — `PanchangamRepository`, the `/instant` and `/sunrise-sunset` endpoints, and the admin `/generate` write path.
- `tests/features/santhigiri_events/` — event-definition CRUD and occurrence-generation, end-to-end, including admin-role enforcement and ETag invalidation.
- `tests/features/settings/` — `AppSettingRepository`, the admin settings CRUD endpoints, and settings→panchangam integration (e.g. `seed_year_range` gating `get_by_year`/`get_by_month`).
- `features/guruvani/` has no test coverage yet (no `tests/features/guruvani/` directory) — a gap, not a deliberate omission; follow the `auth`/`santhigiri_events` test shape (repository round-trips + router CRUD + role-guard checks) when adding it.

Tests use an in-memory SQLite engine (the FK pragma listener in `app/db/database.py` makes `ON DELETE CASCADE` behave as it does on Postgres); see `tests/conftest.py`. The API tests override `get_session` onto a seeded engine and drive the app with `TestClient` (see `tests/features/etag/test_service.py` for the fixture pattern).

When adding new astronomical calculations, add parametrized tests to `tests/` that verify against known Panchangam dates. Cross-check expected values against published physical Panchangams or the Drik Panchang reference.

---

## Caching Strategy

This is the most performance-critical aspect of the system. Understand it before making any changes.

### Runtime store (Postgres via `PanchangamRepository`)

Both endpoints are served through `features/panchangam/service.py`, which reads via `features/panchangam/repository.py::PanchangamRepository` (the `PanchangamRepositoryPort` adapter) against the Neon/Postgres database configured by `DATABASE_URL` (seeded for 2021–2030). This makes the monthly endpoint essentially free — it serves pre-computed rows without any Skyfield calls. If a date is missing from the DB, `get_panchangam_data()` computes it live; the result is returned but **not** written back (unlike the retired in-memory cache), so a real gap must be closed by re-applying the SQL seed files rather than relying on organic backfill.

At startup, the FastAPI lifespan (`utils/lifespan.py`) calls `init_db()`, which only ensures the schema exists (idempotent). The database is seeded out-of-band by applying `db/sql/01_schema.sql` and `db/sql/02_seed.sql` to the Neon/Postgres target with `psql`; the server never seeds itself at runtime.

### Function-level LRU caches

Several functions in `core/astronomy/` and `core/kollavarsham/` are decorated with `@lru_cache`. Key examples:

- `get_sunrise_sunset()` in `core/astronomy/sunrise_sunset.py`
- `get_thithi_transition_by_date()` in `core/astronomy/thithi_transition.py`
- `get_kollavarsham_date()` and `get_madhyahnam_raasi()` in `core/kollavarsham/kollavarsham.py`
- `get_sun_sidereal_longitude()` in `core/astronomy/calculations.py`

These are critical for the transition-detection logic, which calls the same function for the previous day, current day, and next day. Without LRU caching these would be redundantly recalculated.

### Regenerating data (live, DB-driven — no offline pipeline)

There is no offline pickle-cache pipeline anymore; both base panchangam data and Santhigiri event occurrences are (re)computed directly against Postgres through admin endpoints:

1. **Base panchangam data** — `POST /api/v1/panchangam/generate` (admin, `PanchangamGenerationService`) recomputes a date range from the astronomy code and overwrites the corresponding rows, streaming NDJSON progress. Use this after changing computation logic in `core/astronomy/`/`core/calendar/`/`core/kollavarsham/`.
2. **Santhigiri event occurrences** — `POST /api/v1/panchangam/events/{event_id}/occurrences` (one event) or `POST /api/v1/panchangam/events/generate` (all events) recompute occurrence dates for a year range from the DB's panchangam data (via `core/events/event_occurrences.py`) and overwrite `santhigiri_event_dates`. Use this after adding/editing an event definition.

Both paths commit atomically with an ETag refresh (`features/etag/service.py`) so cached clients revalidate correctly. Neither writes to disk or requires a separate seed-regeneration step.

---

## Ephemeris File

`de421.bsp` lives at `core/astronomy/de421.bsp` and is loaded at module
import time in `core/astronomy/ephemeris.py` as a module-level singleton,
via a `skyfield.api.Loader` rooted at the module's own directory (`Path(__file__).parent`)
rather than the process's current working directory — so it resolves correctly
no matter where the app is run from:

```python
_loader = Loader(str(Path(__file__).parent))
ephem = _loader("de421.bsp")
earth = ephem["earth"]
sun   = ephem["sun"]
moon  = ephem["moon"]
ts    = _loader.timescale()
```

Importing anything from `core/astronomy/` triggers this load. Do not move the load call into individual functions — it is intentionally a module-level singleton. In tests, mock `app.core.astronomy.ephemeris` if you need to avoid loading the ephemeris.

---

## Known Issues and Active Work

- `core/events/significant_dates.py` is implemented and live: `match_condition_based_events()` matches single-day-pinned event conditions against a computed day, and `PanchangamService._compute()`/`get_panchangam_at_instant()` (`features/panchangam/service.py`) call it to overlay `santhigiri_significant_dates` onto any live-computation fallback (a date missing from the DB, or the `/instant` endpoint). "Last occurrence" and month/nakshatra-only conditions are still out of scope for this matcher (see its module docstring) — they need whole-year context and remain the job of `core/events/event_occurrences.py`, used only by the DB-writing occurrence-generation endpoints.
- `core/calendar/panchangam.py::get_panchangam()` (the dict-returning version) is a legacy function superseded by `get_panchangam_data()`. Do not add new callers of `get_panchangam()`.
- The live-computation fallback in `PanchangamService` (used when a date is missing from the DB) does not write its result back to the database. A persistent gap must be closed by regenerating and re-applying the `db/sql/*.sql` seed files, not by traffic alone.
- `NAKSHATRA_TRANSITION_STEP_DAYS` is `0.01` for 2021–2027 and 2029–2030. For 2028 it must be `0.05`. This is a fragile per-year constant; treat any change with caution. `app/utils/check_nakshatra_transitions.py`/`check_thithi_transitions.py` hold standalone transition-miss-checker functions for validating a change against a generated cache — they are **not** wired into app startup or CI, so run them manually after touching this constant.
- `features/auth/`, `features/santhigiri_events/`, `features/settings/`, `features/etag/`, `features/panchangam/`, and `features/guruvani/` have all been migrated to the ports & adapters pattern (see "Ports & adapters" above). Every feature now follows this pattern.
- There is no `app/services/` folder anymore — `SettingsService` and the ETag payload/compute functions now live in `features/settings/service.py` and `features/etag/service.py` respectively. Cross-feature callers of `SettingsService` depend on `core/ports/settings_service.py::SettingsServicePort`, not the concrete class. `features/etag/service.py` itself depends on `core/ports/panchangam_service.py::PanchangamServicePort` rather than importing `features.panchangam.service.PanchangamService`/`features.panchangam.repository.PanchangamRepository` directly — `api/deps.py::get_panchangam_service_for_etag_refresh` binds a settings-free instance for it and for the two write-path services that call `refresh_etags`. `features/etag/service.py::build_enum_payload`/`refresh_etags` likewise depend on `core/ports/reference_repository.py::ReferenceRepositoryPort` rather than constructing `db/reference_repository.py::ReferenceRepository` from a raw `Session` — `api/deps.py::get_reference_repository` binds the concrete adapter, injected into `features/reference/router.py`'s reference endpoints and into `PanchangamGenerationService`/`SanthigiriEventService` (which dropped their `session` fields now that `refresh_etags` no longer needs one).
- The `thithi`/`nakshatra`/`masa`/`events`/`locations` reference endpoints used to live on `features/panchangam/router.py`; they now live in their own `features/reference/router.py`, still mounted under the `/panchangam` URL prefix for backward compatibility. `features/reference/` has no `ports.py`/`service.py` of its own — it depends on `core/ports/reference_repository.py::ReferenceRepositoryPort` and `features/etag/service.py` directly, the same way `panchangam/router.py` does for `/year`.
- `POST /auth/google` (Google Sign-In) and its find-or-create-by-`google_id` logic were dropped from `features/auth/` during the `app/` restructure and never carried over to `AuthRepositoryPort`/`AuthRepository`/`AuthService`, even though `db/models/user.py::User` still has a `google_id` column and `core/security.py::verify_google_id_token` still exists. `tests/features/auth/test_google_auth.py` documents this as a skipped gap rather than a fabricated pass — restoring it is a real feature slice (new port method + DTO + repository + service + router wiring), not a quick fix.

---

## What Not To Do

- Do not put business logic in route handlers. If a route handler is doing anything beyond parsing params and calling `PanchangamService`, move the logic to that feature's `service.py` or `core/`.
- Do not call `core/astronomy/`, `core/calendar/`, or a concrete `db/` repository directly from route handlers — go through `features/panchangam/service.py` (or the relevant feature's `service.py`).
- Do not define new Pydantic models inside `core/` or `db/` modules.
- Do not add new event definitions in `core/` or `api/`. All event definitions belong in `utils/santhigiri_events.py`.
- Do not change `NAKSHATRA_TRANSITION_STEP_DAYS` without re-validating every year's cache with `app/utils/check_nakshatra_transitions.py`/`check_thithi_transitions.py` (run manually — they are not part of startup or CI).
- Do not assume the daily endpoint passes user-supplied coordinates to the computation — check the route handler first.
- Do not hardcode Malayalam or Sanskrit display names as string literals in new code. Domain logic keys off the typed enum (`.name` slug / `.id`); display text is DB-owned — read it from the reference tables. The only place display strings are literals is `db/sql/02_seed.sql`.
