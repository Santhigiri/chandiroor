from typing import List
from fastapi import APIRouter, Depends, Request, Response

from app.api.deps import EtagRepositoryDep, ReferenceRepositoryDep, UnitOfWorkDep, require_role
from app.features.etag.service import build_enum_payload, conditional_json_response, enum_key
from app.schemas.compact_panchangam_data import CompactSanthigiriEvent
from app.schemas.location import LocationInfo
from app.utils.malayalam_masa import MalayalamMasa
from panchangam_astronomy.enums.nakshatra import Nakshatra
from app.utils.roles import Role
from panchangam_astronomy.enums.thithi import Thithi

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
