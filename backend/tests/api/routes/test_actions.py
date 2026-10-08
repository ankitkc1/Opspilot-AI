import uuid
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.models import ActionItem, AIDailyBriefing, AIWeeklyReview


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


def _create_weekly_review(db: Session) -> AIWeeklyReview:
    review = AIWeeklyReview(
        headline="Build consistency next week",
        summary="The selected week had limited recorded sales activity.",
        wins=[],
        concerns=["Sales activity was limited."],
        priorities=["Confirm sales are recorded at the end of each day."],
        period_start_date=date(2099, 3, 1),
        period_end_date=date(2099, 3, 7),
        model="qwen3:4b",
        source={
            "start_date": "2099-03-01",
            "end_date": "2099-03-07",
            "timezone": "Australia/Sydney",
            "days": 7,
            "revenue": "0.00",
            "sales_count": 0,
            "units_sold": "0.000",
            "average_sale_value": "0.00",
            "previous_period": {
                "start_date": "2099-02-22",
                "end_date": "2099-02-28",
                "revenue": "0.00",
                "sales_count": 0,
                "units_sold": "0.000",
                "revenue_change_percent": "0.00",
                "sales_count_change_percent": "0.00",
                "units_sold_change_percent": "0.00",
            },
            "daily": [
                {
                    "report_date": f"2099-03-0{day}",
                    "revenue": "0.00",
                    "sales_count": 0,
                    "units_sold": "0.000",
                    "average_sale_value": "0.00",
                }
                for day in range(1, 8)
            ],
        },
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    return review


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("POST", "/", _action_payload()),
        ("GET", "/", None),
        ("GET", f"/{uuid.UUID(int=1)}", None),
        ("GET", f"/{uuid.UUID(int=1)}/source-briefing", None),
        ("GET", f"/{uuid.UUID(int=1)}/source-weekly-review", None),
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
        json=_action_payload(
            source_briefing_id=str(briefing.id),
            source_suggestion="Review the low-stock list",
        ),
    )

    assert response.status_code == 201
    content = response.json()
    assert content["title"] == "Review the low-stock list"
    assert content["status"] == "open"
    assert content["source_briefing_id"] == str(briefing.id)
    assert content["source_suggestion"] == "Review the low-stock list"
    assert content["created_by_id"]
    assert content["completed_at"] is None
    assert content["outcome_note"] is None

    stored = db.get(ActionItem, uuid.UUID(content["id"]))
    assert stored is not None
    assert stored.created_by_id == uuid.UUID(content["created_by_id"])


