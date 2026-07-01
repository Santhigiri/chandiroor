"""
Integration tests for db/migrate.py against the real pickle cache.

Only the 2022 pickle is loaded (via a monkeypatched ``load_cache``) to keep the
suite fast while still exercising the full seed → upsert_many → read-back path
on genuine PanchangamData.
"""
import datetime
import pickle

import pytest
from sqlmodel import Session, select

import db.migrate as migrate
from db.database import init_db
from db.migrate import _is_db_populated, init_db_from_pickle
from db.models.panchangam import Panchangam as PanchangamRow
from db.repository import PanchangamRepository

PICKLE_2022 = "data/panchangam_2022.pkl"
KNOWN_POURNAMI = datetime.date(2022, 1, 17)


def _load_2022():
    with open(PICKLE_2022, "rb") as f:
        return pickle.load(f)


def test_is_db_populated_false_on_empty(temp_db):
    init_db()
    with Session(temp_db) as s:
        assert _is_db_populated(s) is False


def test_init_db_from_pickle_populates(temp_db, monkeypatch):
    monkeypatch.setattr(migrate, "load_cache", _load_2022)
    cache = _load_2022()

    init_db_from_pickle()

    with Session(temp_db) as s:
        assert _is_db_populated(s) is True
        assert len(s.exec(select(PanchangamRow)).all()) == len(cache)

        pd = PanchangamRepository(s).get_by_date(KNOWN_POURNAMI)
        assert pd is not None
        assert pd.date == KNOWN_POURNAMI
        assert pd.is_pournami is True


def test_init_db_from_pickle_skips_when_populated(temp_db, monkeypatch):
    calls = {"n": 0}

    def counting_load():
        calls["n"] += 1
        return _load_2022()

    monkeypatch.setattr(migrate, "load_cache", counting_load)

    init_db_from_pickle()          # first call imports
    init_db_from_pickle()          # second call short-circuits on populated DB

    assert calls["n"] == 1


def test_init_db_from_pickle_force_reimports(temp_db, monkeypatch):
    calls = {"n": 0}

    def counting_load():
        calls["n"] += 1
        return _load_2022()

    monkeypatch.setattr(migrate, "load_cache", counting_load)
    cache = _load_2022()

    init_db_from_pickle()
    init_db_from_pickle(force=True)   # re-imports despite populated DB

    assert calls["n"] == 2
    with Session(temp_db) as s:
        # upsert replaces rather than duplicating — count stays at one year.
        assert len(s.exec(select(PanchangamRow)).all()) == len(cache)
