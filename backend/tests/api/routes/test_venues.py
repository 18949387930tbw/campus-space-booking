import uuid

from fastapi.testclient import TestClient

from app.core.config import settings


def venue_payload() -> dict[str, object]:
    return {
        "name": f"Venue {uuid.uuid4().hex[:8]}",
        "location": "Library Building",
        "capacity": 40,
        "open_time": "08:00:00",
        "close_time": "22:00:00",
        "description": "Quiet study space",
    }


def test_create_venue_as_admin(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    payload = venue_payload()
    response = client.post(
        f"{settings.API_V1_STR}/venues/",
        headers=superuser_token_headers,
        json=payload,
    )

    assert response.status_code == 200
    assert response.json()["name"] == payload["name"]
    assert response.json()["is_active"] is True


def test_create_venue_as_student_is_forbidden(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/venues/",
        headers=normal_user_token_headers,
        json=venue_payload(),
    )

    assert response.status_code == 403


def test_duplicate_venue_name_is_rejected(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    payload = venue_payload()
    first = client.post(
        f"{settings.API_V1_STR}/venues/",
        headers=superuser_token_headers,
        json=payload,
    )
    second = client.post(
        f"{settings.API_V1_STR}/venues/",
        headers=superuser_token_headers,
        json=payload,
    )

    assert first.status_code == 200
    assert second.status_code == 409


def test_admin_can_update_and_delete_venue(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    payload = venue_payload()
    created = client.post(
        f"{settings.API_V1_STR}/venues/",
        headers=superuser_token_headers,
        json=payload,
    ).json()

    updated = client.patch(
        f"{settings.API_V1_STR}/venues/{created['id']}",
        headers=superuser_token_headers,
        json={"capacity": 80, "is_active": False},
    )
    assert updated.status_code == 200
    assert updated.json()["capacity"] == 80
    assert updated.json()["is_active"] is False

    deleted = client.delete(
        f"{settings.API_V1_STR}/venues/{created['id']}",
        headers=superuser_token_headers,
    )
    assert deleted.status_code == 200
    assert deleted.json()["message"] == "Venue deleted successfully"


def test_invalid_venue_hours_are_rejected(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    payload = venue_payload() | {"open_time": "22:00:00", "close_time": "08:00:00"}
    response = client.post(
        f"{settings.API_V1_STR}/venues/",
        headers=superuser_token_headers,
        json=payload,
    )

    assert response.status_code == 422