from datetime import time

from sqlalchemy import func
from sqlmodel import Session, select

from app.models import Venue, VenueCreate, VenueUpdate


class VenueError(Exception):
    """Base exception for venue operations."""


class VenueConflictError(VenueError):
    """Raised when a venue name is already in use."""


class VenueValidationError(VenueError):
    """Raised when venue opening hours are invalid."""


def _validate_hours(open_time: time, close_time: time) -> None:
    if open_time >= close_time:
        raise VenueValidationError("open_time must be before close_time")


def get_venue(session: Session, venue_id) -> Venue | None:
    return session.get(Venue, venue_id)


def list_venues(session: Session, skip: int = 0, limit: int = 100) -> tuple[list[Venue], int]:
    count = session.exec(select(func.count()).select_from(Venue)).one()
    venues = session.exec(
        select(Venue).order_by(Venue.name).offset(skip).limit(limit)
    ).all()
    return list(venues), count


def _name_exists(session: Session, name: str, exclude_id=None) -> bool:
    statement = select(Venue).where(func.lower(Venue.name) == name.lower())
    if exclude_id is not None:
        statement = statement.where(Venue.id != exclude_id)
    return session.exec(statement).first() is not None


def create_venue(session: Session, venue_in: VenueCreate) -> Venue:
    _validate_hours(venue_in.open_time, venue_in.close_time)
    if _name_exists(session, venue_in.name):
        raise VenueConflictError("Venue name already exists")

    venue = Venue.model_validate(venue_in)
    session.add(venue)
    session.commit()
    session.refresh(venue)
    return venue


def update_venue(session: Session, venue: Venue, venue_in: VenueUpdate) -> Venue:
    data = venue_in.model_dump(exclude_unset=True)
    merged = {
        "open_time": data.get("open_time", venue.open_time),
        "close_time": data.get("close_time", venue.close_time),
    }
    _validate_hours(merged["open_time"], merged["close_time"])
    name = data.get("name")
    if name and _name_exists(session, name, exclude_id=venue.id):
        raise VenueConflictError("Venue name already exists")

    venue.sqlmodel_update(data)
    session.add(venue)
    session.commit()
    session.refresh(venue)
    return venue


def delete_venue(session: Session, venue: Venue) -> None:
    session.delete(venue)
    session.commit()