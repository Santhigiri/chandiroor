from enum import Enum
from functools import lru_cache
from typing import Dict
from .paksha import Paksha


class Thithi(Enum):
    # Shukla Paksha (1–15)
    PRATHAMA_SHUKLA = (1, Paksha.SHUKLA, 1, "പ്രതിപദ", "Prathama")
    DWITHIYA_SHUKLA = (2, Paksha.SHUKLA, 2, "ദ്വിതീയ", "Dwitiya")
    TRITHIYA_SHUKLA = (3, Paksha.SHUKLA, 3, "തൃതീയ", "Tritiya")
    CHATURTHI_SHUKLA = (4, Paksha.SHUKLA, 4, "ചതുർത്ഥി", "Chaturthi")
    PANCHAMI_SHUKLA = (5, Paksha.SHUKLA, 5, "പഞ്ചമി", "Panchami")
    SHASHTHI_SHUKLA = (6, Paksha.SHUKLA, 6, "ഷഷ്ഠി", "Shashthi")
    SAPTAMI_SHUKLA = (7, Paksha.SHUKLA, 7, "സപ്തമി", "Saptami")
    ASHTAMI_SHUKLA = (8, Paksha.SHUKLA, 8, "അഷ്ടമി", "Ashtami")
    NAVAMI_SHUKLA = (9, Paksha.SHUKLA, 9, "നവമി", "Navami")
    DASHAMI_SHUKLA = (10, Paksha.SHUKLA, 10, "ദശമി", "Dashami")
    EKADASHI_SHUKLA = (11, Paksha.SHUKLA, 11, "ഏകാദശി", "Ekadashi")
    DWADASHI_SHUKLA = (12, Paksha.SHUKLA, 12, "ദ്വാദശി", "Dwadashi")
    TRAYODASHI_SHUKLA = (13, Paksha.SHUKLA, 13, "ത്രയോദശി", "Trayodashi")
    CHATURDASHI_SHUKLA = (14, Paksha.SHUKLA, 14, "ചതുര്ദശി", "Chaturdashi")
    POORNIMA = (15, Paksha.SHUKLA, 15, "പൗർണമി", "Purnima")

    # Krishna Paksha (1–15)
    PRATHAMA_KRISHNA = (16, Paksha.KRISHNA, 1, "പ്രതിപദ", "Prathama")
    DWITHIYA_KRISHNA = (17, Paksha.KRISHNA, 2, "ദ്വിതീയ", "Dwitiya")
    TRITHIYA_KRISHNA = (18, Paksha.KRISHNA, 3, "തൃതീയ", "Tritiya")
    CHATURTHI_KRISHNA = (19, Paksha.KRISHNA, 4, "ചതുർത്ഥി", "Chaturthi")
    PANCHAMI_KRISHNA = (20, Paksha.KRISHNA, 5, "പഞ്ചമി", "Panchami")
    SHASHTHI_KRISHNA = (21, Paksha.KRISHNA, 6, "ഷഷ്ഠി", "Shashthi")
    SAPTAMI_KRISHNA = (22, Paksha.KRISHNA, 7, "സപ്തമി", "Saptami")
    ASHTAMI_KRISHNA = (23, Paksha.KRISHNA, 8, "അഷ്ടമി", "Ashtami")
    NAVAMI_KRISHNA = (24, Paksha.KRISHNA, 9, "നവമി", "Navami")
    DASHAMI_KRISHNA = (25, Paksha.KRISHNA, 10, "ദശമി", "Dashami")
    EKADASHI_KRISHNA = (26, Paksha.KRISHNA, 11, "ഏകാദശി", "Ekadashi")
    DWADASHI_KRISHNA = (27, Paksha.KRISHNA, 12, "ദ്വാദശി", "Dwadashi")
    TRAYODASHI_KRISHNA = (28, Paksha.KRISHNA, 13, "ത്രയോദശി", "Trayodashi")
    CHATURDASHI_KRISHNA = (29, Paksha.KRISHNA, 14, "ചതുര്ദശി", "Chaturdashi")
    AMAVASYA = (30, Paksha.KRISHNA, 15, "അമാവാസി", "Amavasya")

    def __init__(self, id: int, paksha: Paksha, day: int, ml: str, en: str):
        self.id = id
        self.paksha = paksha
        self.day = day
        self.ml = ml
        self.en = en

    @classmethod
    @lru_cache()
    def _lookup(cls) -> Dict[int, "Thithi"]:
        return {item.id: item for item in cls}


    @classmethod
    def from_id(cls, id: int)-> "Thithi":
        return cls._lookup()[id]

    def to_dict(self):
        return {
            "name": self.name,
            "id": self.id,
            "paksha": self.paksha.to_dict(),
            "ml": self.ml,
            "en": self.en
        }
