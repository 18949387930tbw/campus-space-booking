from datetime import UTC, datetime, time, timedelta
import uuid

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, create_engine

from app.models import Booking, BookingSlot, BookingStatus, User, UserRole, Venue


def test_user_defaults_to_student() -> None:
    user = User(email="student@example.com", hashed_password="x")

    assert user.role == UserRole.student


def test_booking_slot_unique_constraint() -> None:
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    owner_id = uuid.uuid4()
    venue_id = uuid.uuid4()
    first_booking_id = uuid.uuid4()
    second_booking_id = uuid.uuid4()
    slot_start = datetime(2026, 10, 10, 10, 0, tzinfo=UTC)

    with Session(engine) as session:
        session.add(User(email="u@example.com", hashed_password="x", id=owner_id))
        session.add(
            Venue(
                id=venue_id,
                name="A101",
                location="A",
                capacity=30,
                open_time=time(8, 0),
                close_time=time(22, 0),
            )
        )
        session.add_all(
            [
                Booking(
                    id=first_booking_id,
                    venue_id=venue_id,
                    user_id=owner_id,
                    start_time=slot_start,
                    end_time=slot_start + timedelta(hours=1),
                    purpose="study",
                    status=BookingStatus.pending,
                ),
                Booking(
                    id=second_booking_id,
                    venue_id=venue_id,
                    user_id=owner_id,
                    start_time=slot_start,
                    end_time=slot_start + timedelta(hours=1),
                    purpose="study",
                    status=BookingStatus.pending,
                ),
            ]
        )
        session.add(
            BookingSlot(
                booking_id=first_booking_id,
                venue_id=venue_id,
                slot_start=slot_start,
            )
        )
        session.commit()

        session.add(
            BookingSlot(
                booking_id=second_booking_id,
                venue_id=venue_id,
                slot_start=slot_start,
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()