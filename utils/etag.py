"""
Helpers for HTTP conditional requests (ETag / ``If-None-Match``).

The route computes/loads a strong ETag for a response and uses
``if_none_match_satisfied`` to decide whether to return ``304 Not Modified``
(the client already holds this exact representation) or the full ``200`` body.
"""
from typing import Optional


def if_none_match_satisfied(header_value: Optional[str], etag: str) -> bool:
    """
    True when an ``If-None-Match`` request header matches *etag*.

    Handles the header forms allowed by RFC 9110: ``*`` (matches anything), a
    single tag, or a comma-separated list of tags. Comparison ignores the weak
    validator prefix (``W/``) so a weak client tag still matches our strong one,
    which is the intended behaviour for the ``If-None-Match`` conditional.
    """
    if not header_value:
        return False

    if header_value.strip() == "*":
        return True

    wanted = _normalise(etag)
    return any(_normalise(candidate) == wanted for candidate in header_value.split(","))


def _normalise(tag: str) -> str:
    """Strip surrounding whitespace and the optional weak-validator ``W/`` prefix."""
    tag = tag.strip()
    if tag.startswith("W/"):
        tag = tag[2:]
    return tag
