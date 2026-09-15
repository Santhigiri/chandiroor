"""
Shared fixtures for the DB-layer test suite.

The unit fixtures use a shared in-memory SQLite database (``sqlite://`` with a
``StaticPool`` so every connection sees the same schema/data). Importing
``db.database`` registers its module-level ``PRAGMA foreign_keys = ON`` connect
listener against the SQLAlchemy ``Engine`` class, so FK enforcement and
``ON DELETE CASCADE`` behave exactly as they do in production.
"""
from __future__ import annotations

import datetime as _dt
import os
from typing import Callable, List, Optional

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

# db.database now requires DATABASE_URL (Postgres/Neon) at import time. The tests
# build their own in-memory SQLite engines and never touch the module-level
# engine, so a throwaway value just satisfies the import — no real connection is
# ever opened against it. Must be set before ``import db.database`` below.
os.environ.setdefault("DATABASE_URL", "sqlite://")

# core.config.Settings requires TVM_JWKS_URL at import time (there is no local
# fallback secret). The tests never make a real HTTP call to it — see
# `_mock_tvm_jwks` below, which patches the JWKS fetch to return an in-memory
# test keypair instead.
os.environ.setdefault("TVM_JWKS_URL", "http://tvm.invalid/.well-known/jwks.json")

# Importing db.database registers the shared "connect" pragma listener that
# turns foreign_keys ON for every SQLite connection, including our test engine.
import app.db.database  # noqa: F401
import app.db.models  # noqa: F401 — register every table on SQLModel.metadata
from app.db.seed import seed_lookup_tables

from app.core.astronomy.nakshatra_transition import NakshatraTransition
from app.core.astronomy.thithi_transition import ThithiTransition
from app.core.chandramasa.chandramasa_models import ChandraMasaDate
from app.core.chandramasa.enums.masa import ChandraMasa
from app.core.chandramasa.enums.masa_type import MasaType
from app.core.kollavarsham.kollavarsham import KollavarshamDate
from app.schemas.location import LocationInfo
from app.schemas.panchangam_data import PanchangamData
from app.utils.location import Location
from app.core.kollavarsham.enums.masa import MalayalamMasa
from app.core.astronomy.enums.nakshatra import Nakshatra
from app.utils.santhigiri_events import SanthigiriEvent
from app.core.astronomy.enums.thithi import Thithi

import app.core.jwks_client as jwks_client
from app.core.config import settings
from app.utils.roles import Role


# ── Engine / session fixtures ─────────────────────────────────────────────────

@pytest.fixture
def engine():
    """A fresh, isolated in-memory SQLite engine with the full schema created."""
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(eng)
    try:
        yield eng
    finally:
        SQLModel.metadata.drop_all(eng)
        eng.dispose()


@pytest.fixture
def session(engine):
    """A Session bound to the in-memory engine (schema only, no seed data)."""
    with Session(engine) as s:
        yield s


@pytest.fixture
def seeded_session(session):
    """A Session with the immutable lookup tables already seeded."""
    seed_lookup_tables(session)
    return session


# ── PanchangamData factory ────────────────────────────────────────────────────

