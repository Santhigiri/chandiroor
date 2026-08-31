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

Each feature owns its own router, service, and request/response schemas under `features/<name>/`. Only pieces that are genuinely shared across *multiple* features — the persistence layer (`db/`), the astronomy/calendar domain logic (`core/`), cross-cutting services (`services/`), and cross-cutting schemas (`schemas/`) — live outside a feature folder.

Everything below lives under `app/` (the on-disk package root); paths in this
document are given relative to `app/` unless a leading `app/` is shown.

```
panchangam-api/
└── app/
    ├── main.py                     # App factory: wires lifespan, CORS, routers
    ├── api/
    │   └── deps.py                 # Shared Depends: get_*_service, get_location, get_current_principal, require_role — also where every port gets bound to its concrete adapter
    ├── features/                   # One subpackage per feature — the HTTP boundary + orchestration for that feature
    │   ├── panchangam/                  # Migrated to ports & adapters (see "Ports & adapters" below)
    │   │   ├── router.py               # Compact panchangam + reference (thithi/nakshatra/masa/events) reads, mounted at /api/v1
    │   │   ├── legacy_router.py        # Deprecated pre-v1 router (unversioned); do not add new callers or new endpoints here
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
    │   │   ├── schemas.py    # Flat request/response schemas (HTTP boundary shape, distinct from ports.py's nested DTOs)
    │   │   └── offline_cache/  # Single-consumer offline maintenance scripts for the pickle-cache pipeline (see "Offline cache management")
    │   │       ├── cache_crud.py                    # Reads/writes pickle files on disk
    │   │       ├── cache_common_events.py           # Populates simple (condition-based) Santhigiri events into cache
    │   │       ├── cache_navapoojitham.py           # Populates Navapoojitham (Guru birthday) into cache
    │   │       ├── cache_sishya_bday.py             # Populates Shishyapoojitha birthday into cache
    │   │       ├── cache_chothi_theerthayathra.py   # Populates pilgrimage dates into cache
    │   │       ├── cache_utils.py
    │   │       └── rebuild_events.py
    │   ├── auth/                        # Migrated to ports & adapters (the canonical example — see below)
    │   │   ├── ports.py           # AuthRepositoryPort (Protocol) + DTOs (UserGet/Create/Update/WithCredentials) + UserNotFoundException
    │   │   ├── auth_repository.py # AuthRepository — concrete adapter implementing the port against SQLModel
    │   │   ├── router.py    # login / refresh / me / users / Google sign-in (JWT auth)
    │   │   ├── service.py   # AuthService — depends on AuthRepositoryPort + UnitOfWork, not the concrete adapter
    │   │   └── schemas.py
    │   ├── guruvani/
    │   │   ├── router.py
    │   │   ├── service.py
    │   │   └── schemas.py
    │   ├── settings/                    # Migrated to ports & adapters, but the service itself stays in services/ — see below
    │   │   ├── ports.py      # AppSettingRepositoryPort (Protocol) + AppSettingGet DTO
    │   │   ├── repository.py # AppSettingRepository — concrete adapter implementing the port against SQLModel
    │   │   └── router.py     # Admin CRUD for app_setting
    │   └── etag/                        # Migrated to ports & adapters; only the payload/ETag *functions* stay in services/ — see below
    │       ├── ports.py      # EtagRepositoryPort (Protocol) — no DTO, the boundary value is a bare ETag string
    │       └── repository.py # EtagRepository — concrete adapter implementing the port against SQLModel (dataset_etag table)
    ├── services/                    # Only services used by 3+ features stay here — everything else moved into features/<name>/service.py
    │   ├── etag_service.py          # Canonical payload builders + ETag compute/refresh (used by every feature).
    │   │                             # Depends on features/etag/ports.py's EtagRepositoryPort + UnitOfWork for ETag
    │   │                             # persistence, never the concrete adapter — the rest of its functions still take a
    │   │                             # raw Session because they build payloads via a session-constructed
    │   │                             # features/panchangam/repository.py and db/reference_repository.py (the latter
    │   │                             # not migrated yet) rather than dependency-injecting the port from the caller.
    │   └── settings_service.py      # SettingsService — reads/writes app_setting; used by every feature's service plus api/deps.py.
    │                                 # Depends on features/settings/ports.py's AppSettingRepositoryPort + UnitOfWork, not the
    │                                 # concrete adapter — built the same way as a migrated feature's service.py, just located
    │                                 # here instead of features/settings/ because 3+ other features' services use it directly.
    ├── db/                         # Postgres persistence layer (SQLModel) — unchanged by the feature-folder move
    │   ├── database.py             # Engine (reads DATABASE_URL from env), session factory, init_db()
    │   ├── unit_of_work.py         # SqlUnitOfWork — the one concrete UnitOfWork adapter (see "Ports & adapters" below)
    │   ├── reference_repository.py # Reads the enum/reference datasets (thithi, nakshatra, masa, events)
    │   ├── kollavarsham_repository.py
    │   ├── guruvani_repository.py
    │   ├── seed.py                 # Seeds lookup tables (Thithi, Nakshatra, Paksha, MalayalamMasa, Location, SanthigiriEvent)
    │   ├── sql/                    # Standalone schema + seed SQL applied to Neon/Postgres via psql
    │   └── models/                 # SQLModel table definitions
    ├── core/                        # Unchanged by the feature-folder move — shared by every feature
    │   ├── astronomy/              # Pure astronomical computation (no HTTP, no Pydantic responses)
    │   ├── calendar/               # Domain aggregation: combines astronomy into calendar objects
    │   ├── ports/
    │   │   └── unit_of_work.py     # UnitOfWork (Protocol) — the transaction boundary every migrated feature's service depends on
    │   ├── security.py             # Password hashing + JWT mint/decode (no HTTP)
    │   ├── config.py               # Settings (JWT_SECRET_KEY etc.) via pydantic-settings
    │   └── constants.py            # Shared domain constants (names, coordinates, timezone)
    ├── schemas/                     # Only schemas used by 2+ features, or by db/ or core/, stay here
    │   ├── location.py              # LocationInfo — used by features/panchangam/repository.py, core/calendar/, and multiple features
    │   ├── panchangam_data.py       # PanchangamData — returned by features/panchangam/repository.py and core/calendar/panchangam.py
    │   ├── compact_panchangam_data.py  # Used by services/etag_service.py, db/reference_repository.py, and multiple features
    │   └── app_setting.py           # Used by services/settings_service.py *and* features/santhigiri_events/service.py
    └── utils/                      # Domain enums, roles, and cross-cutting helpers with no feature to own them
        ├── roles.py                # Role enum (anonymous < user < admin) for authorization
        ├── lifespan.py             # Startup: init_db() ensures the Postgres schema exists (no runtime seeding)
        └── santhigiri_events.py    # Event definitions and matching conditions — stays here (not features/) since
                                     # core/calendar/ and db/ import it directly and must not depend on features/
scripts/gen_seed_sql.py     # Build-time tool: turns the pickle caches into db/sql/*.sql — at the repo root, not under app/
data/panchangam_YYYY.pkl    # Pre-computed yearly caches (2021–2030); source for the SQL seed files — at the repo root, not under app/
```

