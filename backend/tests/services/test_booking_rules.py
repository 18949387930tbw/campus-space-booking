from datetime import datetime, time, timedelta
import uuid

import pytest
from sqlmodel import Session

from app.models import BookingCreate, User, Venue
from app.services.booking_service import (
    BookingConflictError,
    BookingValidationError,
    build_slots,
    create_booking,
    validate_booking_window,
)


@pytest.fixture
def owner(db: Session) -> User:
    user = User(
        email=f"owner-{uuid.uuid4().hex}@example.com",
        hashed_password="x",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def venue(db: Session) -> Venue:
    venue = Venue(
        name=f"Room {uuid.uuid4().hex[:8]}",
        location="Main Building",
        capacity=20,
        open_time=time(8, 0),
        close_time=time(22, 0),
    )
    db.add(venue)
    db.commit()
    db.refresh(venue)
    return venue


def booking_data(
    venue: Venue, start: datetime, end: datetime, purpose: str = "study"
) -> BookingCreate:
    return BookingCreate(
        venue_id=venue.id,
        start_time=start,
        end_time=end,
        purpose=purpose,
    )


def test_build_slots_uses_half_open_interval() -> None:
    start = datetime(2026, 10, 10, 10, 0)
    end = datetime(2026, 10, 10, 11, 0)

    assert build_slots(start, end) == [start, datetime(2026, 10, 10, 10, 30)]


def test_build_slots_rejects_unaligned_time() -> None:
    with pytest.raises(BookingValidationError):
        build_slots(
            datetime(2026, 10, 10, 10, 7), datetime(2026, 10, 10, 11, 0)
        )


def test_build_slots_rejects_booking_longer_than_four_hours() -> None:
    start = datetime(2026, 10, 10, 10, 0)
    with pytest.raises(BookingValidationError):
        build_slots(start, start + timedelta(hours=4, minutes=30))


def test_validate_booking_window_rejects_outside_venue_hours(venue: Venue) -> None:
    with pytest.raises(BookingValidationError):
        validate_booking_window(
            venue,
            datetime(2026, 10, 10, 7, 30),
            datetime(2026, 10, 10, 8, 30),
        )


def test_touching_intervals_do_not_overlap(
    db: Session, venue: Venue, owner: User
) -> None:
    first = create_booking(
        db,
        owner,
        booking_data(
            venue,
            datetime(2026, 10, 10, 10, 0),
            datetime(2026, 10, 10, 11, 0),
        ),
    )
    second = create_booking(
        db,
        owner,
        booking_data(
            venue,
            datetime(2026, 10, 10, 11, 0),
            datetime(2026, 10, 10, 12, 0),
        ),
    )

    assert first.id != second.id


def test_venue_overlap_is_rejected(
    db: Session, venue: Venue, owner: User
) -> None:
    create_booking(
        db,
        owner,
        booking_data(
            venue,
            datetime(2026, 10, 10, 10, 0),
            datetime(2026, 10, 10, 11, 0),
        ),
    )
    second_owner = User(
        email=f"owner-{uuid.uuid4().hex}@example.com",
        hashed_password="x",
    )
    db.add(second_owner)
    db.commit()

    with pytest.raises(BookingConflictError):
        create_booking(
            db,
            second_owner,
            booking_data(
                venue,
                datetime(2026, 10, 10, 10, 30),
                datetime(2026, 10, 10, 11, 30),
            ),
        )


def test_user_cannot_book_two_venues_at_once(
    db: Session, venue: Venue, owner: User
) -> None:
    second_venue = Venue(
        name=f"Room {uuid.uuid4().hex[:8]}",
        location="Main Building",
        capacity=10,
        open_time=time(8, 0),
        close_time=time(22, 0),
    )
    db.add(second_venue)
    db.commit()
    db.refresh(second_venue)

    create_booking(
        db,
        owner,
        booking_data(
            venue,
            datetime(2026, 10, 10, 10, 0),
            datetime(2026, 10, 10, 11, 0),
        ),
    )

    with pytest.raises(BookingConflictError):
        create_booking(
            db,
            owner,
            booking_data(
                second_venue,
                datetime(2026, 10, 10, 10, 30),
                datetime(2026, 10, 10, 11, 30),
            ),
        )