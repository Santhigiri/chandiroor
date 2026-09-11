from enum import Enum
from functools import lru_cache
from typing import Dict


class ChandraMasa(Enum):
    """A lunar (Amanta) month. ``name`` is the stable slug used everywhere
    internally; localized display text lives in the DB ``chandra_masa`` table
    (seeded by ``db/sql/02_seed.sql``), not on this enum."""

    CHAITRA = 1
    VAISHAKHA = 2
    JYESHTHA = 3
    ASHADHA = 4
    SHRAVANA = 5
    BHADRAPADA = 6
    ASHWINA = 7
    KARTIKA = 8
    MARGASHIRSHA = 9
    PAUSHA = 10
    MAGHA = 11
    PHALGUNA = 12

    def __init__(self, id: int):
        self.id = id

    @classmethod
    @lru_cache()
    def _lookup(cls) -> Dict[int, "ChandraMasa"]:
        return {item.id: item for item in cls}

    @classmethod
    def from_id(cls, id: int) -> "ChandraMasa":
        return cls._lookup()[id]

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "id": self.id,
        }
