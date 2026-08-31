"""Tests for features/settings/repository.py — AppSettingRepository get/list/upsert."""
from sqlmodel import select

from features.settings.repository import AppSettingRepository
from db.models.app_setting import AppSetting


def test_get_missing_returns_none(session):
    assert AppSettingRepository(session).get("seed_year_range") is None


def test_upsert_then_get_round_trip(session):
    repo = AppSettingRepository(session)
    repo.upsert("seed_year_range", {"start_year": 2021, "end_year": 2030})
    session.commit()

    row = repo.get("seed_year_range")
    assert row is not None
    assert row.value == {"start_year": 2021, "end_year": 2030}


def test_upsert_overwrites_existing_not_duplicate(session):
    repo = AppSettingRepository(session)
    repo.upsert("max_generate_span_days", {"max_days": 366})
    session.commit()

    repo.upsert("max_generate_span_days", {"max_days": 400})
    session.commit()

    row = repo.get("max_generate_span_days")
    assert row.value == {"max_days": 400}
    assert len(session.exec(select(AppSetting)).all()) == 1


def test_upsert_does_not_commit(session):
    """upsert() leaves the write uncommitted so callers can batch a transaction."""
    AppSettingRepository(session).upsert("max_generate_span_days", {"max_days": 400})
    session.rollback()

    assert AppSettingRepository(session).get("max_generate_span_days") is None


def test_upsert_preserves_description_when_not_provided(session):
    repo = AppSettingRepository(session)
    repo.upsert(
        "event_cutoffs",
        {"nazhika_cutoff": 7.5, "transition_hour_cutoff": 3.0},
        description="Event day-attribution cutoffs",
    )
    session.commit()

    repo.upsert("event_cutoffs", {"nazhika_cutoff": 8.0, "transition_hour_cutoff": 3.0})
    session.commit()

    row = repo.get("event_cutoffs")
    assert row.description == "Event day-attribution cutoffs"
    assert row.value["nazhika_cutoff"] == 8.0


def test_list_all_sorted_by_key(session):
    repo = AppSettingRepository(session)
    repo.upsert("seed_year_range", {"start_year": 2021, "end_year": 2030})
    repo.upsert("astronomy_epsilons", {"nakshatra_epsilon": 1e-8, "kollavarsham_epsilon": 1e-6})
    session.commit()

    keys = [row.key for row in repo.list_all()]
    assert keys == sorted(keys)
    assert set(keys) == {"seed_year_range", "astronomy_epsilons"}
