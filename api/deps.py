"""
Shared FastAPI dependency providers for the route layer.

Keeping the wiring here (rather than duplicated in each router) is what lets the
route handlers stay thin: they declare ``Depends(get_service)`` and never touch
``db/`` directly.
"""
from typing import Annotated

from fastapi import Depends
from sqlmodel import Session

from db.database import get_session
from db.repository import PanchangamRepository
from services.panchangam_service import PanchangamService


def get_service(
    session: Annotated[Session, Depends(get_session)],
) -> PanchangamService:
    return PanchangamService(PanchangamRepository(session))
