"""
Canonical payload builders + ETag computation.

This module is the single source of truth shared by the *write* path
(``db.migrate`` recomputes ETags when data is loaded) and the *read* path (the
API routes serve the body and its ETag). Because both sides build the payload
here and hash it the same way, the stored ETag can never disagree with the bytes
the endpoint actually returns.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, List

from fastapi import Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlmodel import Session

from db.etag_repository import EtagRepository
from db.reference_repository import ReferenceRepository
from db.repository import PanchangamRepository
from schemas.compact_panchangam_data import CompactPanchangamData
from services.panchangam_service import PanchangamService
from app.content_hash import stable_hash
from app.etag import if_none_match_satisfied

# Enum reference datasets exposed by the API, keyed by route name → the
# ReferenceRepository method that reads each one from the database.
_ENUM_READERS = {
    "thithi": "list_thithis",
    "nakshatra": "list_nakshatras",
    "masa": "list_masas",
    "events": "list_events",
}
ENUM_NAMES = tuple(_ENUM_READERS)


# ── Keys ──────────────────────────────────────────────────────────────────────

def year_key(year: int) -> str:
    return f"year:{year}"


def enum_key(name: str) -> str:
    return f"enum:{name}"


# ── Payload builders ──────────────────────────────────────────────────────────

def build_year_payload(
    service: PanchangamService, year: int
) -> Dict[str, CompactPanchangamData]:
    """Return the compact ``{date-str: CompactPanchangamData}`` map the /year route serves."""
    data = service.get_by_year(year=year)
    return {
        str(day): CompactPanchangamData.from_panchangam_data(value)
        for day, value in data.items()
    }


def build_enum_payload(session: Session, name: str) -> List[Dict[str, Any]]:
    """Return the reference list for an enum dataset name, read from the DB."""
    repo = ReferenceRepository(session)
    return getattr(repo, _ENUM_READERS[name])()


# ── ETag ──────────────────────────────────────────────────────────────────────

def compute_etag(payload: Any) -> str:
    """Return a strong, quoted ETag for *payload* (a route-response object)."""
    return '"' + stable_hash(jsonable_encoder(payload)) + '"'


def conditional_json_response(
    request: Request,
    session: Session,
    key: str,
    payload_builder: Callable[[], Any],
) -> Response:
    """
    Serve an ETag-validated JSON response for the dataset stored under *key*.

    Returns ``304 Not Modified`` (no body, no payload build) when the client's
    ``If-None-Match`` matches the stored ETag — the cheap path for repeat polls.
    Otherwise builds the payload via *payload_builder* and returns it with its
    ``ETag`` header, computing and persisting the ETag on the way if it was not
    already stored (e.g. a year outside the pre-seeded range).
    """
    etag_repo = EtagRepository(session)
    etag = etag_repo.get(key)

    if etag and if_none_match_satisfied(request.headers.get("if-none-match"), etag):
        return Response(status_code=304, headers={"ETag": etag})

    encoded = jsonable_encoder(payload_builder())
    if etag is None:
        etag = '"' + stable_hash(encoded) + '"'
        etag_repo.set(key, etag)
        session.commit()

    return JSONResponse(content=encoded, headers={"ETag": etag})


def refresh_etags(session: Session, years: Iterable[int]) -> None:
    """
    Recompute and store the ETag for each given year plus every enum dataset.

    Called from the data-write path so ETags stay in lockstep with the data.
    Commits once at the end.
    """
    etag_repo = EtagRepository(session)
    service = PanchangamService(PanchangamRepository(session))

    for year in years:
        etag_repo.set(year_key(year), compute_etag(build_year_payload(service, year)))

    for name in ENUM_NAMES:
        etag_repo.set(enum_key(name), compute_etag(build_enum_payload(session, name)))

    session.commit()
