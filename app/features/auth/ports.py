from dataclasses import dataclass
from datetime import date
from typing import Optional, Protocol

from pydantic import EmailStr
from app.core.astronomy.enums.nakshatra import Nakshatra
from app.utils.roles import Role

class UserNotFoundException(Exception):
    pass




@dataclass(frozen=True)
class UserCreate:
    username: str
    hashed_password: str
    role: Role

@dataclass(frozen=True)
class UserGet:
    username: str
    full_name: Optional[str]
    is_active: bool
    role: Role
    email: Optional[EmailStr]
    date_of_birth: Optional[date]
    birth_nakshatra: Optional[Nakshatra]

@dataclass(frozen=True)
class UserUpdate:
    username: str
    full_name: Optional[str]
    is_active: bool
    role: Optional[Role]
    date_of_birth: Optional[date]
    birth_nakshatra: Optional[Nakshatra]

@dataclass(frozen=True)
class UserWithCredentials:
    username: str
    hashed_password: str
    is_active: bool
    role: Role
    email: Optional[EmailStr]
    full_name: Optional[str]
    date_of_birth: Optional[date]
    birth_nakshatra: Optional[Nakshatra]

    def to_user_get(self) -> UserGet:
        return UserGet(
            username=self.username,
            full_name=self.full_name,
            role=self.role,
            is_active=self.is_active,
            email=self.email,
            date_of_birth=self.date_of_birth,
            birth_nakshatra=self.birth_nakshatra
        )

class AuthRepositoryPort(Protocol):
    def get_user_with_credentials(self, username: str) -> UserWithCredentials: ...
    def get_by_username(self, username: str)-> UserGet: ...
    def exists(self, username: str) -> bool: ...
    def create_user(self, user: UserCreate)-> UserGet: ...
    def update_user(self, user_profile: UserUpdate) -> UserGet: ...
