"""Lightweight Chandra Masa (lunar month) value-object.

Kept free of any Skyfield/ephemeris imports so the API response schema and the DB
repository can import ``ChandraMasaDate`` without loading the heavy astronomy
stack. ``core.chandramasa.chandramasa`` imports this class back and populates it.
"""
from datetime import date

from pydantic import BaseModel


class ChandraMasaDate(BaseModel):
    date: date
    masa: int  # ChandraMasa id (1-12)
    masa_day: int  # day of the lunar (Amanta) month
    masa_type: int  # MasaType id: 1=Nija (regular), 2=Adhika (leap), 3=Kshaya (deficit)
