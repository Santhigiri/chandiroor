"""Canonical localized display names for the reference enums.

Display text was removed from the Python enums (``panchangam_astronomy.enums.*``
and ``app.utils.malayalam_masa``) so the domain layer carries only stable slugs
and structural data. The names live here instead — in the ``db`` layer, next to
the reference tables they populate — keyed by the enum's integer id.

``db/seed.py`` uses these to fill the ``paksha`` / ``thithi`` / ``nakshatra`` /
``malayalam_masa`` lookup tables for tests and local dev. Production databases
are seeded from ``db/sql/02_seed.sql`` (the parallel authoritative copy). Once a
row exists in the DB it is authoritative and editable; additional languages are
added there (new columns or an i18n side table), not here.
"""
from __future__ import annotations

from typing import Dict, TypedDict


class DisplayName(TypedDict):
    en: str
    ml: str


PAKSHA_NAMES: Dict[int, DisplayName] = {
    1: {"en": "Shukla Paksha", "ml": "ശുക്ലപക്ഷം"},
    2: {"en": "Krishna Paksha", "ml": "കൃഷ്ണപക്ഷം"},
}

NAKSHATRA_NAMES: Dict[int, DisplayName] = {
    1: {"en": "Ashwati", "ml": "അശ്വതി"},
    2: {"en": "Bharani", "ml": "ഭരണി"},
    3: {"en": "Karthika", "ml": "കാർത്തിക"},
    4: {"en": "Rohini", "ml": "രോഹിണി"},
    5: {"en": "Makayiram", "ml": "മകയിരം"},
    6: {"en": "Thiruvathira", "ml": "തിരുവാതിര"},
    7: {"en": "Punartham", "ml": "പുണർതം"},
    8: {"en": "Pooyam", "ml": "പൂയം"},
    9: {"en": "Aayilyam", "ml": "ആയില്യം"},
    10: {"en": "Makam", "ml": "മകം"},
    11: {"en": "Pooram", "ml": "പൂരം"},
    12: {"en": "Uthram", "ml": "ഉത്രം"},
    13: {"en": "Atham", "ml": "അത്തം"},
    14: {"en": "Chithira", "ml": "ചിത്തിര"},
    15: {"en": "Chothi", "ml": "ചോതി"},
    16: {"en": "Vishakham", "ml": "വിശാഖം"},
    17: {"en": "Anizham", "ml": "അനിഴം"},
    18: {"en": "Thrikketta", "ml": "തൃക്കേട്ട"},
    19: {"en": "Moolam", "ml": "മൂലം"},
    20: {"en": "Pooradam", "ml": "പൂരാടം"},
    21: {"en": "Uthradam", "ml": "ഉത്രാടം"},
    22: {"en": "Thiruvonam", "ml": "തിരുവോണം"},
    23: {"en": "Avittam", "ml": "അവിട്ടം"},
    24: {"en": "Chatayam", "ml": "ചതയം"},
    25: {"en": "Pooruruttathi", "ml": "പൂരുരുട്ടാതി"},
    26: {"en": "Uthrattathi", "ml": "ഉത്രട്ടാതി"},
    27: {"en": "Revathi", "ml": "രേവതി"},
}

# Keyed by Thithi.id (1–30). Shukla 1–15, Krishna 16–30; the paksha suffix is
# implied by the id and not part of the base name.
THITHI_NAMES: Dict[int, DisplayName] = {
    1: {"en": "Prathama", "ml": "പ്രതിപദ"},
    2: {"en": "Dwitiya", "ml": "ദ്വിതീയ"},
    3: {"en": "Tritiya", "ml": "തൃതീയ"},
    4: {"en": "Chaturthi", "ml": "ചതുർത്ഥി"},
    5: {"en": "Panchami", "ml": "പഞ്ചമി"},
    6: {"en": "Shashthi", "ml": "ഷഷ്ഠി"},
    7: {"en": "Saptami", "ml": "സപ്തമി"},
    8: {"en": "Ashtami", "ml": "അഷ്ടമി"},
    9: {"en": "Navami", "ml": "നവമി"},
    10: {"en": "Dashami", "ml": "ദശമി"},
    11: {"en": "Ekadashi", "ml": "ഏകാദശി"},
    12: {"en": "Dwadashi", "ml": "ദ്വാദശി"},
    13: {"en": "Trayodashi", "ml": "ത്രയോദശി"},
    14: {"en": "Chaturdashi", "ml": "ചതുര്ദശി"},
    15: {"en": "Purnima", "ml": "പൗർണമി"},
    16: {"en": "Prathama", "ml": "പ്രതിപദ"},
    17: {"en": "Dwitiya", "ml": "ദ്വിതീയ"},
    18: {"en": "Tritiya", "ml": "തൃതീയ"},
    19: {"en": "Chaturthi", "ml": "ചതുർത്ഥി"},
    20: {"en": "Panchami", "ml": "പഞ്ചമി"},
    21: {"en": "Shashthi", "ml": "ഷഷ്ഠി"},
    22: {"en": "Saptami", "ml": "സപ്തമി"},
    23: {"en": "Ashtami", "ml": "അഷ്ടമി"},
    24: {"en": "Navami", "ml": "നവമി"},
    25: {"en": "Dashami", "ml": "ദശമി"},
    26: {"en": "Ekadashi", "ml": "ഏകാദശി"},
    27: {"en": "Dwadashi", "ml": "ദ്വാദശി"},
    28: {"en": "Trayodashi", "ml": "ത്രയോദശി"},
    29: {"en": "Chaturdashi", "ml": "ചതുര്ദശി"},
    30: {"en": "Amavasya", "ml": "അമാവാസി"},
}

MASA_NAMES: Dict[int, DisplayName] = {
    1: {"en": "Medam", "ml": "മേടം"},
    2: {"en": "Edavam", "ml": "ഇടവം"},
    3: {"en": "Mithunam", "ml": "മിഥുനം"},
    4: {"en": "Karkidakam", "ml": "കർക്കിടകം"},
    5: {"en": "Chingam", "ml": "ചിങ്ങം"},
    6: {"en": "Kanni", "ml": "കന്നി"},
    7: {"en": "Thulam", "ml": "തുലാം"},
    8: {"en": "Vrischikam", "ml": "വൃശ്ചികം"},
    9: {"en": "Dhanu", "ml": "ധനു"},
    10: {"en": "Makaram", "ml": "മകരം"},
    11: {"en": "Kumbham", "ml": "കുംഭം"},
    12: {"en": "Meenam", "ml": "മീനം"},
}
