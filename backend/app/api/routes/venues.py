import uuid
from typing import Any

from fastapi import APIRouter, HTTPException

from app.api.deps import CurrentAdmin, CurrentUser, SessionDep
from app.models import Message, VenueCreate, VenuePublic, VenuesPublic, VenueUpdate
from app.services import venue_service

router = APIRouter(prefix="/venues", tags=["venues"])


def _raise_venue_error(error: venue_service.VenueError) -> None:
    if isinstance(error, venue_service.VenueConflictError):
        raise HTTPException(status_code=409, detail=str(error))
    raise HTTPException(status_code=422, detail=str(error))


@router.get("/", response_model=VenuesPublic)
def read_venues(
    session: SessionDep,
    _current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    venues, count = venue_service.list_venues(session, skip=skip, limit=limit)
    return VenuesPublic(
        data=[VenuePublic.model_validate(venue) for venue in venues], count=count
    )


@router.post("/", response_model=VenuePublic)
def create_venue(
    *, session: SessionDep, _current_admin: CurrentAdmin, venue_in: VenueCreate
) -> Any:
    try:
        return venue_service.create_venue(session, venue_in)
    except venue_service.VenueError as error:
        _raise_venue_error(error)


@router.get("/{venue_id}", response_model=VenuePublic)
def read_venue(
    session: SessionDep, _current_user: CurrentUser, venue_id: uuid.UUID
) -> Any:
    venue = venue_service.get_venue(session, venue_id)
    if not venue:
        raise HTTPException(status_code=404, detail="Venue not found")
    return venue


@router.patch("/{venue_id}", response_model=VenuePublic)
def update_venue(
    *,
    session: SessionDep,
    _current_admin: CurrentAdmin,
    venue_id: uuid.UUID,
    venue_in: VenueUpdate,
) -> Any:
    venue = venue_service.get_venue(session, venue_id)
    if not venue:
        raise HTTPException(status_code=404, detail="Venue not found")
    try:
        return venue_service.update_venue(session, venue, venue_in)
    except venue_service.VenueError as error:
        _raise_venue_error(error)


@router.delete("/{venue_id}")
def delete_venue(
    session: SessionDep, _current_admin: CurrentAdmin, venue_id: uuid.UUID
) -> Message:
    venue = venue_service.get_venue(session, venue_id)
    if not venue:
        raise HTTPException(status_code=404, detail="Venue not found")
    venue_service.delete_venue(session, venue)
    return Message(message="Venue deleted successfully")