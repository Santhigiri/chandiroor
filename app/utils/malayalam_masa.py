from enum import Enum
from functools import lru_cache
from typing import Any, Dict


class MalayalamMasa(Enum):
    MEDAM = (1, "മേടം", "Medam")
    IDAVAM = (2, "ഇടവം", "Edavam")
    MITHUNAM = (3, "മിഥുനം", "Mithunam")
    KARKIDAKAM = (4, "കർക്കിടകം", "Karkidakam")
    CHINGAM = (5, "ചിങ്ങം", "Chingam")
    KANNI = (6, "കന്നി", "Kanni")
    THULAM = (7, "തുലാം", "Thulam")
    VRISCHIKAM = (8, "വൃശ്ചികം", "Vrischikam")
    DHANU = (9, "ധനു", "Dhanu")
    MAKARAM = (10, "മകരം", "Makaram")
    KUMBHAM = (11, "കുംഭം", "Kumbham")
    MEENAM = (12, "മീനം", "Meenam")

    def __init__(self, id: int, ml: str, en: str):
        self.id = id
        self.ml = ml
        self.en = en

    @classmethod
    @lru_cache()
    def _lookup(cls)-> Dict[int, "MalayalamMasa"]:
        return {item.id: item for item in cls}


    @classmethod
    def from_id(cls, id: int)-> "MalayalamMasa":
        return cls._lookup()[id]
    
    def to_dict(self)-> Dict:
        return {
            "name": self.name,
            "id": self.id,
            "ml": self.ml,
            "en": self.en
        }
