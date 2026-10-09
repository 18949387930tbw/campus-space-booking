import itertools
import uuid
from datetime import datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.models import UserCreate
from tests.utils.user import user_authentication_headers
from tests.utils.utils import random_email, random_lower_string

_counter = itertools.count()


def _unique_window() -> tuple[datetime, datetime]:
    index = next(_counter)
    start = datetime(2026, 11, 1, 10, 0) + timedelta(days=index)
    return start, start + timedelta(hours=1)


def venue_payload() -> dict[str, Any]:
    return {
        "name": f"Venue {uuid.uuid4().hex[:8]}",
        "location": "Library Building",
        "capacity": 40,
        "open_time": "08:00:00",
        "close_time": "22:00:00",
    }


def booking_payload(
    venue_id: str, start: datetime, end: datetime, purpose: str = "study"
) -> dict[str, Any]:
    return {
        "venue_id": venue_id,
        "start_time": start.isoformat(),
        "end_time": end.isoformat(),
        "purpose": purpose,
    }


@pytest.fixture
def venue(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> dict[str, Any]:
    response = client.post(
        f"{settings.API_V1_STR}/venues/",
        headers=superuser_token_headers,
        json=venue_payload(),
    )
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture
def second_user_headers(
    client: TestClient, db: Session
) -> dict[str, str]:
    email = random_email()
    password = random_lower_string()
    crud.create_user(
        session=db, user_create=UserCreate(email=email, password=password)
    )
    return user_authentication_headers(
        client=client, email=email, password=password
    )


@pytest.fixture
def pending_booking(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    venue: dict[str, Any],
) -> dict[str, Any]:
    start, end = _unique_window()
    response = client.post(
        f"{settings.API_V1_STR}/bookings/",
        headers=normal_user_token_headers,
        json=booking_payload(venue["id"], start, end),
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "pending"
    return data


def test_create_booking_returns_pending_and_lists_it(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    venue: dict[str, Any],
) -> None:
    start, end = _unique_window()
    created = client.post(
        f"{settings.API_V1_STR}/bookings/",
        headers=normal_user_token_headers,
        json=booking_payload(venue["id"], start, end),
    )
    assert created.status_code == 200, created.text
    booking = created.json()
    assert booking["status"] == "pending"

    listing = client.get(
        f"{settings.API_V1_STR}/bookings/",
        headers=normal_user_token_headers,
    )
    assert listing.status_code == 200
    ids = [item["id"] for item in listing.json()["data"]]
    assert booking["id"] in ids


def test_unaligned_booking_window_is_rejected(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    venue: dict[str, Any],
) -> None:
    start = datetime(2026, 12, 1, 10, 7)
    end = datetime(2026, 12, 1, 11, 0)
    response = client.post(
        f"{settings.API_V1_STR}/bookings/",
        headers=normal_user_token_headers,
        json=booking_payload(venue["id"], start, end),
    )
    assert response.status_code == 422


def test_venue_overlap_is_rejected(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    second_user_headers: dict[str, str],
    venue: dict[str, Any],
) -> None:
    start, end = _unique_window()
    first = client.post(
        f"{settings.API_V1_STR}/bookings/",
        headers=normal_user_token_headers,
        json=booking_payload(venue["id"], start, end),
    )
    assert first.status_code == 200

    clash_start = start + timedelta(minutes=30)
    clash_end = end + timedelta(minutes=30)
    second = client.post(
        f"{settings.API_V1_STR}/bookings/",
        headers=second_user_headers,
        json=booking_payload(venue["id"], clash_start, clash_end),
    )
    assert second.status_code == 409


def test_student_cannot_approve(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    pending_booking: dict[str, Any],
) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/bookings/{pending_booking['id']}/approve",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 403


def test_admin_approves_pending_booking(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    pending_booking: dict[str, Any],
) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/bookings/{pending_booking['id']}/approve",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "approved"


def test_cancelled_booking_cannot_be_approved(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    normal_user_token_headers: dict[str, str],
    pending_booking: dict[str, Any],
) -> None:
    cancel = client.post(
        f"{settings.API_V1_STR}/bookings/{pending_booking['id']}/cancel",
        headers=normal_user_token_headers,
    )
    assert cancel.status_code == 200
    assert cancel.json()["status"] == "cancelled"

    response = client.post(
        f"{settings.API_V1_STR}/bookings/{pending_booking['id']}/approve",
        headers=superuser_token_headers,
    )
    assert response.status_code == 409


def test_cancelling_releases_slots_for_rebooking(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    second_user_headers: dict[str, str],
    venue: dict[str, Any],
) -> None:
    start, end = _unique_window()
    created = client.post(
        f"{settings.API_V1_STR}/bookings/",
        headers=normal_user_token_headers,
        json=booking_payload(venue["id"], start, end),
    )
    assert created.status_code == 200
    booking_id = created.json()["id"]

    cancel = client.post(
        f"{settings.API_V1_STR}/bookings/{booking_id}/cancel",
        headers=normal_user_token_headers,
    )
    assert cancel.status_code == 200

    rebooked = client.post(
        f"{settings.API_V1_STR}/bookings/",
        headers=second_user_headers,
        json=booking_payload(venue["id"], start, end),
    )
    assert rebooked.status_code == 200, rebooked.text