### Why this structure exists

**`core/astronomy/`** contains pure astronomical functions. They take `datetime` and coordinate/timezone values as inputs and return floats, ints, or strings. They have zero knowledge of HTTP, Pydantic models, or persistence. They are independently testable.

**`core/calendar/`** aggregates astronomy into meaningful calendar objects. `panchangam.py::get_panchangam_data()` is the single orchestration point: it calls into `core/astronomy/`, builds a `PanchangamData` Pydantic object, and returns it. It is used directly by `features/panchangam/service.py` as the live-computation fallback for any date not yet in the DB.

**`features/<name>/`** is a vertical slice: its `router.py` is the HTTP boundary (parses/validates query params, obtains a service via FastAPI `Depends`, delegates to it, translates domain errors to HTTP status codes) and its `service.py` sits between the router and persistence. `PanchangamService.get_by_date()`/`get_by_month()` read through the `PanchangamRepositoryPort`, falling back to `get_panchangam_data()` only when a date is missing from the database. A feature with no feature-local service (`settings`) leans on a shared `services/` module instead — `features/settings/router.py` depends on `services/settings_service.py::SettingsService` (see "Ports & adapters" below for why that service lives outside the feature folder). A feature that has been migrated to ports & adapters (see below) never imports a concrete `db/` repository from its `service.py`/`router.py` at all — only its own `ports.py` and the concrete adapter bound in `api/deps.py`.

