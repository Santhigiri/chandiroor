from __future__ import annotations
from dataclasses import dataclass
from types import TracebackType
from typing import Optional, Protocol, Type

from sqlmodel import Session



@dataclass(frozen=True)
class SqlUnitOfWork:
    _session: Session

    def __enter__(self) -> SqlUnitOfWork:
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> None:
        if exc_type is not None:
            self._session.rollback()

    def commit(self) -> None:
        self._session.commit()

    def rollback(self) -> None:
        self._session.rollback()
