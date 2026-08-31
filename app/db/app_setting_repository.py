"""
AppSettingRepository — get/list/upsert for the ``app_setting`` table.

Following the convention of ``PanchangamRepository``/
``features.santhigiri_events.repository.SanthigiriEventRepository``, mutating
methods do NOT commit — the caller owns the transaction.
"""
from __future__ import annotations

import datetime
from typing import List, Optional

from sqlmodel import Session, select

from app.db.models.app_setting import AppSetting


class AppSettingRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def get(self, key: str) -> Optional[AppSetting]:
        return self._s.get(AppSetting, key)

    def list_all(self) -> List[AppSetting]:
        return list(self._s.exec(select(AppSetting).order_by(AppSetting.key)).all())

    def upsert(
        self,
        key: str,
        value: dict,
        *,
        description: Optional[str] = None,
        updated_by: Optional[str] = None,
    ) -> AppSetting:
        """Insert or replace *key*'s value. Does NOT commit.

        ``description`` is only applied when provided (an update leaves the
        stored description untouched otherwise); ``updated_at`` is always
        refreshed to now.
        """
        existing = self.get(key)
        row = AppSetting(
            key=key,
            value=value,
            description=description if description is not None else (
                existing.description if existing else None
            ),
            updated_at=datetime.datetime.now(datetime.timezone.utc),
            updated_by=updated_by,
        )
        self._s.merge(row)
        return row