def test_create_action_links_saved_weekly_review_and_returns_source(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    review = _create_weekly_review(db)
    priority = "Confirm sales are recorded at the end of each day."
    response = client.post(
        f"{settings.API_V1_STR}/actions/",
        headers=superuser_token_headers,
        json=_action_payload(
            title=priority,
            priority="medium",
            source_weekly_review_id=str(review.id),
            source_suggestion=priority,
        ),
    )

    assert response.status_code == 201
    content = response.json()
    assert content["source_briefing_id"] is None
    assert content["source_weekly_review_id"] == str(review.id)
    assert content["source_suggestion"] == priority

    filtered = client.get(
        f"{settings.API_V1_STR}/actions/",
        headers=superuser_token_headers,
        params={"source_weekly_review_id": str(review.id)},
    )
    assert filtered.status_code == 200
    assert filtered.json()["count"] == 1
    assert filtered.json()["data"][0]["id"] == content["id"]

    source = client.get(
        f"{settings.API_V1_STR}/actions/{content['id']}/source-weekly-review",
        headers=superuser_token_headers,
    )
    assert source.status_code == 200
    assert source.json()["id"] == str(review.id)
    assert source.json()["headline"] == "Build consistency next week"
    assert source.json()["source"]["days"] == 7


def test_create_action_rejects_missing_source_briefing(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/actions/",
        headers=superuser_token_headers,
        json=_action_payload(
            source_briefing_id=str(uuid.uuid4()),
            source_suggestion="Review the low-stock list",
        ),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Source briefing not found"


def test_create_action_rejects_missing_source_weekly_review(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/actions/",
        headers=superuser_token_headers,
        json=_action_payload(
            source_weekly_review_id=str(uuid.uuid4()),
            source_suggestion="Review the low-stock list",
        ),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Source weekly review not found"


@pytest.mark.parametrize(
    "source",
    [
        {"source_briefing_id": str(uuid.uuid4())},
        {"source_weekly_review_id": str(uuid.uuid4())},
        {"source_suggestion": "Review the low-stock list"},
        {
            "source_briefing_id": str(uuid.uuid4()),
            "source_weekly_review_id": str(uuid.uuid4()),
            "source_suggestion": "Review the low-stock list",
        },
    ],
)
def test_create_action_requires_complete_source_reference(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    source: dict[str, str],
) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/actions/",
        headers=superuser_token_headers,
        json=_action_payload(**source),
    )
    assert response.status_code == 422


def test_create_action_rejects_suggestion_outside_briefing_category(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    briefing = _create_briefing(db)
    response = client.post(
        f"{settings.API_V1_STR}/actions/",
        headers=superuser_token_headers,
        json=_action_payload(
            source_briefing_id=str(briefing.id),
            source_suggestion="A product may sell out",
            category="priority",
        ),
    )

    assert response.status_code == 422
    assert "not present" in response.json()["detail"]


def test_create_action_rejects_duplicate_briefing_suggestion(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    briefing = _create_briefing(db)
    payload = _action_payload(
        source_briefing_id=str(briefing.id),
        source_suggestion="Review the low-stock list",
    )

    first = client.post(
        f"{settings.API_V1_STR}/actions/",
        headers=superuser_token_headers,
        json=payload,
    )
    duplicate = client.post(
        f"{settings.API_V1_STR}/actions/",
        headers=superuser_token_headers,
        json=payload,
    )

    assert first.status_code == 201
    assert duplicate.status_code == 409
    assert "already in the Action Center" in duplicate.json()["detail"]


@pytest.mark.parametrize(
    ("category", "suggestion"),
    [
        ("risk", "Confirm sales are recorded at the end of each day."),
        ("priority", "Invent a priority that is not in the review."),
    ],
)
def test_create_action_rejects_invalid_weekly_review_priority(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
    category: str,
    suggestion: str,
) -> None:
    review = _create_weekly_review(db)
    response = client.post(
        f"{settings.API_V1_STR}/actions/",
        headers=superuser_token_headers,
        json=_action_payload(
            title=suggestion,
            category=category,
            source_weekly_review_id=str(review.id),
            source_suggestion=suggestion,
        ),
    )

    assert response.status_code == 422
    assert "not present" in response.json()["detail"]


def test_create_action_rejects_duplicate_weekly_review_priority(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    review = _create_weekly_review(db)
    priority = "Confirm sales are recorded at the end of each day."
    payload = _action_payload(
        title=priority,
        source_weekly_review_id=str(review.id),
        source_suggestion=priority,
    )

    first = client.post(
        f"{settings.API_V1_STR}/actions/",
        headers=superuser_token_headers,
        json=payload,
    )
    duplicate = client.post(
        f"{settings.API_V1_STR}/actions/",
        headers=superuser_token_headers,
        json=payload,
    )

    assert first.status_code == 201
    assert duplicate.status_code == 409
    assert "already in the Action Center" in duplicate.json()["detail"]


def test_create_action_recognizes_legacy_linked_action_as_duplicate(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    briefing = _create_briefing(db)
    created = client.post(
        f"{settings.API_V1_STR}/actions/",
        headers=superuser_token_headers,
        json=_action_payload(),
    )
    legacy_action = db.get(ActionItem, uuid.UUID(created.json()["id"]))
    assert legacy_action is not None
    legacy_action.source_briefing_id = briefing.id
    db.add(legacy_action)
    db.commit()

    duplicate = client.post(
        f"{settings.API_V1_STR}/actions/",
        headers=superuser_token_headers,
        json=_action_payload(
            source_briefing_id=str(briefing.id),
            source_suggestion="Review the low-stock list",
        ),
    )

    assert duplicate.status_code == 409


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
    own_before = client.get(
        f"{settings.API_V1_STR}/actions/",
        headers=superuser_token_headers,
    ).json()
    other_before = client.get(
        f"{settings.API_V1_STR}/actions/",
        headers=normal_user_token_headers,
    ).json()

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
    assert own_list.json()["count"] == own_before["count"] + 1
    assert action_id in {action["id"] for action in own_list.json()["data"]}

    other_list = client.get(
        f"{settings.API_V1_STR}/actions/",
        headers=normal_user_token_headers,
    )
    assert other_list.status_code == 200
    assert other_list.json()["count"] == other_before["count"]
    assert action_id not in {action["id"] for action in other_list.json()["data"]}

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
        json={
            "status": "completed",
            "priority": "high",
            "outcome_note": "  Supplier order was confirmed for Friday.  ",
        },
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"
    assert completed.json()["priority"] == "high"
    assert completed.json()["completed_at"] is not None
    assert completed.json()["outcome_note"] == (
        "Supplier order was confirmed for Friday."
    )

    filtered = client.get(
        f"{settings.API_V1_STR}/actions/",
        headers=superuser_token_headers,
        params={"status": "completed", "category": "priority"},
    )
    assert filtered.status_code == 200
    assert action_id in {action["id"] for action in filtered.json()["data"]}

    reopened = client.patch(
        f"{settings.API_V1_STR}/actions/{action_id}",
        headers=superuser_token_headers,
        json={"status": "in_progress"},
    )
    assert reopened.status_code == 200
    assert reopened.json()["completed_at"] is None
    assert reopened.json()["outcome_note"] == (
        "Supplier order was confirmed for Friday."
    )


@pytest.mark.parametrize(
    "payload",
    [
        {"status": "completed"},
        {"status": "completed", "outcome_note": "   "},
    ],
)
def test_update_action_requires_completion_outcome_note(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    payload: dict[str, object],
) -> None:
    created = client.post(
        f"{settings.API_V1_STR}/actions/",
        headers=superuser_token_headers,
        json=_action_payload(),
    )

    completed = client.patch(
        f"{settings.API_V1_STR}/actions/{created.json()['id']}",
        headers=superuser_token_headers,
        json=payload,
    )

    assert completed.status_code == 422
    assert completed.json()["detail"] == "A completion outcome note is required"


def test_update_action_edits_completed_outcome_note(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    created = client.post(
        f"{settings.API_V1_STR}/actions/",
        headers=superuser_token_headers,
        json=_action_payload(),
    )
    action_id = created.json()["id"]
    completed = client.patch(
        f"{settings.API_V1_STR}/actions/{action_id}",
        headers=superuser_token_headers,
        json={"status": "completed", "outcome_note": "Order submitted."},
    )
    assert completed.status_code == 200

    updated = client.patch(
        f"{settings.API_V1_STR}/actions/{action_id}",
        headers=superuser_token_headers,
        json={"outcome_note": "Order confirmed for Friday delivery."},
    )

    assert updated.status_code == 200
    assert updated.json()["outcome_note"] == (
        "Order confirmed for Friday delivery."
    )


def test_update_action_edits_operational_fields(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    created = client.post(
        f"{settings.API_V1_STR}/actions/",
        headers=superuser_token_headers,
        json=_action_payload(),
    )
    action_id = created.json()["id"]

    updated = client.patch(
        f"{settings.API_V1_STR}/actions/{action_id}",
        headers=superuser_token_headers,
        json={
            "title": "Confirm the supplier order",
            "description": "Call the supplier before 3 pm.",
            "category": "risk",
            "priority": "medium",
            "due_date": "2099-03-03",
        },
    )

    assert updated.status_code == 200
    content = updated.json()
    assert content["title"] == "Confirm the supplier order"
    assert content["description"] == "Call the supplier before 3 pm."
    assert content["category"] == "risk"
    assert content["priority"] == "medium"
    assert content["due_date"] == "2099-03-03"


def test_actions_filter_by_source_briefing_and_return_source(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    briefing = _create_briefing(db)
    linked = client.post(
        f"{settings.API_V1_STR}/actions/",
        headers=superuser_token_headers,
        json=_action_payload(
            source_briefing_id=str(briefing.id),
            source_suggestion="Review the low-stock list",
        ),
    )
    manual = client.post(
        f"{settings.API_V1_STR}/actions/",
        headers=superuser_token_headers,
        json=_action_payload(title="Prepare the weekly roster"),
    )
    assert linked.status_code == 201
    assert manual.status_code == 201

    filtered = client.get(
        f"{settings.API_V1_STR}/actions/",
        headers=superuser_token_headers,
        params={"source_briefing_id": str(briefing.id)},
    )
    assert filtered.status_code == 200
    assert filtered.json()["count"] == 1
    assert filtered.json()["data"][0]["id"] == linked.json()["id"]

    source = client.get(
        f"{settings.API_V1_STR}/actions/{linked.json()['id']}/source-briefing",
        headers=superuser_token_headers,
    )
    assert source.status_code == 200
    assert source.json()["id"] == str(briefing.id)
    assert source.json()["headline"] == "Stock needs attention"


def test_action_source_briefing_is_owner_scoped_and_requires_source(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    normal_user_token_headers: dict[str, str],
    db: Session,
) -> None:
    briefing = _create_briefing(db)
    linked = client.post(
        f"{settings.API_V1_STR}/actions/",
        headers=superuser_token_headers,
        json=_action_payload(
            source_briefing_id=str(briefing.id),
            source_suggestion="Review the low-stock list",
        ),
    )
    manual = client.post(
        f"{settings.API_V1_STR}/actions/",
        headers=superuser_token_headers,
        json=_action_payload(title="Prepare the weekly roster"),
    )

    other_user = client.get(
        f"{settings.API_V1_STR}/actions/{linked.json()['id']}/source-briefing",
        headers=normal_user_token_headers,
    )
    no_source = client.get(
        f"{settings.API_V1_STR}/actions/{manual.json()['id']}/source-briefing",
        headers=superuser_token_headers,
    )

    assert other_user.status_code == 404
    assert no_source.status_code == 404
    assert no_source.json()["detail"] == "Action has no source briefing"


def test_action_source_weekly_review_is_owner_scoped_and_requires_source(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    normal_user_token_headers: dict[str, str],
    db: Session,
) -> None:
    review = _create_weekly_review(db)
    priority = "Confirm sales are recorded at the end of each day."
    linked = client.post(
        f"{settings.API_V1_STR}/actions/",
        headers=superuser_token_headers,
        json=_action_payload(
            title=priority,
            source_weekly_review_id=str(review.id),
            source_suggestion=priority,
        ),
    )
    manual = client.post(
        f"{settings.API_V1_STR}/actions/",
        headers=superuser_token_headers,
        json=_action_payload(title="Prepare the weekly roster"),
    )

    other_user = client.get(
        f"{settings.API_V1_STR}/actions/"
        f"{linked.json()['id']}/source-weekly-review",
        headers=normal_user_token_headers,
    )
    no_source = client.get(
        f"{settings.API_V1_STR}/actions/"
        f"{manual.json()['id']}/source-weekly-review",
        headers=superuser_token_headers,
    )

    assert other_user.status_code == 404
    assert no_source.status_code == 404
    assert no_source.json()["detail"] == "Action has no source weekly review"


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
