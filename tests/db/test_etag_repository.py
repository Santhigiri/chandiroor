"""Tests for features/etag/repository.py — EtagRepository get/set round-trip."""
from sqlmodel import select

from features.etag.repository import EtagRepository
from db.models.dataset_etag import DatasetEtag


def test_get_missing_returns_none(session):
    assert EtagRepository(session).get("year:2099") is None


def test_set_then_get_round_trip(session):
    repo = EtagRepository(session)
    repo.set("year:2026", '"abc123"')
    session.commit()

    assert repo.get("year:2026") == '"abc123"'


def test_set_overwrites_existing(session):
    repo = EtagRepository(session)
    repo.set("enum:thithi", '"old"')
    session.commit()

    repo.set("enum:thithi", '"new"')
    session.commit()

    assert repo.get("enum:thithi") == '"new"'
    # Overwrite, not a second row.
    assert len(session.exec(select(DatasetEtag)).all()) == 1


def test_set_does_not_commit(session):
    """set() leaves the write uncommitted so callers can batch a transaction."""
    EtagRepository(session).set("year:2026", '"x"')
    session.rollback()

    assert EtagRepository(session).get("year:2026") is None
