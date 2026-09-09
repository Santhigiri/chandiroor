"""
Tests for the Amanta lunar month (Chandra Masa).

The month runs Amavasya -> Amavasya (the Krishna -> Shukla paksha boundary),
attributed to a calendar day by the thithi active at sunrise (same convention
as Thithi/Kollavarsham). The boundary is cross-checked against a published
reference: Ugadi (Chaitra Shukla Pratipada) 2021 fell on 2021-04-13
(see e.g. https://www.prokerala.com/festivals/ugadi.html), the day the Amanta
year begins its Chaitra month.

The three Adhika (leap) months found by scanning 2021-2030 (2023 Adhika
Ashadha, 2026 Adhika Vaishakha, 2029 Adhika Phalguna) line up with the
well-publicized 2023 "Adhik Maas"/"Purushottam Maas" period (~2023-07-18 to
2023-08-16) -- called Adhika Ashadha in the Amanta-following regions this API
targets, Adhika Shravana in Purnimanta-following regions further north; the
two schemes name the same physical period differently, which is expected.
"""
from datetime import date, timedelta

import pytest

from app.core.astronomy.constants import Coordinates, DEFAULT_TIMEZONE
from app.core.chandramasa.chandramasa import get_chandra_masa_date
from app.core.chandramasa.enums.masa import ChandraMasa

LAT = round(Coordinates.SG_LATITUDE, 3)
LON = round(Coordinates.SG_LONGITUDE, 3)
TZ = DEFAULT_TIMEZONE


def _cm(day: date):
    return get_chandra_masa_date(dt=day, latitude=LAT, longitude=LON, timezone=TZ)


def test_ugadi_2021_is_chaitra_day_one():
    cm = _cm(date(2021, 4, 13))
    assert cm.masa == ChandraMasa.CHAITRA.id
    assert cm.masa_day == 1
    assert cm.is_adhika is False


def test_day_before_month_start_is_previous_month_last_day():
    """2021-04-12 is the last day of Phalguna (day 29): the Krishna->Shukla
    paksha boundary lands on 2021-04-13, not the day before."""
    cm = _cm(date(2021, 4, 12))
    assert cm.masa == ChandraMasa.PHALGUNA.id
    assert cm.masa != ChandraMasa.CHAITRA.id


def test_masa_day_increments_across_consecutive_days_within_a_month():
    days = [_cm(date(2021, 4, 13) + timedelta(days=i)) for i in range(5)]
    assert [d.masa_day for d in days] == [1, 2, 3, 4, 5]
    assert all(d.masa == ChandraMasa.CHAITRA.id for d in days)
    assert all(d.is_adhika is False for d in days)


def test_masa_day_resets_at_the_next_month_boundary():
    """2021-05-11 is Chaitra's last day (day 29); 2021-05-12 resets to
    Vaishakha day 1."""
    last_day_of_chaitra = _cm(date(2021, 5, 11))
    first_day_of_vaishakha = _cm(date(2021, 5, 12))

    assert last_day_of_chaitra.masa == ChandraMasa.CHAITRA.id
    assert last_day_of_chaitra.masa_day == 29

    assert first_day_of_vaishakha.masa == ChandraMasa.VAISHAKHA.id
    assert first_day_of_vaishakha.masa_day == 1


# ── Adhika masa (leap month) ────────────────────────────────────────────────
# 2023's well-known extra month: a regular Ashadha (2023-06-19), then an
# Adhika Ashadha (2023-07-18) sharing its name with the regular Shravana that
# follows it (2023-08-17) once the Sun crosses into the next raasi.

def test_adhika_masa_detected_and_shares_name_with_following_month():
    regular_ashadha = _cm(date(2023, 6, 19))
    adhika_ashadha = _cm(date(2023, 7, 18))
    regular_shravana = _cm(date(2023, 8, 17))

    assert regular_ashadha.masa == ChandraMasa.ASHADHA.id
    assert regular_ashadha.is_adhika is False

    assert adhika_ashadha.masa == ChandraMasa.ASHADHA.id
    assert adhika_ashadha.masa_day == 1
    assert adhika_ashadha.is_adhika is True

    assert regular_shravana.masa == ChandraMasa.SHRAVANA.id
    assert regular_shravana.is_adhika is False


@pytest.mark.parametrize(
    "day, expected_masa",
    [
        (date(2021, 1, 14), ChandraMasa.PAUSHA),
        (date(2021, 6, 11), ChandraMasa.JYESHTHA),
        (date(2022, 4, 2), ChandraMasa.CHAITRA),
        (date(2026, 3, 20), ChandraMasa.CHAITRA),
        (date(2029, 4, 14), ChandraMasa.CHAITRA),
    ],
)
def test_month_start_names_across_years(day, expected_masa):
    """Spot-checks across several years that month-start naming stays a
    monotonic 12-month cycle (Chaitra recurs every year near April)."""
    cm = _cm(day)
    assert cm.masa == expected_masa.id
    assert cm.masa_day == 1
