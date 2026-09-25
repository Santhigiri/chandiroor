"""
Canonical payload builders + ETag computation.

This module is the single source of truth shared by the *write* path
(``refresh_etags`` recomputes ETags when data is loaded) and the *read* path (the
API routes serve the body and its ETag, computing a missing one lazily). Because
both sides build the payload here and hash it the same way, the stored ETag can
never disagree with the bytes the endpoint actually returns.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, List, Optional

from fastapi import Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from app.core.ports.panchangam_service import PanchangamServicePort
from app.core.ports.reference_repository import ReferenceRepositoryPort
from app.core.ports.unit_of_work import UnitOfWork
from app.features.etag.ports import EtagRepositoryPort
from app.schemas.compact_panchangam_data import CompactPanchangamData
from app.utils.content_hash import stable_hash
from app.utils.etag import if_none_match_satisfied
from app.utils.location import DEFAULT_LOCATION, Location

# Enum reference datasets exposed by the API, keyed by route name → the
# ReferenceRepository method that reads each one from the database. These are all
# location-independent (the reference/lookup datasets, including the list of
# available locations itself).
_ENUM_READERS = {
    "thithi": "list_thithis",
    "nakshatra": "list_nakshatras",
    "masa": "list_masas",
    "chandra_masa": "list_chandra_masas",
    "events": "list_events",
    "locations": "list_locations",
}
ENUM_NAMES = tuple(_ENUM_READERS)

# v2 counterparts, reading the row-per-(parent, language_code) translation
# tables instead. Kept as a separate map (and separate ETag key namespace, see
# `enum_key_v2`) so warming/serving a v2 dataset never collides with its v1
# sibling of the same name — the two are different payload shapes cached
# independently. `events`/`locations` have no translation table, so no v2 entry.
_ENUM_READERS_V2 = {
    "thithi": "list_thithis_v2",
    "nakshatra": "list_nakshatras_v2",
    "masa": "list_masas_v2",
    "chandra_masa": "list_chandra_masas_v2",
    "paksha": "list_pakshas_v2",
}
ENUM_NAMES_V2 = tuple(_ENUM_READERS_V2)


# ── Keys ──────────────────────────────────────────────────────────────────────

def year_key(year: int, location_code: str) -> str:
    return f"year:{location_code}:{year}"


def enum_key(name: str) -> str:
    return f"enum:{name}"


def enum_key_v2(name: str) -> str:
    return f"enum:v2:{name}"


# ── Payload builders ──────────────────────────────────────────────────────────

def build_year_payload(
    service: PanchangamServicePort, year: int, location: Location = DEFAULT_LOCATION
) -> Dict[str, CompactPanchangamData]:
    """Return the compact ``{date-str: CompactPanchangamData}`` map the /year route serves."""
    data = service.get_by_year(year=year, location=location)
    return {
        str(day): CompactPanchangamData.from_panchangam_data(value)
        for day, value in data.items()
    }


def build_enum_payload(
    reference_repository: ReferenceRepositoryPort, name: str
) -> List[Dict[str, Any]]:
    """Return the reference list for an enum dataset name, read from the DB."""
    return getattr(reference_repository, _ENUM_READERS[name])()


def build_enum_payload_v2(reference_repository: ReferenceRepositoryPort, name: str) -> List[Any]:
    """v2 counterpart of :func:`build_enum_payload`, reading the translation tables."""
    return getattr(reference_repository, _ENUM_READERS_V2[name])()


# ── ETag ──────────────────────────────────────────────────────────────────────

def compute_etag(payload: Any) -> str:
    """Return a strong, quoted ETag for *payload* (a route-response object)."""
    return '"' + stable_hash(jsonable_encoder(payload)) + '"'


def etag_json_response(
    request: Request,
    payload: Any,
    body_transform: Optional[Callable[[Any], Any]] = None,
) -> Response:
    """
    Serve *payload* as an ETag-validated JSON response, computed fresh on every
    call — unlike :func:`conditional_json_response`, which persists the ETag to
    avoid rebuilding an expensive payload (e.g. a full year of Skyfield-backed
    data). Use this instead for payloads cheap enough to rebuild every request,
    e.g. the settings admin endpoints, where there's no benefit to persisting
    (and later invalidating) a stored ETag.

    *body_transform*, if given, is applied to *payload* to build the served
    body only — the ETag is still computed from the untransformed *payload*.
    Used by v2 routers (app/api/envelope.py::envelope) to wrap the body in the
    {success, message, data} envelope without changing what gets hashed, so a
    v1 and v2 caller of the same underlying data always agree on the ETag.
    """
    encoded = jsonable_encoder(payload)
    etag = '"' + stable_hash(encoded) + '"'

    if if_none_match_satisfied(request.headers.get("if-none-match"), etag):
        return Response(status_code=304, headers={"ETag": etag})

    body = encoded if body_transform is None else jsonable_encoder(body_transform(payload))
    return JSONResponse(content=body, headers={"ETag": etag})


def etag_text_response(request: Request, text: str, media_type: str) -> Response:
    """
    Serve *text* (already-built, e.g. an iCalendar document) as an
    ETag-validated plain-text response, hashed fresh on every call.

    Unlike :func:`conditional_json_response`, there is no persisted ETag to
    check before rebuilding the payload — the caller has already built *text*
    by the time this is called. This still saves the client a full re-download
    when nothing changed (a 304 with no body), which is what matters for a
    periodically-polled feed (e.g. a calendar subscription URL), and it can
    never disagree with the body just built since both are derived from the
    same value in the same call.
    """
    etag = '"' + stable_hash(text) + '"'

    if if_none_match_satisfied(request.headers.get("if-none-match"), etag):
        return Response(status_code=304, headers={"ETag": etag})

    return Response(content=text, media_type=media_type, headers={"ETag": etag})


def conditional_text_response(
    request: Request, body: str, etag: str, media_type: str
) -> Response:
    """
    Serve a pre-built ``(body, etag)`` pair as an ETag-validated text response —
    the read-through-cache sibling of :func:`etag_text_response`.

    Use this when the caller already holds a persisted ETag alongside the body
    (e.g. a cached document read from the database), so a matching
    ``If-None-Match`` short-circuits to a ``304`` without re-hashing a body
    that was already cheap to fetch — unlike :func:`etag_text_response`, which
    always hashes *text* fresh because the caller had to rebuild it anyway.
    """
    if if_none_match_satisfied(request.headers.get("if-none-match"), etag):
        return Response(status_code=304, headers={"ETag": etag})

    return Response(content=body, media_type=media_type, headers={"ETag": etag})


def conditional_json_response(
    request: Request,
    etag_repository: EtagRepositoryPort,
    unit_of_work: UnitOfWork,
    key: str,
    payload_builder: Callable[[], Any],
    body_transform: Optional[Callable[[Any], Any]] = None,
) -> Response:
    """
    Serve an ETag-validated JSON response for the dataset stored under *key*.

    Returns ``304 Not Modified`` (no body, no payload build) when the client's
    ``If-None-Match`` matches the stored ETag — the cheap path for repeat polls.
    Otherwise builds the payload via *payload_builder* and returns it with its
    ``ETag`` header, computing and persisting the ETag on the way if it was not
    already stored (e.g. a year outside the pre-seeded range).

    *body_transform*, if given, is applied to the built payload to construct the
    served body only — the ETag is always computed from the untransformed
    payload, so :func:`refresh_etags` (which hashes the same *payload_builder*
    output directly, never transformed) and this function's lazily-computed
    ETag can never disagree. See :func:`etag_json_response` for the same
    convention on the non-persisted path.
    """
    etag = etag_repository.get(key)

    if etag and if_none_match_satisfied(request.headers.get("if-none-match"), etag):
        return Response(status_code=304, headers={"ETag": etag})

    payload = payload_builder()
    encoded = jsonable_encoder(payload)
    if etag is None:
        etag = '"' + stable_hash(encoded) + '"'
        with unit_of_work as uow:
            etag_repository.set(key, etag)
            uow.commit()

    body = encoded if body_transform is None else jsonable_encoder(body_transform(payload))
    return JSONResponse(content=body, headers={"ETag": etag})


def refresh_etags(
    reference_repository: ReferenceRepositoryPort,
    panchangam_service: PanchangamServicePort,
    etag_repository: EtagRepositoryPort,
    unit_of_work: UnitOfWork,
    years: Iterable[int],
    locations: Optional[Iterable[Location]] = None,
) -> None:
    """
    Recompute and store the ETag for each (location, year) pair plus every enum dataset.

    A convenience for pre-warming ETags after a bulk data load (e.g. offline SQL
    seeding) so they stay in lockstep with the data; the read path also fills any
    missing ETag lazily on first request. ``locations`` defaults to every known
    location. Commits once at the end.

    *panchangam_service* and *reference_repository* are both injected by the
    caller rather than constructed here, so this module never imports
    ``features.panchangam.service``, ``features.panchangam.repository``, or
    ``db.reference_repository`` directly (see ``core/ports/panchangam_service.py``
    and ``core/ports/reference_repository.py``).
    """
    years = list(years)
    locs = list(locations) if locations is not None else list(Location)
    with unit_of_work as uow:
        for location in locs:
            for year in years:
                etag_repository.set(
                    year_key(year, location.code),
                    compute_etag(build_year_payload(panchangam_service, year, location)),
                )

        for name in ENUM_NAMES:
            etag_repository.set(
                enum_key(name),
                compute_etag(build_enum_payload(reference_repository, name)),
            )

        for name in ENUM_NAMES_V2:
            etag_repository.set(
                enum_key_v2(name),
                compute_etag(build_enum_payload_v2(reference_repository, name)),
            )

        uow.commit()
