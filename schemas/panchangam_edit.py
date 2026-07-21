from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PanchangamDayUpdate(BaseModel):
    """Partial-update body for an existing day's persisted Panchangam.

    Every field is optional: only the values supplied are overridden, the rest of
    the day (including thithi/nakshatra transitions, kollavarsham, and any
    Santhigiri events) is left as computed. Thithi/nakshatra are addressed by
    their stable ids (validated against the 30 thithis / 27 nakshatras); the
    service resolves them to the typed enums.
    """

    thithi_id: Optional[int] = Field(default=None, ge=1, le=30)
    nakshatra_id: Optional[int] = Field(default=None, ge=1, le=27)
    nazhika_from_sunrise: Optional[float] = None
    sunrise: Optional[datetime] = None
    sunset: Optional[datetime] = None
