from typing import List
from fastapi import APIRouter, Depends, Request, Response

from app.api.deps import EtagRepositoryDep, ReferenceRepositoryDep, UnitOfWorkDep, require_role
from app.features.etag.service import build_enum_payload, conditional_json_response, enum_key, etag_json_response
from app.features.reference.schemas import EventConditionFieldInfo
from app.schemas.compact_panchangam_data import CompactSanthigiriEvent
from app.schemas.location import LocationInfo
from app.core.kollavarsham.enums.masa import MalayalamMasa
from app.core.chandramasa.enums.masa import ChandraMasa
from app.core.astronomy.enums.nakshatra import Nakshatra
from app.utils.roles import Role
from app.utils.santhigiri_events import EVENT_CONDITION_FIELDS
from app.core.astronomy.enums.thithi import Thithi

# The enum reference datasets are read from the database (not the Python enums)
# so DB edits — e.g. to Santhigiri event names/descriptions — are reflected.
# Each is served ETag-validated so the frontend can revalidate cheaply and reuse
# its cached copy on a 304. See features.etag.service for the payloads.
#
# Mounted under the `/panchangam` URL prefix (not `/reference`) even though it
# owns its own feature package — these paths predate the feature split and
# existing clients depend on them, so the URL stays put while the code moves.
router = APIRouter(
    prefix='/panchangam',
    dependencies=[Depends(require_role(Role.ANONYMOUS))],
)


def _reference_response(
    request: Request,
    reference_repository: ReferenceRepositoryDep,
    etag_repository: EtagRepositoryDep,
    unit_of_work: UnitOfWorkDep,
    name: str,
) -> Response:
    return conditional_json_response(
        request,
        etag_repository,
        unit_of_work,
        enum_key(name),
        lambda: build_enum_payload(reference_repository, name),
    )


@router.get(
    '/thithi',
    response_model= List[Thithi]
)
def thithi_reference(
    request: Request,
    reference_repository: ReferenceRepositoryDep,
    etag_repository: EtagRepositoryDep,
    unit_of_work: UnitOfWorkDep,
) -> Response:
    return _reference_response(request, reference_repository, etag_repository, unit_of_work, "thithi")


@router.get(
    '/nakshatra',
    response_model= List[Nakshatra]
)
def nakshatra_reference(
    request: Request,
    reference_repository: ReferenceRepositoryDep,
    etag_repository: EtagRepositoryDep,
    unit_of_work: UnitOfWorkDep,
) -> Response:
    return _reference_response(request, reference_repository, etag_repository, unit_of_work, "nakshatra")


@router.get(
    '/masa',
    response_model= List[MalayalamMasa]
)
def masa_reference(
    request: Request,
    reference_repository: ReferenceRepositoryDep,
    etag_repository: EtagRepositoryDep,
    unit_of_work: UnitOfWorkDep,
) -> Response:
    return _reference_response(request, reference_repository, etag_repository, unit_of_work, "masa")


@router.get(
    '/chandra-masa',
    response_model= List[ChandraMasa]
)
def chandra_masa_reference(
    request: Request,
    reference_repository: ReferenceRepositoryDep,
    etag_repository: EtagRepositoryDep,
    unit_of_work: UnitOfWorkDep,
) -> Response:
    return _reference_response(request, reference_repository, etag_repository, unit_of_work, "chandra_masa")


@router.get(
    '/events',
    response_model= List[CompactSanthigiriEvent]
)
def events_reference(
    request: Request,
    reference_repository: ReferenceRepositoryDep,
    etag_repository: EtagRepositoryDep,
    unit_of_work: UnitOfWorkDep,
) -> Response:
    return _reference_response(request, reference_repository, etag_repository, unit_of_work, "events")


@router.get(
    '/event-condition-fields',
    response_model=List[EventConditionFieldInfo],
)
def event_condition_fields_reference(request: Request) -> Response:
    """The set of ``EventCondition`` fields an admin can add as a matching
    criterion when building an event definition — key, label, value kind,
    and (for an enum-typed field) which reference dataset to populate a
    select from. Static, code-defined data (not DB-backed), so this is
    served via `etag_json_response` (computed fresh, cheap to rebuild) rather
    than `conditional_json_response` (which persists the ETag in the DB)."""
    payload = [
        EventConditionFieldInfo(
            key=f.key, label=f.label, kind=f.kind, reference_dataset=f.reference_dataset
        )
        for f in EVENT_CONDITION_FIELDS
    ]
    return etag_json_response(request, payload)


@router.get(
    '/locations',
    response_model= List[LocationInfo]
)
def locations_reference(
    request: Request,
    reference_repository: ReferenceRepositoryDep,
    etag_repository: EtagRepositoryDep,
    unit_of_work: UnitOfWorkDep,
) -> Response:
    # The list of locations a client can request via ?location=<code>.
    return _reference_response(request, reference_repository, etag_repository, unit_of_work, "locations")