@pytest.fixture
def make_panchangam_data() -> Callable[..., PanchangamData]:
    """
    Factory that builds a valid ``PanchangamData`` from the real domain enums.

    Datetimes are UTC-aware: the DB columns are TIMESTAMPTZ and
    ``db.models.types.UTCDateTime`` normalizes every round trip (on both
    SQLite and Postgres) to UTC-aware, so fixtures must be aware too for
    ``upsert`` → ``get_by_date`` round-trip comparisons to hold.
    """

    def _build(
        date: _dt.date,
        *,
        thithi: Thithi = Thithi.POORNIMA,
        nakshatra: Nakshatra = Nakshatra.CHOTHI,
        nazhika_from_sunrise: float = 12.5,
        kv_month: MalayalamMasa = MalayalamMasa.MEENAM,
        kv_day: int = 5,
        kv_year: int = 1201,
        chandra_masa: ChandraMasa = ChandraMasa.PHALGUNA,
        chandra_masa_day: int = 5,
        chandra_masa_type: MasaType = MasaType.NIJA,
        thithi_transitions: Optional[List[ThithiTransition]] = None,
        nakshatra_transitions: Optional[List[NakshatraTransition]] = None,
        santhigiri_significant_dates: Optional[List[SanthigiriEvent]] = None,
        location: Location = Location.TVM,
    ) -> PanchangamData:
        sunrise = _dt.datetime.combine(date, _dt.time(6, 15), tzinfo=_dt.timezone.utc)
        sunset = _dt.datetime.combine(date, _dt.time(18, 30), tzinfo=_dt.timezone.utc)
        day_start = _dt.datetime.combine(date, _dt.time.min, tzinfo=_dt.timezone.utc)

        if thithi_transitions is None:
            thithi_transitions = [
                ThithiTransition(
                    thithi=thithi,
                    start_time=day_start,
                    end_time=day_start + _dt.timedelta(hours=20),
                )
            ]
        if nakshatra_transitions is None:
            nakshatra_transitions = [
                NakshatraTransition(
                    nakshatra=nakshatra,
                    start_time=day_start,
                    end_time=day_start + _dt.timedelta(hours=20),
                )
            ]

        kv = KollavarshamDate(
            date=date,
            kv_day=kv_day,
            kv_month=kv_month.id,
            kv_year=kv_year,
        )

        cm = ChandraMasaDate(
            date=date,
            masa=chandra_masa.id,
            masa_day=chandra_masa_day,
            masa_type=chandra_masa_type.id,
        )

        return PanchangamData(
            date=date,
            kv=kv,
            chandra_masa=cm,
            thithi_transitions=thithi_transitions,
            nakshatra_transitions=nakshatra_transitions,
            thithi=thithi,
            nakshatra=nakshatra,
            sunrise=sunrise,
            sunset=sunset,
            nazhika_from_sunrise=nazhika_from_sunrise,
            santhigiri_significant_dates=santhigiri_significant_dates or [],
            location=LocationInfo.from_location(location),
        )

    return _build


# ── Temp-file DB for the on-disk schema test ──────────────────────────────────

@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """
    Point ``db.database`` at a throwaway on-disk SQLite file and return its engine.
    """
    import app.db.database as database

    db_path = tmp_path / "panchangam_test.db"
    test_engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )

    monkeypatch.setattr(database, "engine", test_engine)

    yield test_engine
    test_engine.dispose()


# ── TVM JWT test helpers ───────────────────────────────────────────────────────
#
# Chandiroor never mints tokens itself — it only verifies RS256 access tokens
# against TVM's JWKS (``app.core.jwks_client``). These helpers mint tokens
# shaped like a real TVM-issued one, signed with a throwaway in-memory test
# keypair, and patch the JWKS fetch so verification resolves against that same
# keypair instead of making a real HTTP call.

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwk as _jose_jwk
from jose import jwt as _jose_jwt

_TEST_KID = "test-key-1"
_test_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_test_private_pem = _test_private_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
).decode("utf-8")
_test_public_pem = (
    _test_private_key.public_key()
    .public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    .decode("utf-8")
)
_test_public_jwk = _jose_jwk.construct(_test_public_pem, algorithm="RS256").to_dict()
_test_public_jwk["kid"] = _TEST_KID


def mint_tvm_token(role: Role, user_id: int = 1, is_verified: bool = True) -> str:
    """Mint a throwaway RS256 access token shaped like a real TVM-issued one."""
    claims = {
        "userId": user_id,
        "role": role.name,
        "isVerified": is_verified,
        "iss": settings.tvm_jwt_issuer,
        "aud": settings.tvm_jwt_audience,
        "exp": _dt.datetime.now(_dt.timezone.utc) + _dt.timedelta(hours=1),
    }
    return _jose_jwt.encode(
        claims, _test_private_pem, algorithm="RS256", headers={"kid": _TEST_KID}
    )


def bearer_header(role: Role, user_id: int = 1) -> dict:
    """An ``Authorization`` header carrying a freshly minted test token."""
    return {"Authorization": f"Bearer {mint_tvm_token(role, user_id)}"}


@pytest.fixture(autouse=True)
def _mock_tvm_jwks(monkeypatch):
    """Resolve TVM's JWKS to the in-memory test keypair, never a real HTTP call."""
    monkeypatch.setattr(
        jwks_client, "_fetch_jwks", lambda: {_TEST_KID: _test_public_jwk}
    )
    jwks_client.reset_cache()
    yield
    jwks_client.reset_cache()
