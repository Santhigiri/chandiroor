"""
v2 reference-data endpoints — row-per-(parent, language_code) translations.

Additive sibling to ``features/reference/router.py`` (v1): v1's
``/api/v1/panchangam/thithi|nakshatra|masa|chandra-masa`` endpoints keep
reading the fixed ``ml``/``en`` columns unchanged. These v2 endpoints read
the new ``*_translation`` tables instead and return every language as a
``translations: [{language_code, text}]`` list, optionally narrowed to one
language via ``?language_code=``, matching kumily's translation-row pattern
(see kumily's ``features/guru_gita/router.py``).

Declares only its own feature-local prefix — ``main.py`` mounts it under
``/api/v2`` — per CLAUDE.md's "Versioning without a `v1/` directory".

Kumily's convention puts ``?language_code=`` filtering in a feature's
``service.py``. This feature has no ``service.py`` (v1's ``router.py``
already calls ``features/etag/service.py``'s helpers directly via a private
``_reference_response`` function) — the filter here is kept as a private
router-local helper for the same reason, matching this feature's existing
shape rather than introducing a service.py solely to hold one function.
"""
from dataclasses import replace
from typing import List, Optional, Union

from fastapi import APIRouter, Depends, Query, Request, Response

from app.api.deps import EtagRepositoryDep, ReferenceRepositoryDep, UnitOfWorkDep, require_role
from app.core.ports.reference_repository import ReferenceItemGet, ThithiItemGet
from app.features.etag.service import build_enum_payload_v2, conditional_json_response, enum_key_v2, etag_json_response
from app.features.reference.schemas import ReferenceItemSchema, ThithiItemSchema
from app.utils.languages import LanguageCode
from app.utils.roles import Role

router = APIRouter(
    prefix='/panchangam',
    dependencies=[Depends(require_role(Role.ANONYMOUS))],
)


def _filter_item(
    item: Union[ReferenceItemGet, ThithiItemGet], language_code: str
) -> Union[ReferenceItemGet, ThithiItemGet]:
    filtered = replace(
        item,
        translations=[t for t in item.translations if t.language_code == language_code],
    )
    if isinstance(filtered, ThithiItemGet) and filtered.paksha is not None:
        filtered = replace(filtered, paksha=_filter_item(filtered.paksha, language_code))
    return filtered


def _reference_response_v2(
    request: Request,
    reference_repository: ReferenceRepositoryDep,
    etag_repository: EtagRepositoryDep,
    unit_of_work: UnitOfWorkDep,
    name: str,
    language_code: Optional[LanguageCode],
) -> Response:
    if language_code is None:
        return conditional_json_response(
            request,
            etag_repository,
            unit_of_work,
            enum_key_v2(name),
            lambda: build_enum_payload_v2(reference_repository, name),
        )

    items = build_enum_payload_v2(reference_repository, name)
    filtered = [_filter_item(item, language_code.value) for item in items]
    return etag_json_response(request, filtered)


@router.get('/thithi', response_model=List[ThithiItemSchema])
def thithi_reference_v2(
    request: Request,
    reference_repository: ReferenceRepositoryDep,
    etag_repository: EtagRepositoryDep,
    unit_of_work: UnitOfWorkDep,
    language_code: Optional[LanguageCode] = Query(default=None),
) -> Response:
    return _reference_response_v2(
        request, reference_repository, etag_repository, unit_of_work, "thithi", language_code
    )


@router.get('/nakshatra', response_model=List[ReferenceItemSchema])
def nakshatra_reference_v2(
    request: Request,
    reference_repository: ReferenceRepositoryDep,
    etag_repository: EtagRepositoryDep,
    unit_of_work: UnitOfWorkDep,
    language_code: Optional[LanguageCode] = Query(default=None),
) -> Response:
    return _reference_response_v2(
        request, reference_repository, etag_repository, unit_of_work, "nakshatra", language_code
    )


@router.get('/masa', response_model=List[ReferenceItemSchema])
def masa_reference_v2(
    request: Request,
    reference_repository: ReferenceRepositoryDep,
    etag_repository: EtagRepositoryDep,
    unit_of_work: UnitOfWorkDep,
    language_code: Optional[LanguageCode] = Query(default=None),
) -> Response:
    return _reference_response_v2(
        request, reference_repository, etag_repository, unit_of_work, "masa", language_code
    )


@router.get('/chandra-masa', response_model=List[ReferenceItemSchema])
def chandra_masa_reference_v2(
    request: Request,
    reference_repository: ReferenceRepositoryDep,
    etag_repository: EtagRepositoryDep,
    unit_of_work: UnitOfWorkDep,
    language_code: Optional[LanguageCode] = Query(default=None),
) -> Response:
    return _reference_response_v2(
        request, reference_repository, etag_repository, unit_of_work, "chandra_masa", language_code
    )


@router.get('/paksha', response_model=List[ReferenceItemSchema])
def paksha_reference_v2(
    request: Request,
    reference_repository: ReferenceRepositoryDep,
    etag_repository: EtagRepositoryDep,
    unit_of_work: UnitOfWorkDep,
    language_code: Optional[LanguageCode] = Query(default=None),
) -> Response:
    # No v1 equivalent — v1 only ever exposes paksha nested inside /thithi.
    return _reference_response_v2(
        request, reference_repository, etag_repository, unit_of_work, "paksha", language_code
    )
