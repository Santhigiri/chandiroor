"""
User roles for authorization.

``Role`` is a string enum so it serialises naturally in JWT claims, JSON
responses, and the ``user.role`` DB column. The three roles form an ordered
privilege hierarchy — ``anonymous`` < ``user`` < ``admin`` — used by the
``require_role`` dependency to gate endpoints at a minimum level.
"""
from __future__ import annotations

from enum import Enum


class Role(str, Enum):
    ANONYMOUS = "anonymous"
    USER = "user"
    ADMIN = "admin"

    @property
    def level(self) -> int:
        """Numeric privilege level for hierarchy comparisons (higher = more)."""
        return _ORDER[self]

    def satisfies(self, minimum: "Role") -> bool:
        """True if this role is at least as privileged as *minimum*."""
        return self.level >= minimum.level


_ORDER: dict[Role, int] = {
    Role.ANONYMOUS: 0,
    Role.USER: 1,
    Role.ADMIN: 2,
}
