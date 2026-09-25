"""
Supported language codes for translatable reference-data display text.

``LanguageCode`` is a string enum so it serialises naturally in JSON
responses and can be used directly as a Pydantic field type. It is the
allow-list ``features/reference/schemas.py`` validates ``language_code``
against at the HTTP boundary — ports, repositories, and DB models keep
``language_code`` as a plain ``str`` (validation happens once, here).

Mirrors kumily's ``app/utils/languages.py`` exactly, since both services'
translation tables store the same two language codes.
"""
from __future__ import annotations

from enum import Enum


class LanguageCode(str, Enum):
    EN = "en"
    ML = "ml"
