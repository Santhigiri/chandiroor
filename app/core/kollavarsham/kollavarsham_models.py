"""Lightweight Kollavarsham value-object.

Kept free of any Skyfield/ephemeris imports so the API response schema and the DB
repository can import ``KollavarshamDate`` without loading the heavy astronomy
stack. ``core.kollavarsham.kollavarsham`` imports this class back and populates it.
"""
from datetime import date

from pydantic import BaseModel


class KollavarshamDate(BaseModel):
    date: date
    kv_day: int
    kv_month: int
    kv_year: int
