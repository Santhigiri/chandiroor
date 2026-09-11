"""CRUD endpoints for Guruvani quotes.

* ``GET    /api/v1/guruvani``          — list every quote, ordered by sort_order  (public)
* ``GET    /api/v1/guruvani/random``   — fetch one quote at random                (public)
* ``GET    /api/v1/guruvani/{id}``     — fetch one quote                          (public)
* ``POST   /api/v1/guruvani``          — create a quote                          (admin)
* ``PUT    /api/v1/guruvani/{id}``     — partial-update a quote                   (admin)
* ``DELETE /api/v1/guruvani/{id}``     — delete a quote                           (admin)

``/random`` is registered ahead of ``/{guruvani_id}`` so FastAPI's path
matching (first-match-wins, in declaration order) doesn't swallow the literal
"random" segment as an int path param.

Authorization mirrors the Santhigiri event definitions: reads are public (the
anonymous principal is allowed, any supplied token is still validated), writes
require the ``admin`` role. Handlers stay thin: parse the body, delegate to
``GuruvaniService``, and translate its domain errors into HTTP status codes.
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.api.deps import GuruvaniServiceDep, require_role
from app.features.guruvani.schemas import GuruvaniCreate, GuruvaniDetail, GuruvaniUpdate
from app.features.guruvani.service import GuruvaniNotFound
from app.utils.roles import Role

router = APIRouter(prefix="/guruvani", tags=["guruvani"])


@router.get(
    "",
    response_model=List[GuruvaniDetail],
    dependencies=[Depends(require_role(Role.ANONYMOUS))],
)
def list_guruvani(service: GuruvaniServiceDep) -> List[GuruvaniDetail]:
    return service.list_all()


@router.get(
    "/random",
    response_model=GuruvaniDetail,
    dependencies=[Depends(require_role(Role.ANONYMOUS))],
)
def get_random_guruvani(service: GuruvaniServiceDep) -> GuruvaniDetail:
    try:
        return service.get_random()
    except GuruvaniNotFound:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="No Guruvani entries exist."
        )


@router.get(
    "/{guruvani_id}",
    response_model=GuruvaniDetail,
    dependencies=[Depends(require_role(Role.ANONYMOUS))],
)
def get_guruvani(guruvani_id: int, service: GuruvaniServiceDep) -> GuruvaniDetail:
    try:
        return service.get(guruvani_id)
    except GuruvaniNotFound:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=f"Guruvani '{guruvani_id}' not found."
        )


@router.post(
    "",
    response_model=GuruvaniDetail,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role(Role.ADMIN))],
)
def create_guruvani(
    payload: GuruvaniCreate, service: GuruvaniServiceDep
) -> GuruvaniDetail:
    return service.create(payload)


@router.put(
    "/{guruvani_id}",
    response_model=GuruvaniDetail,
    dependencies=[Depends(require_role(Role.ADMIN))],
)
def update_guruvani(
    guruvani_id: int, payload: GuruvaniUpdate, service: GuruvaniServiceDep
) -> GuruvaniDetail:
    try:
        return service.update(guruvani_id, payload)
    except GuruvaniNotFound:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=f"Guruvani '{guruvani_id}' not found."
        )


@router.delete(
    "/{guruvani_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_role(Role.ADMIN))],
)
def delete_guruvani(guruvani_id: int, service: GuruvaniServiceDep) -> Response:
    try:
        service.delete(guruvani_id)
    except GuruvaniNotFound:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=f"Guruvani '{guruvani_id}' not found."
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
