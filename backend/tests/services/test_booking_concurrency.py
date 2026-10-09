import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, time, timedelta
from threading import Barrier

import pytest
from sqlmodel import Session

from app.core.db import engine as db_engine
from app.models import BookingCreate, User, Venue
from app.services.booking_service import BookingConflictError, create_booking


@pytest.fixture
def engine():
    return db_engine


def _seed_contest(engine, *, days_ahead: int) -> tuple[uuid.UUID, list[uuid.UUID], datetime, datetime]:
    venue_id = uuid.uuid4()
    user_ids = [uuid.uuid4(), uuid.uuid4()]
    start = datetime(2026, 12, 20, 10, 0) + timedelta(days=days_ahead)
    end = start + timedelta(hours=1)

    with Session(engine) as session:
        session.add(
            Venue(
                id=venue_id,
                name=f"Room {uuid.uuid4().hex[:8]}",
                location="Main Building",
                capacity=10,
                open_time=time(8, 0),
                close_time=time(22, 0),
            )
        )
        for user_id in user_ids:
            session.add(
                User(
                    id=user_id,
                    email=f"racer-{uuid.uuid4().hex}@example.com",
                    hashed_password="x",
                )
            )
        session.commit()

    return venue_id, user_ids, start, end


def _run_race(engine, venue_id, user_ids, start, end) -> list[tuple[str, object]]:
    barrier = Barrier(len(user_ids))

    def attempt(user_id: uuid.UUID) -> tuple[str, object]:
        with Session(engine) as session:
            user = session.get(User, user_id)
            barrier.wait()
            try:
                booking = create_booking(
                    session,
                    user,
                    BookingCreate(
                        venue_id=venue_id,
                        start_time=start,
                        end_time=end,
                        purpose="study",
                    ),
                )
                return ("ok", booking.id)
            except BookingConflictError:
                return ("conflict", None)
            except Exception as error:  # noqa: BLE001 - surfaced in assertion
                return ("error", f"{type(error).__name__}: {error}")

    with ThreadPoolExecutor(max_workers=len(user_ids)) as pool:
        futures = [pool.submit(attempt, user_id) for user_id in user_ids]
        return [future.result() for future in futures]


def test_two_concurrent_bookings_only_one_succeeds(engine) -> None:
    venue_id, user_ids, start, end = _seed_contest(engine, days_ahead=0)

    results = _run_race(engine, venue_id, user_ids, start, end)

    successes = [result for result in results if result[0] == "ok"]
    errors = [result for result in results if result[0] == "error"]
    assert not errors, results
    assert len(successes) == 1, results
    assert len([r for r in results if r[0] == "conflict"]) == 1, results
