
from __future__ import annotations
from functools import lru_cache
from typing import Any, Dict, Optional
from enum import Enum


class Nakshatra(Enum):
    ASWATHI = (1, "അശ്വതി", "Ashwati")
    BHARANI = (2, "ഭരണി", "Bharani")
    KARTHIKA = (3, "കാർത്തിക", "Karthika")
    ROHINI = (4, "രോഹിണി", "Rohini")
    MAKAYIRAM = (5, "മകയിരം", "Makayiram")
    THIRUVATHIRA = (6, "തിരുവാതിര", "Thiruvathira")
    PUNARTHAM = (7, "പുണർതം", "Punartham")
    POOYAM = (8, "പൂയം", "Pooyam")
    AAYILYAM = (9, "ആയില്യം", "Aayilyam")
    MAKAM = (10, "മകം", "Makam")
    POORAM = (11, "പൂരം", "Pooram")
    UTHRAM = (12, "ഉത്രം", "Uthram")
    ATHAM = (13, "അത്തം", "Atham")
    CHITHIRA = (14, "ചിത്തിര", "Chithira")
    CHOTHI = (15, "ചോതി", "Chothi")
    VISHAKHAM = (16, "വിശാഖം", "Vishakham")
    ANIZHAM = (17, "അനിഴം", "Anizham")
    THRIKKETTA = (18, "തൃക്കേട്ട", "Thrikketta")
    MOOLAM = (19, "മൂലം", "Moolam")
    POORADAM = (20, "പൂരാടം", "Pooradam")
    UTHRADAM = (21, "ഉത്രാടം", "Uthradam")
    THIRUVONAM = (22, "തിരുവോണം", "Thiruvonam")
    AVITTAM = (23, "അവിട്ടം", "Avittam")
    CHATAYAM = (24, "ചതയം", "Chatayam")
    POORURUTTATHI = (25, "പൂരുരുട്ടാതി", "Pooruruttathi")
    UTHRATTATHI = (26, "ഉത്രട്ടാതി", "Uthrattathi")
    REVATHI = (27, "രേവതി", "Revathi")

    def __init__(self, id: int, ml: str, en: str):
        self.id = id
        self.ml = ml
        self.en = en

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
            "ml": self.ml,
            "en": self.en
        }
    
    @classmethod
    def get_or_none(cls, nakshatra: Optional[str]) -> Nakshatra | None:
        if nakshatra is None:
            return None
        try:
            return cls[nakshatra]
        except KeyError:
            return None
