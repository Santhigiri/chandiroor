import datetime
from typing import Optional

from sqlalchemy import Column
from sqlmodel import JSON, Field, SQLModel

from app.db.models.types import UTCDateTime


class AppSetting(SQLModel, table=True):
    """
    A single admin-editable application setting.

    One row per tunable value (keyed by a stable string such as
    ``"seed_year_range"`` or ``"nakshatra_transition_step_days"`` — see
    ``utils.settings_keys.SettingKey``), holding an arbitrary JSON ``value``
    whose shape is validated against a dedicated Pydantic model in
    ``schemas.app_setting`` before it is ever written here. This table is a
    generic, reusable store — it has no opinion about what any given key
    means; that lives entirely in ``schemas/`` and ``services/settings_service.py``.

    A row absent from this table is not an error: every reader falls back to
    the equivalent hardcoded constant (see ``SettingsService``), so a fresh
    deploy behaves identically to today until the seed migration is applied
    and/or an admin edits a value.
    """

    __tablename__ = "app_setting" # pyright: ignore[reportAssignmentType]

    key:         str               = Field(primary_key=True)
    value:       dict              = Field(sa_column=Column(JSON, nullable=False))
    description: Optional[str]     = None
    updated_at:  datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
        sa_column=Column(UTCDateTime, nullable=False),
    )
    updated_by:  Optional[str]     = None
