"""
AppSettingRepository — concrete adapter for ``AppSettingRepositoryPort``,
implementing get/list/upsert for the ``app_setting`` table against SQLModel.

Following the convention of ``PanchangamRepository``/
``features.santhigiri_events.repository.SanthigiriEventRepository``, mutating
methods do NOT commit — the caller owns the transaction.
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import List, Optional

from sqlmodel import Session, select

from app.db.models.app_setting import AppSetting as AppSettingRow
from app.features.settings.ports import AppSettingGet


@dataclass()
class AppSettingRepository:
    _s: Session

    def _row_to_app_setting_get(self, row: AppSettingRow) -> AppSettingGet:
        return AppSettingGet(
            key=row.key,
            value=row.value,
            description=row.description,
            updated_at=row.updated_at,
            updated_by=row.updated_by,
        )

    def get(self, key: str) -> Optional[AppSettingGet]:
        row = self._s.get(AppSettingRow, key)
        if row is None:
            return None
        return self._row_to_app_setting_get(row)

    def list_all(self) -> List[AppSettingGet]:
        rows = self._s.exec(select(AppSettingRow).order_by(AppSettingRow.key)).all()
        return [self._row_to_app_setting_get(row) for row in rows]

    def upsert(
        self,
        key: str,
        value: dict,
        *,
        description: Optional[str] = None,
        updated_by: Optional[str] = None,
    ) -> AppSettingGet:
        """Insert or replace *key*'s value. Does NOT commit.

        ``description`` is only applied when provided (an update leaves the
        stored description untouched otherwise); ``updated_at`` is always
        refreshed to now.
        """
        existing = self._s.get(AppSettingRow, key)
        row = AppSettingRow(
            key=key,
            value=value,
            description=description if description is not None else (
                existing.description if existing else None
            ),
            updated_at=datetime.datetime.now(datetime.timezone.utc),
            updated_by=updated_by,
        )
        self._s.merge(row)
        return self._row_to_app_setting_get(row)