**`db/`** is the Postgres persistence layer (SQLModel), untouched by the feature-folder split because several of its modules back more than one feature. The engine is built in `db/database.py` from a `DATABASE_URL` connection string read from the environment (a Neon Postgres URL, e.g. `postgresql://user:password@host/db?sslmode=require`) — no credentials are hardcoded. `PanchangamRepository` (in `features/panchangam/repository.py`, the concrete adapter for `PanchangamRepositoryPort`) is the only place that talks to the database for panchangam data — getters (`get_by_date`, `get_by_date_range`, `get_by_month`) and setters (`upsert`, `upsert_many`). `db/database.py::init_db()` ensures the schema exists at startup (idempotent); the database is seeded out-of-band by applying `db/sql/01_schema.sql` and `db/sql/02_seed.sql` to Neon/Postgres via `psql`. The server does not seed itself at runtime.

**`features/panchangam/legacy_router.py`** is the one surviving unversioned/legacy router, colocated with its v1 sibling since both belong to the same feature. Route handlers (whether here or in a feature's `router.py`) parse and validate query parameters, obtain a service via FastAPI `Depends`, and delegate to it. They must not contain domain logic, computations, or direct astronomy/DB calls.

**`schemas/`** holds only the Pydantic models shared across features (or consumed by `db/`/`core/calendar/`, which don't import from `features/`). Everything else lives in the owning feature's `schemas.py`/`schemas/` package. The primary response schema is `PanchangamData` in `schemas/panchangam_data.py` — it is also the type returned by both the repository and the live-computation fallback.

**`utils/`** holds domain enums (`Nakshatra`, `Thithi`, `Paksha`, `MalayalamMasa`), `roles.py`, `lifespan.py`, and `santhigiri_events.py` — anything imported by `core/`/`db/` (which must not depend on `features/`) or genuinely shared across features. The offline pickle-cache scripts (`cache_*.py`, `rebuild_events.py`) live in `features/santhigiri_events/offline_cache/` instead, since they are single-consumer maintenance tooling for that one feature's cache pipeline, not a cross-cutting concern — they are run manually to rebuild the pickle files, which are then read by `scripts/gen_seed_sql.py` to regenerate the `db/sql/*.sql` seed files. They are not called at runtime.

### Ports & adapters

The target pattern for every feature going forward is **ports and adapters**: a feature's service depends only on an abstract `Protocol` describing what it needs from persistence, never on a concrete SQLModel repository class. `features/auth/` is the canonical, fully-migrated example — read it before migrating another feature. `features/santhigiri_events/` is migrated the same way. `features/settings/` is migrated too, with one deliberate variation: its `ports.py`/`repository.py` live under `features/settings/` as usual, but the service itself (`SettingsService`) stays at `services/settings_service.py` rather than moving to `features/settings/service.py`, because — unlike `AuthService`/`SanthigiriEventService` — it's a dependency of 3+ other features' own services (`panchangam`, `santhigiri_events`, the panchangam generation path) and `api/deps.py`, not just its own router; see the "services/" entry above and CLAUDE.md's layer-boundary rule against importing another feature's `service.py` directly.

`features/etag/` follows the same "port lives in the feature, orchestration stays in `services/`" shape as `settings`, but with a further wrinkle: `services/etag_service.py` isn't a class-based service at all — it's the shared payload-builder/ETag-compute module every feature's router calls into, so there's no single `EtagService` dataclass to hold the port. Instead, `conditional_json_response()` and `refresh_etags()` take `etag_repository: EtagRepositoryPort` and `unit_of_work: UnitOfWork` as plain parameters, resolved by the caller (a router via `api/deps.py`'s `EtagRepositoryDep`/`UnitOfWorkDep`, or a feature's own `service.py` that already holds those fields, e.g. `SanthigiriEventService`). `features/etag/ports.py` has no DTO — unlike `AppSettingGet`/`UserGet`, the value crossing the boundary is a bare ETag string keyed by dataset name, so there is no row shape to translate.

`features/panchangam/` is migrated too, with its own wrinkle: `ports.py`'s `PanchangamRepositoryPort` has no new DTOs at all. `PanchangamData` (`schemas/panchangam_data.py`) and `SanthigiriEvent` (`utils/santhigiri_events.py`) are already plain, framework-independent Pydantic/dataclass domain objects — not SQLModel rows — so `PanchangamRepository` (`features/panchangam/repository.py`) returns and accepts them directly rather than translating to/from a separate boundary type. `PanchangamService` (`features/panchangam/service.py`) depends on the port alone, same as a canonical migrated feature. `PanchangamGenerationService` (`features/panchangam/generation_service.py`), the write-path sibling built for the admin `/generate` endpoint, is shaped like `SanthigiriEventService`: a frozen `@dataclass` holding `PanchangamRepositoryPort`, `SettingsService`, `EtagRepositoryPort`, and `UnitOfWork` as fields, plus the raw `Session` that `services/etag_service.refresh_etags` still needs to build payloads — wired up by `api/deps.py::get_panchangam_generation_service` and injected into `generation_router.py` via `Depends`, never constructed by hand in the router.

`settings`, `etag`, and `panchangam` are otherwise built exactly like a migrated feature's service: depending on the port + `UnitOfWork`, never the concrete adapter. A feature without a `ports.py` (`guruvani`) is still on the older "service talks to a concrete `db/*_repository.py` directly" style — acceptable for now, but do not build new patterns on it (see "Known Issues and Active Work").

The pieces, using `features/auth/` as the reference:

- **`ports.py`** defines three things: the repository `Protocol` (`AuthRepositoryPort`), frozen `@dataclass` DTOs for data crossing the boundary (`UserGet`, `UserCreate`, `UserUpdate`, `UserWithCredentials`), and any domain exceptions the port can raise (`UserNotFoundException`). Nothing in `ports.py` imports SQLModel or a session.
- **The adapter** (`features/auth/auth_repository.py`, or `features/santhigiri_events/repository.py`) is a concrete class implementing the port against SQLModel: it takes a `Session`, and every method translates ORM rows to/from the port's DTOs (e.g. `AuthRepository._user_row_to_user_get`) — mirroring the `to_dto`/`from_dto` convention already used on `db/models/santhigiri_event.py`.
- **`service.py`** is a frozen `@dataclass` (not a plain `__init__`) holding the port and a `UnitOfWork` (`core/ports/unit_of_work.py`) as fields — e.g. `AuthService(auth_repository: AuthRepositoryPort, uow: UnitOfWork)`. It imports the port's Protocol and DTOs, never the concrete adapter class or `Session`. Request-schema → DTO conversion (and the reverse, DTO → response-schema) happens inside `service.py` methods (e.g. `AuthService._user_get_to_get_user_response`), not in the router.
- **`db/unit_of_work.py::SqlUnitOfWork`** is the one concrete `UnitOfWork` adapter, wrapping a `Session`. A mutation wraps the repository call(s) in `with self.unit_of_work as uow: ...; uow.commit()` (or lets a shared commit helper like `services/etag_service.refresh_etags` do the commit, if the mutation must land atomically with an ETag refresh).
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

The `santhigiri_event` table is the **authoritative, editable** definition store for event types (name, description, matching condition), seeded from `utils/santhigiri_events.py` but authoritative thereafter. It is read for the `GET /panchangam/events` reference list (via `db/reference_repository.py`) and written through the `SanthigiriEventsRepositoryPort` adapter (`features/santhigiri_events/repository.py`). `features/santhigiri_events/service.py` orchestrates create/update/delete against that port: each mutation commits **atomically with an ETag refresh** (`services/etag_service.py`) — always the `events` reference dataset, plus every `year` dataset whose cascade-deleted occurrences changed on a delete — so cached clients revalidate correctly. Editing a definition does **not** by itself recompute which dates the event falls on — that's a separate step, either the offline cache pipeline (see "Adding a new Santhigiri event") or the live DB-driven `POST /panchangam/events/{event_id}/occurrences` / `POST /panchangam/events/generate` endpoints (`SanthigiriEventService.generate_occurrences`/`generate_all_occurrences_streaming`), which (re)compute an event's (or every event's) occurrence dates over a year range directly from the DB's panchangam data and overwrite `santhigiri_event_dates` for that range.

An event definition may also set `yields_to_event_id`, pointing at another event it defers to: when generating this event's occurrences via the live path above, any date where the referenced event's condition also matches is dropped from this event's own occurrence set. This is resolved live against the same year's panchangam data on every generation run (not a static precomputed exclusion), and only affects the live generation path — it has no offline-pipeline equivalent. Used to resolve same-date collisions between events that can both plausibly claim a day, e.g. `JANMAGRIHA_THEERTHA_YATHRA` (every Chothi Nakshatra transition) yields to `NAVAPOOJITHAM` (the last Chothi-in-Chingam day) since a year's Navapoojitham date is also, incidentally, a routine Chothi transition.

---

## Mandatory Conventions

Follow these rules without exception.

### Layer import boundaries

- Route handlers in `features/<name>/router.py` (or `features/panchangam/legacy_router.py`) must only parse HTTP params and delegate to that feature's `service.py` (or a shared `services/` module). They must not call a `db/` repository or `core/astronomy/`/`core/calendar/` directly.
- `core/astronomy/` functions must not import from `api/`, `features/`, `schemas/`, or `utils/lifespan.py`.
- `core/calendar/` functions must not import from `api/` or `features/`.
- `db/` (models, `reference_repository.py`, etc.) must not import from `api/`, `features/`, or `services/` — with one narrow, deliberate exception: a table model backing a migrated feature (e.g. `db/models/santhigiri_event.py`) may import that feature's `ports.py` for its `to_dto`/`from_dto` conversion, since the port's DTOs *are* that row's serialization contract. Nothing else in `db/` gets this exception.
- Pydantic models belong in `schemas/` (if shared across features) or `features/<name>/schemas.py` (if feature-local). Do not define response models inside `core/` or `utils/`.
- A feature's `service.py` may import shared `services/` modules (`etag_service`, `settings_service`) and `db/`, but other features must not import one feature's `service.py`/`router.py`/`schemas.py` directly — go through the shared layers instead.
- A feature migrated to ports & adapters (see "Ports & adapters" above) must not have its `service.py` or `router.py` import a concrete repository/adapter class directly — depend on the port (`Protocol`) and get the concrete instance via `api/deps.py`.

### Business logic placement

- All astronomical calculations go in `core/astronomy/`.
- All calendar/domain aggregation goes in `core/calendar/`.
- Event definitions go in `utils/santhigiri_events.py`.
- Cache management scripts go in `features/santhigiri_events/offline_cache/cache_*.py`.
- No business logic may live inside a route handler.

### Adding a new astronomical value

1. Implement the raw calculation function in the appropriate `core/astronomy/` file.
2. Call it from `core/calendar/panchangam.py::get_panchangam_data()`.
3. Add the field to `schemas/panchangam_data.py::PanchangamData`.
4. The route handler picks it up automatically — do not touch the route.

### Adding a new Santhigiri event

1. Define the event in `utils/santhigiri_events.py` with the appropriate `EventCondition`.
2. If condition-based (fixed English/Malayalam date, Nakshatra, Thithi, or Pournami), add it to `_COMMON_EVENTS` in `features/santhigiri_events/offline_cache/cache_common_events.py`.
3. If it uses "last occurrence" logic (like Navapoojitham or Shishyapoojitha birthday), write a dedicated `features/santhigiri_events/offline_cache/cache_<event_name>.py` following the pattern in `cache_navapoojitham.py`.
4. Run the appropriate cache script offline to rebuild the pickle files.
5. The event will appear in `PanchangamData.santhigiri_significant_dates` in the API response.

### Adding a new API endpoint

1. If the endpoint belongs to an existing feature, add it to that feature's `features/<name>/router.py` (or a new `features/<name>/<sub>_router.py` alongside it, as `panchangam` does for `generation_router.py`). For a genuinely new feature, create `features/<name>/` with `router.py` (+ `service.py`/`schemas.py`/`schemas/` as needed) following the layout of an existing feature. Do not add endpoints to an existing router file unless they are closely related to that feature.
2. Define request params as a Pydantic `BaseModel` in `features/<name>/schemas.py` (feature-local), or in top-level `schemas/` only if the schema must also be consumed by `db/`, `core/calendar/`, or another feature.
3. Register the new router in `main.py` using `app.include_router(...)`. For a versioned router, pass the version prefix at inclusion time, e.g. `app.include_router(router, prefix="/api/v1")` — routers themselves should not hardcode the version segment (see "Versioning without a `v1/` directory" above).
4. All domain logic the endpoint needs must be implemented in `core/` or a `service.py` orchestrator (the feature's own, or a shared `services/` module for cross-feature concerns) — never in the handler.
5. **Choose an authorization level with `require_role`.** Read endpoints that expose public panchangam data use `require_role(Role.ANONYMOUS)` (permits anonymous, still validates any supplied token). Any endpoint that **mutates** state must be gated at the appropriate role — event-definition writes and user management require `require_role(Role.ADMIN)`. Apply the guard per-endpoint via the decorator's `dependencies=[...]` when a router mixes privilege levels, or at the router level when they are uniform.

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

The Malayalam day is computed by walking backwards through days' end-of-Modyana samples to find when the current raasi began. Implemented in `core/calendar/kollavarsham.py`.

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
- `GET /panchangam/?date_str=YYYY-MM-DD` — legacy version; returns full Panchangam for a single day
- `GET /panchangam/monthly?year=YYYY&month=MM` — legacy version; returns full Panchangam for every day in the month

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

Panchangam parameters default to today's date, Santhigiri Ashram coordinates, and `Asia/Kolkata` timezone.

---

## Running Tests

```bash
pytest tests/
```

Current coverage:

- `tests/test_is_pournami.py` — 24 parametrized test cases verifying full moon detection against known dates for 2022 and 2026.
- `tests/test_etag.py` — `stable_hash`/`If-None-Match` helpers plus end-to-end conditional-request behaviour of the year and enum-reference endpoints.
- `tests/test_auth.py` — JWT login/refresh, token-type enforcement, and the `require_role` guards (401/403).
- `tests/test_santhigiri_event_crud.py` — event-definition CRUD end-to-end, including admin-role enforcement and ETag invalidation.
- `tests/db/` — repository-layer unit tests (round-trips, cascade deletes, event derivation).
- `tests/test_panchangam.py` — skeleton (not yet implemented).

Tests use an in-memory SQLite engine (the FK pragma listener in `db/database.py` makes `ON DELETE CASCADE` behave as it does on Postgres); see `tests/conftest.py`. The API tests override `get_session` onto a seeded engine and drive the app with `TestClient` (see `tests/test_etag.py` for the fixture pattern).

When adding new astronomical calculations, add parametrized tests to `tests/` that verify against known Panchangam dates. Cross-check expected values against published physical Panchangams or the Drik Panchang reference.

---

## Caching Strategy

This is the most performance-critical aspect of the system. Understand it before making any changes.

### Runtime store (Postgres via `PanchangamRepository`)

Both endpoints are served through `features/panchangam/service.py`, which reads via `features/panchangam/repository.py::PanchangamRepository` (the `PanchangamRepositoryPort` adapter) against the Neon/Postgres database configured by `DATABASE_URL` (seeded for 2021–2030). This makes the monthly endpoint essentially free — it serves pre-computed rows without any Skyfield calls. If a date is missing from the DB, `get_panchangam_data()` computes it live; the result is returned but **not** written back (unlike the retired in-memory cache), so a real gap must be closed by re-applying the SQL seed files rather than relying on organic backfill.

At startup, the FastAPI lifespan (`utils/lifespan.py`) calls `init_db()`, which only ensures the schema exists (idempotent). The database is seeded out-of-band by applying `db/sql/01_schema.sql` and `db/sql/02_seed.sql` to the Neon/Postgres target with `psql`; the server never seeds itself at runtime.

### Function-level LRU caches

Several functions in `core/astronomy/` and `core/calendar/` are decorated with `@lru_cache`. Key examples:

- `get_sunrise_sunset()` in `core/astronomy/sunrise_sunset.py`
- `get_thithi_transition_by_date()` in `core/astronomy/thithi_transition.py`
- `get_kollavarsham_date()` and `get_madhyahnam_raasi()` in `core/calendar/kollavarsham.py`
- `get_sun_sidereal_longitude()` in `core/astronomy/calculations.py`

These are critical for the transition-detection logic, which calls the same function for the previous day, current day, and next day. Without LRU caching these would be redundantly recalculated.

### Offline cache management (pickle files)

The `data/panchangam_YYYY.pkl` files are pre-computed offline using scripts in `features/santhigiri_events/offline_cache/`:

1. `cache_crud.py::buildcache(year)` — computes all 365 days for a year and writes a pickle file.
2. `cache_common_events.py::cache_common_events()` — reads all pickle files, matches simple event conditions, and rewrites them with `santhigiri_significant_dates` populated.
3. `cache_navapoojitham.py::cache_navapoojitham()` — same for Guru birthday.
4. `cache_sishya_bday.py::cache_sishya_bday()` — same for Shishyapoojitha birthday.
5. `cache_chothi_theerthayathra.py::cache_chothi_theerthayathra()` — same for Chothi pilgrimage dates.

**When to rebuild:** If you change computation logic in `core/astronomy/` or `core/calendar/`, or add/modify Santhigiri events, regenerate the pickle files offline, commit them, then re-run `scripts/gen_seed_sql.py` to regenerate `db/sql/*.sql` and apply those files to the target Neon/Postgres database with `psql`. The server never writes pickle files or the DB at runtime.

### Cache rebuild order

1. Run `buildcache(year)` for each affected year.
2. Run event caching scripts in any order — they are independent of each other.
3. Re-run `scripts/gen_seed_sql.py` and apply the regenerated `db/sql/*.sql` to the Neon/Postgres database (`DATABASE_URL`) — this is the step that actually changes what the API serves.

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

- `core/calendar/santhigiri_significant_dates.py` is an empty placeholder. The live computation path (`get_santhigiri_significant_dates_without_occurances`) is commented out in `panchangam.py` — Santhigiri event dates come from the DB only (seeded offline from the pickle cache), so a date outside 2021–2030 served via the live-computation fallback will have an empty `santhigiri_significant_dates`.
- `core/calendar/panchangam.py::get_panchangam()` (the dict-returning version) is a legacy function superseded by `get_panchangam_data()`. Do not add new callers of `get_panchangam()`.
- The daily endpoint (`GET /panchangam/`) accepts `latitude`, `longitude`, and `timezone` as query parameters but `PanchangamService`/`get_panchangam_data()` never receive them — hardcoded defaults are used throughout. This is a known inconsistency, unrelated to the DB migration.
- The live-computation fallback in `PanchangamService` (used when a date is missing from the DB) does not write its result back to the database. A persistent gap must be closed by regenerating and re-applying the `db/sql/*.sql` seed files, not by traffic alone.
- `NAKSHATRA_TRANSITION_STEP_DAYS` is `0.01` for 2021–2027 and 2029–2030. For 2028 it must be `0.05`. This is a fragile per-year constant; treat any change with caution and validate with the transition miss checker on startup.
- `features/auth/`, `features/santhigiri_events/`, `features/settings/`, `features/etag/`, and `features/panchangam/` have been migrated to the ports & adapters pattern (see "Ports & adapters" above). `guruvani` still has its `service.py` talk to a concrete `db/*_repository.py` class directly.
- The whole `tests/` suite predates the move of the codebase under `app/` and still imports top-level modules (`import db.database`, `from core.calendar...`, etc.) that no longer exist at that path — every test file needs its imports updated to `app.db...`/`app.core...` before the suite can run again. This is a large, mechanical, repo-wide fix that has not been done yet.

---

## What Not To Do

- Do not put business logic in route handlers. If a route handler is doing anything beyond parsing params and calling `PanchangamService`, move the logic to `services/` or `core/`.
- Do not call `core/astronomy/`, `core/calendar/`, or a concrete `db/` repository directly from route handlers — go through `features/panchangam/service.py` (or the relevant feature's `service.py`).
- Do not define new Pydantic models inside `core/` or `db/` modules.
- Do not modify the pickle files by hand. Always use the cache scripts, then re-run `scripts/gen_seed_sql.py` and re-apply `db/sql/*.sql` to the Postgres database.
- Do not add new event definitions in `core/` or `api/`. All event definitions belong in `utils/santhigiri_events.py`.
- Do not change `NAKSHATRA_TRANSITION_STEP_DAYS` without re-validating every year's cache with the transition miss checker.
- Do not assume the daily endpoint passes user-supplied coordinates to the computation — check the route handler first.
- Do not hardcode Malayalam or Sanskrit names as string literals in new code. Use `NAKSHATRA_NAMES`, `THITHI_NAMES`, or the appropriate enum from `utils/`.
