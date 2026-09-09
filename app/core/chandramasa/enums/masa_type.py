from enum import Enum
from functools import lru_cache
from typing import Dict


class MasaType(Enum):
    """Classification of an Amanta lunar month by how many Sankrantis (solar
    raasi changes) fall within it. ``name`` is the stable slug used
    everywhere internally."""

    NIJA = 1     # regular month: exactly one Sankranti within it
    ADHIKA = 2   # leap month: no Sankranti within it
    KSHAYA = 3   # deficit month: two or more Sankrantis within it

    def __init__(self, id: int):
        self.id = id

    @classmethod
    @lru_cache()
    def _lookup(cls) -> Dict[int, "MasaType"]:
        return {item.id: item for item in cls}

    @classmethod
    def from_id(cls, id: int) -> "MasaType":
        return cls._lookup()[id]

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "id": self.id,
        }
