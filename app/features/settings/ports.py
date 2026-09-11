from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Protocol


@dataclass(frozen=True)
class AppSettingGet:
    key: str
    value: dict
    description: Optional[str]
    updated_at: datetime
    updated_by: Optional[str]


class AppSettingRepositoryPort(Protocol):
    def get(self, key: str) -> Optional[AppSettingGet]: ...

    def list_all(self) -> list[AppSettingGet]: ...

    def upsert(
        self,
        key: str,
        value: dict,
        *,
        description: Optional[str] = None,
        updated_by: Optional[str] = None,
    ) -> AppSettingGet: ...
