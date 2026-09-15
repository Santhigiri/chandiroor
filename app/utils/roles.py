"""
User roles for authorization.

``Role`` is a string enum so it serialises naturally in JSON responses. Member
*names* (not values) must match TVM's role claim exactly — TVM signs its
access tokens with a Kotlin enum whose ``.name`` is one of ``USER``,
``EDITOR``, ``ADMIN``, ``SUPER_ADMIN``, ``ROOT`` — since ``core.security``
resolves an incoming claim via ``Role[claim_value]``. ``ANONYMOUS`` is
Chandiroor's own concept for "no token presented" and is never a claim TVM
issues.

The six roles form an ordered privilege hierarchy used by the
``require_role`` dependency to gate endpoints at a minimum level.
"""
from __future__ import annotations

from enum import Enum


class Role(str, Enum):
    ANONYMOUS = "anonymous"
    USER = "USER"
    EDITOR = "EDITOR"
    ADMIN = "ADMIN"
    SUPER_ADMIN = "SUPER_ADMIN"
    ROOT = "ROOT"

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
    Role.EDITOR: 2,
    Role.ADMIN: 3,
    Role.SUPER_ADMIN: 4,
    Role.ROOT: 5,
}
