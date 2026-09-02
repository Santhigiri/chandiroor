from enum import Enum


class Paksha(Enum):
    """The lunar fortnight. ``name`` is the stable slug; localized display text
    lives in the DB ``paksha`` table (seeded by ``db/sql/02_seed.sql``), not on
    this enum."""

    SHUKLA = 1
    KRISHNA = 2

    def __init__(self, id: int):
        self.id = id

    def to_dict(self):
        return {
            "name": self.name,
            "id": self.id,
        }
