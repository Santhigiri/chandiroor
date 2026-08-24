import datetime
from typing import Optional

from sqlalchemy import Column
from sqlmodel import Field, SQLModel

from db.models.types import UTCDateTime
from app.utils.roles import Role


class User(SQLModel, table=True):
    """
    An API user with credentials and an authorization role.

    Passwords are never stored in the clear — only the bcrypt hash produced by
    ``core.security.hash_password`` is persisted. ``role`` stores a
    ``utils.roles.Role`` value ('admin' or 'user'; 'anonymous' is never
    persisted, it is the absence of a user). The table is created automatically
    at startup via ``SQLModel.metadata.create_all`` (see ``db.database.init_db``).

    ``hashed_password`` is nullable because a user who signed up via Google
    Sign-In (``google_id`` set) has no local password. ``email``, ``full_name``
    come from the Google profile on first login; ``date_of_birth`` and
    ``birth_nakshatra`` (an ``utils.nakshatra.Nakshatra`` member name, e.g.
    ``"CHOTHI"``) are optional, self-service profile fields set via
    ``PATCH /auth/me``.
    """

    __tablename__ = "user"  # pyright: ignore[reportAssignmentType]

    id:               Optional[int]      = Field(default=None, primary_key=True)
    username:         str                = Field(unique=True, index=True)
    hashed_password:  Optional[str]      = Field(default=None)
    role:             str                = Field(default=Role.USER.value)
    is_active:        bool               = Field(default=True)
    created_at:       datetime.datetime  = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
        sa_column=Column(UTCDateTime, nullable=False),
    )
    email:            Optional[str]      = Field(default=None, unique=True, index=True)
    full_name:        Optional[str]      = Field(default=None)
    google_id:        Optional[str]      = Field(default=None, unique=True, index=True)
    date_of_birth:    Optional[datetime.date] = Field(default=None)
    birth_nakshatra:  Optional[str]      = Field(default=None) #TODO: change str to Nakshatra and map fk
