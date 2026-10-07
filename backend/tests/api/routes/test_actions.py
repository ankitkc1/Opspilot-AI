import uuid
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.models import ActionItem, AIDailyBriefing


def _action_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "title": "Review the low-stock list",
        "description": "Confirm what needs ordering before the next service.",
        "category": "priority",
        "priority": "high",
        "due_date": "2099-03-02",
    }
    payload.update(overrides)
    return payload


def _create_briefing(db: Session) -> AIDailyBriefing:
    briefing = AIDailyBriefing(
        headline="Stock needs attention",
        summary="Review the products that are close to their reorder level.",
        priorities=["Review the low-stock list"],
        risks=["A product may sell out"],
        opportunities=[],
        report_date=date(2099, 3, 1),
        model="qwen3:4b",
        source={
            "report_date": "2099-03-01",
            "timezone": "Australia/Sydney",
            "revenue": "0.00",
            "sales_count": 0,
            "units_sold": "0.000",
            "average_sale_value": "0.00",
            "top_products": [],
            "low_stock_count": 0,
            "low_stock": [],
        },
    )
    db.add(briefing)
    db.commit()
    db.refresh(briefing)
    return briefing


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("POST", "/", _action_payload()),
        ("GET", "/", None),
        ("GET", f"/{uuid.UUID(int=1)}", None),
        ("PATCH", f"/{uuid.UUID(int=1)}", {"status": "completed"}),
        ("DELETE", f"/{uuid.UUID(int=1)}", None),
    ],
)
def test_action_endpoints_require_authentication(
    client: TestClient,
    method: str,
    path: str,
    payload: dict[str, object] | None,
) -> None:
    response = client.request(
        method,
        f"{settings.API_V1_STR}/actions{path}",
        json=payload,
    )
    assert response.status_code == 401


def test_create_action_links_saved_briefing(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    briefing = _create_briefing(db)
    response = client.post(
        f"{settings.API_V1_STR}/actions/",
        headers=superuser_token_headers,
        json=_action_payload(source_briefing_id=str(briefing.id)),
    )

    assert response.status_code == 201
    content = response.json()
    assert content["title"] == "Review the low-stock list"
    assert content["status"] == "open"
    assert content["source_briefing_id"] == str(briefing.id)
    assert content["created_by_id"]
    assert content["completed_at"] is None

    stored = db.get(ActionItem, uuid.UUID(content["id"]))
    assert stored is not None
    assert stored.created_by_id == uuid.UUID(content["created_by_id"])


def test_create_action_rejects_missing_source_briefing(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/actions/",
        headers=superuser_token_headers,
        json=_action_payload(source_briefing_id=str(uuid.uuid4())),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Source briefing not found"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("title", ""),
        ("category", "unknown"),
        ("priority", "urgent"),
    ],
)
def test_create_action_rejects_invalid_values(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    field: str,
    value: str,
) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/actions/",
        headers=superuser_token_headers,
        json=_action_payload(**{field: value}),
    )
    assert response.status_code == 422


def test_actions_are_scoped_to_the_current_user(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    normal_user_token_headers: dict[str, str],
) -> None:
    created = client.post(
        f"{settings.API_V1_STR}/actions/",
        headers=superuser_token_headers,
        json=_action_payload(),
    )
    assert created.status_code == 201
    action_id = created.json()["id"]

    own_list = client.get(
        f"{settings.API_V1_STR}/actions/",
        headers=superuser_token_headers,
    )
    assert own_list.status_code == 200
    assert own_list.json()["count"] == 1

    other_list = client.get(
        f"{settings.API_V1_STR}/actions/",
        headers=normal_user_token_headers,
    )
    assert other_list.status_code == 200
    assert other_list.json() == {"data": [], "count": 0}

    other_read = client.get(
        f"{settings.API_V1_STR}/actions/{action_id}",
        headers=normal_user_token_headers,
    )
    assert other_read.status_code == 404


def test_update_action_tracks_completion_and_filters(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    created = client.post(
        f"{settings.API_V1_STR}/actions/",
        headers=superuser_token_headers,
        json=_action_payload(priority="medium"),
    )
    action_id = created.json()["id"]

    completed = client.patch(
        f"{settings.API_V1_STR}/actions/{action_id}",
        headers=superuser_token_headers,
        json={"status": "completed", "priority": "high"},
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"
    assert completed.json()["priority"] == "high"
    assert completed.json()["completed_at"] is not None

    filtered = client.get(
        f"{settings.API_V1_STR}/actions/",
        headers=superuser_token_headers,
        params={"status": "completed", "category": "priority"},
    )
    assert filtered.status_code == 200
    assert filtered.json()["count"] == 1
    assert filtered.json()["data"][0]["id"] == action_id

    reopened = client.patch(
        f"{settings.API_V1_STR}/actions/{action_id}",
        headers=superuser_token_headers,
        json={"status": "in_progress"},
    )
    assert reopened.status_code == 200
    assert reopened.json()["completed_at"] is None


@pytest.mark.parametrize("field", ["title", "category", "priority", "status"])
def test_update_action_rejects_null_required_fields(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    field: str,
) -> None:
    created = client.post(
        f"{settings.API_V1_STR}/actions/",
        headers=superuser_token_headers,
        json=_action_payload(),
    )
    action_id = created.json()["id"]

    response = client.patch(
        f"{settings.API_V1_STR}/actions/{action_id}",
        headers=superuser_token_headers,
        json={field: None},
    )
    assert response.status_code == 422


def test_delete_action_removes_owned_action(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    created = client.post(
        f"{settings.API_V1_STR}/actions/",
        headers=superuser_token_headers,
        json=_action_payload(),
    )
    action_id = created.json()["id"]

    deleted = client.delete(
        f"{settings.API_V1_STR}/actions/{action_id}",
        headers=superuser_token_headers,
    )
    assert deleted.status_code == 204

    missing = client.get(
        f"{settings.API_V1_STR}/actions/{action_id}",
        headers=superuser_token_headers,
    )
    assert missing.status_code == 404
