"""
UserRepository — get and create ``User`` rows.

The only place that talks to the database for users, mirroring
``PanchangamRepository``. The caller owns the session lifecycle; ``create``
commits so a freshly created user is immediately usable.
"""
from __future__ import annotations

from typing import Optional

from sqlmodel import Session, select

from db.models.user import User
from utils.roles import Role


class UserRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def get_by_username(self, username: str) -> Optional[User]:
        """Return the user with *username*, or None if there is no such user."""
        stmt = select(User).where(User.username == username)
        return self._s.exec(stmt).first()

    def exists(self, username: str) -> bool:
        """True if a user with *username* already exists."""
        return self.get_by_username(username) is not None

    def create(
        self,
        username: str,
        hashed_password: str,
        role: Role,
    ) -> User:
        """Insert a new user and commit. Caller must ensure the username is free."""
        user = User(
            username=username,
            hashed_password=hashed_password,
            role=role.value,
        )
        self._s.add(user)
        self._s.commit()
        self._s.refresh(user)
        return user
