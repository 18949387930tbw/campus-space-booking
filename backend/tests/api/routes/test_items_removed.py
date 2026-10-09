from fastapi.testclient import TestClient

from app.core.config import settings


def test_item_route_is_removed(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/items/",
        headers=normal_user_token_headers,
    )

    assert response.status_code == 404
