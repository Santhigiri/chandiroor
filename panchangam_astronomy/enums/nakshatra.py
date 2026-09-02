
from __future__ import annotations
from functools import lru_cache
from typing import Any, Dict, Optional
from enum import Enum


class Nakshatra(Enum):
    """A lunar mansion. ``name`` is the stable slug used everywhere internally;
    localized display text lives in the DB ``nakshatra`` table (see
    ``app/db/reference_names.py``)."""

    ASWATHI = 1
    BHARANI = 2
    KARTHIKA = 3
    ROHINI = 4
    MAKAYIRAM = 5
    THIRUVATHIRA = 6
    PUNARTHAM = 7
    POOYAM = 8
    AAYILYAM = 9
    MAKAM = 10
    POORAM = 11
    UTHRAM = 12
    ATHAM = 13
    CHITHIRA = 14
    CHOTHI = 15
    VISHAKHAM = 16
    ANIZHAM = 17
    THRIKKETTA = 18
    MOOLAM = 19
    POORADAM = 20
    UTHRADAM = 21
    THIRUVONAM = 22
    AVITTAM = 23
    CHATAYAM = 24
    POORURUTTATHI = 25
    UTHRATTATHI = 26
    REVATHI = 27

    def __init__(self, id: int):
        self.id = id

    @classmethod
    @lru_cache()
    def _lookup(cls)-> Dict[int, Nakshatra]:
        return {item.id: item for item in cls}

    @classmethod
    def from_id(cls, id: int)-> Nakshatra:
        return cls._lookup()[id]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "id": self.id,
        }
    
    @classmethod
    def get_or_none(cls, nakshatra: Optional[str]) -> Nakshatra | None:
        if nakshatra is None:
            return None
        try:
            return cls[nakshatra]
        except KeyError:
            return None
