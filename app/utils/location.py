from enum import Enum
from functools import lru_cache
from typing import Dict, Tuple

from app.core.constants import Coordinates, DEFAULT_TIMEZONE


class Location(Enum):
    """
    A geographic location panchangam data can be computed for.

    Currently only Trivandrum (Santhigiri Ashram, Kerala) is supported, but the
    table is modelled separately so additional locations can be added without
    duplicating coordinates on every ``sunrise_sunset`` row.

    ``code`` is the short, stable key stored as ``location.name`` in the DB
    (the enum member's own ``.name`` is reserved by ``Enum``).
    """

    # (id, code, label, latitude, longitude, timezone)
    TVM = (
        1,
        "tvm",
        "Trivandrum, Kerala, India",
        Coordinates.SG_LATITUDE,
        Coordinates.SG_LONGITUDE,
        DEFAULT_TIMEZONE,
    )

    def __init__(
        self,
        id: int,
        code: str,
        label: str,
        latitude: float,
        longitude: float,
        timezone: str,
    ):
        self.id = id
        self.code = code
        self.label = label
        self.latitude = latitude
        self.longitude = longitude
        self.timezone = timezone

    @classmethod
    @lru_cache()
    def _by_id(cls) -> Dict[int, "Location"]:
        return {item.id: item for item in cls}

    @classmethod
    @lru_cache()
    def _by_coords(cls) -> Dict[Tuple[float, float], "Location"]:
        return {(round(item.latitude, 3), round(item.longitude, 3)): item for item in cls}

    @classmethod
    @lru_cache()
    def _by_code(cls) -> Dict[str, "Location"]:
        return {item.code: item for item in cls}

    @classmethod
    def from_id(cls, id: int) -> "Location":
        return cls._by_id()[id]

    @classmethod
    def from_coords(cls, latitude: float, longitude: float) -> "Location":
        return cls._by_coords()[(round(latitude, 3), round(longitude, 3))]

    @classmethod
    def from_code(cls, code: str) -> "Location":
        """Resolve a location by its short code (``location.name`` in the DB).

        Raises ``KeyError`` for an unknown code — callers at the HTTP boundary
        translate that into a 404.
        """
        return cls._by_code()[code]

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "code": self.code,
            "label": self.label,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "timezone": self.timezone,
        }


# The default location served when a request omits ``?location=`` — the ashram.
DEFAULT_LOCATION_CODE = Location.TVM.code
DEFAULT_LOCATION = Location.TVM
