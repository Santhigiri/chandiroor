from enum import Enum


class Paksha(Enum):
    SHUKLA = (1, "ശുക്ലപക്ഷം", "Shukla Paksha")
    KRISHNA = (2, "കൃഷ്ണപക്ഷം", "Krishna Paksha")

    def __init__(self, id: int, ml: str, en: str):
        self.id = id
        self.ml = ml
        self.en = en

    def to_dict(self):
        return {
            "name": self.name,
            "id": self.id,
            "ml": self.ml,
            "en": self.en
        }
