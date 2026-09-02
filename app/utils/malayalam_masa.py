from enum import Enum
from functools import lru_cache
from typing import Dict


class MalayalamMasa(Enum):
    """A Malayalam solar month. ``name`` is the stable slug used everywhere
    internally; localized display text lives in the DB ``malayalam_masa`` table
    (see ``app/db/reference_names.py``)."""

    MEDAM = 1
    IDAVAM = 2
    MITHUNAM = 3
    KARKIDAKAM = 4
    CHINGAM = 5
    KANNI = 6
    THULAM = 7
    VRISCHIKAM = 8
    DHANU = 9
    MAKARAM = 10
    KUMBHAM = 11
    MEENAM = 12

    def __init__(self, id: int):
        self.id = id

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
        }
