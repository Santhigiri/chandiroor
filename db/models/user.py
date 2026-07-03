import datetime
from typing import Optional

from sqlmodel import Field, SQLModel

from utils.roles import Role


class User(SQLModel, table=True):
    """
    An API user with credentials and an authorization role.

    Passwords are never stored in the clear — only the bcrypt hash produced by
    ``core.security.hash_password`` is persisted. ``role`` stores a
    ``utils.roles.Role`` value ('admin' or 'user'; 'anonymous' is never
    persisted, it is the absence of a user). The table is created automatically
    at startup via ``SQLModel.metadata.create_all`` (see ``db.database.init_db``).
    """

    __tablename__ = "user"  # pyright: ignore[reportAssignmentType]

    id:              Optional[int]      = Field(default=None, primary_key=True)
    username:        str                = Field(unique=True, index=True)
    hashed_password: str
    role:            str                = Field(default=Role.USER.value)
    is_active:       bool               = Field(default=True)
    created_at:      datetime.datetime  = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
