"""
UserRepository — get and create ``User`` rows.

The only place that talks to the database for users, mirroring
``PanchangamRepository``. The caller owns the session lifecycle; ``create``
commits so a freshly created user is immediately usable.
"""
from __future__ import annotations

from dataclasses import dataclass

from pydantic import EmailStr
from sqlmodel import Session, select

from app.db.models.user import User
from app.core.astronomy.enums.nakshatra import Nakshatra
from app.utils.roles import Role
from .ports import UserCreate ,UserGet, UserNotFoundException, UserUpdate, UserWithCredentials


@dataclass()
class AuthRepository:
    _s: Session

    def _get_user_row(self, username: str) -> User:
        stmt = select(User).where(User.username == username)
        user = self._s.exec(stmt).first()
        if user is None:
            raise UserNotFoundException()
        return user

    def _save_user_row(self, user: User) -> User:
        self._s.add(user)
        self._s.flush()
        return user


    def _user_row_to_user_get(self, user: User) -> UserGet:
        return UserGet(
            username= user.username,
            full_name=user.full_name,
            role=Role(user.role),
            is_active=user.is_active,
            email=user.email,
            date_of_birth=user.date_of_birth,
            birth_nakshatra= Nakshatra[user.birth_nakshatra] if user.birth_nakshatra is not None else None
        )


    def _user_row_to_user_with_credentials(self, user: User) -> UserWithCredentials:
        return UserWithCredentials(
            username=user.username,
            hashed_password= user.hashed_password if user.hashed_password else "",
            role= Role(user.role),
            is_active= user.is_active,
            email= user.email,
            full_name= user.full_name,
            date_of_birth= user.date_of_birth,
            birth_nakshatra= Nakshatra[user.birth_nakshatra] if user.birth_nakshatra else None
        )

    def get_user_with_credentials(self, username: str) -> UserWithCredentials: 
        user = self._get_user_row(username)
        return self._user_row_to_user_with_credentials(user)

    def get_by_username(self, username: str) -> UserGet:
        """Return the user with *username*, or None if there is no such user."""
        user = self._get_user_row(username)
        return self._user_row_to_user_get(user)

    def exists(self, username: str) -> bool:
        """True if a user with *username* already exists."""
        try:
            self.get_by_username(username)
            return True
        except UserNotFoundException:
            return False

    def create_user(
        self,
        user: UserCreate
    ) -> UserGet:
        """Insert a new user and commit. Caller must ensure the username is free."""
        new_user = User(
            username=user.username,
            hashed_password=user.hashed_password,
            role=user.role.value,
        )
        new_user = self._save_user_row(new_user)

        return self._user_row_to_user_get(new_user)


    def update_user(
        self,
        user_profile: UserUpdate
    ) -> UserGet:
        """
        Apply the given profile fields to *username* and commit.

        Only fields explicitly passed (non-None) overwrite the stored value —
        omitting a field leaves it unchanged. Caller must ensure the user
        exists.
        """
        user = self._get_user_row(user_profile.username)

        if user is None:
            raise ValueError(f"User not found: {user_profile.username!r}")

        if user_profile.full_name is not None:
            user.full_name = user_profile.full_name

        if user_profile.role is not None:
            user.role = user_profile.role.value

        if user_profile.date_of_birth is not None:
            user.date_of_birth = user_profile.date_of_birth

        if user_profile.birth_nakshatra is not None:
            user.birth_nakshatra = user_profile.birth_nakshatra.name

        self._save_user_row(user)
        return self._user_row_to_user_get(user)
