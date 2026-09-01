"""
Regression test for the multi-location Kollavarsham coordinate bug.

``core.calendar.kollavarsham.get_madhyahnam_raasi`` must thread the caller's
``latitude``/``longitude`` through to ``get_sunrise_sunset`` rather than
silently computing the Malayalam date from the ashram's sun times regardless of
the requested location. Once panchangam is multi-location, that must use the
location's own coordinates.
"""
from datetime import date

from unittest.mock import patch

import app.core.calendar.kollavarsham as kv


def test_get_madhyahnam_raasi_passes_coordinates_through():
    captured = {}

    real = kv.get_sunrise_sunset

    def _spy(date, latitude=None, longitude=None, timezone=None):
        captured["latitude"] = latitude
        captured["longitude"] = longitude
        return real(date, latitude, longitude, timezone)

    # A location that is NOT the Santhigiri default, to prove the coords flow.
    lat, lon, tz = 28.6139, 77.2090, "Asia/Kolkata"  # New Delhi
    kv.get_madhyahnam_raasi.cache_clear()
    with patch.object(kv, "get_sunrise_sunset", side_effect=_spy):
        kv.get_madhyahnam_raasi(dt=date(2026, 3, 20), latitude=lat, longitude=lon, timezone=tz)

    assert captured["latitude"] == lat
    assert captured["longitude"] == lon
