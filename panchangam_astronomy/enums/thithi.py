from __future__ import annotations
from enum import Enum
from functools import lru_cache
from typing import Dict
from .paksha import Paksha


class Thithi(Enum):
    """A lunar day. ``name`` is the stable slug used everywhere internally;
    localized display text lives in the DB ``thithi`` table (see
    ``app/db/reference_names.py``). ``paksha`` and ``day`` are structural."""

    # Shukla Paksha (1–15)
    PRATHAMA_SHUKLA = (1, Paksha.SHUKLA, 1)
    DWITHIYA_SHUKLA = (2, Paksha.SHUKLA, 2)
    TRITHIYA_SHUKLA = (3, Paksha.SHUKLA, 3)
    CHATURTHI_SHUKLA = (4, Paksha.SHUKLA, 4)
    PANCHAMI_SHUKLA = (5, Paksha.SHUKLA, 5)
    SHASHTHI_SHUKLA = (6, Paksha.SHUKLA, 6)
    SAPTAMI_SHUKLA = (7, Paksha.SHUKLA, 7)
    ASHTAMI_SHUKLA = (8, Paksha.SHUKLA, 8)
    NAVAMI_SHUKLA = (9, Paksha.SHUKLA, 9)
    DASHAMI_SHUKLA = (10, Paksha.SHUKLA, 10)
    EKADASHI_SHUKLA = (11, Paksha.SHUKLA, 11)
    DWADASHI_SHUKLA = (12, Paksha.SHUKLA, 12)
    TRAYODASHI_SHUKLA = (13, Paksha.SHUKLA, 13)
    CHATURDASHI_SHUKLA = (14, Paksha.SHUKLA, 14)
    POORNIMA = (15, Paksha.SHUKLA, 15)

    # Krishna Paksha (1–15)
    PRATHAMA_KRISHNA = (16, Paksha.KRISHNA, 1)
    DWITHIYA_KRISHNA = (17, Paksha.KRISHNA, 2)
    TRITHIYA_KRISHNA = (18, Paksha.KRISHNA, 3)
    CHATURTHI_KRISHNA = (19, Paksha.KRISHNA, 4)
    PANCHAMI_KRISHNA = (20, Paksha.KRISHNA, 5)
    SHASHTHI_KRISHNA = (21, Paksha.KRISHNA, 6)
    SAPTAMI_KRISHNA = (22, Paksha.KRISHNA, 7)
    ASHTAMI_KRISHNA = (23, Paksha.KRISHNA, 8)
    NAVAMI_KRISHNA = (24, Paksha.KRISHNA, 9)
    DASHAMI_KRISHNA = (25, Paksha.KRISHNA, 10)
    EKADASHI_KRISHNA = (26, Paksha.KRISHNA, 11)
    DWADASHI_KRISHNA = (27, Paksha.KRISHNA, 12)
    TRAYODASHI_KRISHNA = (28, Paksha.KRISHNA, 13)
    CHATURDASHI_KRISHNA = (29, Paksha.KRISHNA, 14)
    AMAVASYA = (30, Paksha.KRISHNA, 15)

    def __init__(self, id: int, paksha: Paksha, day: int):
        self.id = id
        self.paksha = paksha
        self.day = day

    @classmethod
    @lru_cache()
    def _lookup(cls) -> Dict[int, Thithi]:
        return {item.id: item for item in cls}


    @classmethod
    def from_id(cls, id: int)-> Thithi:
        return cls._lookup()[id]

    def to_dict(self):
        return {
            "name": self.name,
            "id": self.id,
            "paksha": self.paksha.to_dict(),
        }

    @classmethod
    def get_or_none(cls, thithi: str | None) -> Thithi | None:
        if thithi is None: 
            return None
        try:
            return cls[thithi]
        except KeyError:
            return None
        
