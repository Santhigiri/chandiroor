"""
UserRepository — get and create ``User`` rows.

The only place that talks to the database for users, mirroring
``PanchangamRepository``. The caller owns the session lifecycle; ``create``
commits so a freshly created user is immediately usable.
"""
from __future__ import annotations

import datetime
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

    def get_by_google_id(self, google_id: str) -> Optional[User]:
        """Return the user with *google_id*, or None if there is no such user."""
        stmt = select(User).where(User.google_id == google_id)
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

    def create_google_user(
        self,
        google_id: str,
        email: str,
        full_name: Optional[str],
    ) -> User:
        """
        Insert a new Google-authenticated user (no local password) and commit.

        Caller must ensure *google_id* is free (via ``get_by_google_id``). The
        verified Google email is used as the username, matching how a human
        would recognize the account (e.g. in the admin user list).
        """
        user = User(
            username=email,
            hashed_password=None,
            role=Role.USER.value,
            email=email,
            full_name=full_name,
            google_id=google_id,
        )
        self._s.add(user)
        self._s.commit()
        self._s.refresh(user)
        return user

    def update_profile(
        self,
        username: str,
        full_name: Optional[str] = None,
        date_of_birth: Optional[datetime.date] = None,
        birth_nakshatra: Optional[str] = None,
    ) -> User:
        """
        Apply the given profile fields to *username* and commit.

        Only fields explicitly passed (non-None) overwrite the stored value —
        omitting a field leaves it unchanged. Caller must ensure the user
        exists.
        """
        user = self.get_by_username(username)

        if user is None:
            raise ValueError(f"User not found: {username!r}")

        if full_name is not None:
            user.full_name = full_name
        if date_of_birth is not None:
            user.date_of_birth = date_of_birth
        if birth_nakshatra is not None:
            user.birth_nakshatra = birth_nakshatra
        self._s.add(user)
        self._s.commit()
        self._s.refresh(user)
        return user
