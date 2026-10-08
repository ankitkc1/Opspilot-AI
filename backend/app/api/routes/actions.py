import uuid

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import col, func, select

from app.api.deps import CurrentUser, SessionDep
from app.models import (
    ActionCategory,
    ActionItem,
    ActionItemCreate,
    ActionItemPublic,
    ActionItemsPublic,
    ActionItemUpdate,
    ActionStatus,
    AIDailyBriefing,
    AIDailyBriefingPublic,
    AIWeeklyReview,
    AIWeeklyReviewPublic,
    get_datetime_utc,
)

router = APIRouter(prefix="/actions", tags=["actions"])


def _get_owned_action(
    session: SessionDep,
    current_user: CurrentUser,
    action_id: uuid.UUID,
) -> ActionItem:
    action = session.get(ActionItem, action_id)
    if action is None or action.created_by_id != current_user.id:
        raise HTTPException(status_code=404, detail="Action not found")
    return action


@router.post("/", response_model=ActionItemPublic, status_code=status.HTTP_201_CREATED)
def create_action(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    action_in: ActionItemCreate,
) -> ActionItem:
    """Create a user-approved operational action."""

    source_filter: bool | None = None
    if action_in.source_briefing_id is not None:
        briefing = session.get(AIDailyBriefing, action_in.source_briefing_id)
        if briefing is None:
            raise HTTPException(status_code=404, detail="Source briefing not found")

        suggestions = {
            "priority": briefing.priorities,
            "risk": briefing.risks,
            "opportunity": briefing.opportunities,
        }[action_in.category]
        if action_in.source_suggestion not in suggestions:
            raise HTTPException(
                status_code=422,
                detail="Source suggestion is not present in that briefing category",
            )

        source_filter = (
            ActionItem.source_briefing_id == action_in.source_briefing_id
        )
    elif action_in.source_weekly_review_id is not None:
        weekly_review = session.get(
            AIWeeklyReview,
            action_in.source_weekly_review_id,
        )
        if weekly_review is None:
            raise HTTPException(
                status_code=404,
                detail="Source weekly review not found",
            )

        if (
            action_in.category != "priority"
            or action_in.source_suggestion not in weekly_review.priorities
        ):
            raise HTTPException(
                status_code=422,
                detail=(
                    "Source suggestion is not present in that weekly review's "
                    "priorities"
                ),
            )

        source_filter = (
            ActionItem.source_weekly_review_id
            == action_in.source_weekly_review_id
        )

    if source_filter is not None:
        duplicate_filters = (
            ActionItem.created_by_id == current_user.id,
            source_filter,
            ActionItem.category == action_in.category,
        )
        duplicate = session.exec(
            select(ActionItem).where(
                *duplicate_filters,
                ActionItem.source_suggestion == action_in.source_suggestion,
            )
        ).first()
        if duplicate is None:
            duplicate = session.exec(
                select(ActionItem).where(
                    *duplicate_filters,
                    col(ActionItem.source_suggestion).is_(None),
                    ActionItem.title == action_in.source_suggestion,
                )
            ).first()
        if duplicate is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This AI suggestion is already in the Action Center",
            )

    action = ActionItem.model_validate(
        action_in,
        update={"created_by_id": current_user.id},
    )
    session.add(action)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This AI suggestion is already in the Action Center",
        ) from error
    session.refresh(action)
    return action


@router.get("/", response_model=ActionItemsPublic)
def read_actions(
    session: SessionDep,
    current_user: CurrentUser,
    action_status: ActionStatus | None = Query(default=None, alias="status"),
    category: ActionCategory | None = None,
    source_briefing_id: uuid.UUID | None = None,
    source_weekly_review_id: uuid.UUID | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
) -> ActionItemsPublic:
    """List the current user's actions, newest first."""

    filters = [ActionItem.created_by_id == current_user.id]
    if action_status is not None:
        filters.append(ActionItem.status == action_status)
    if category is not None:
        filters.append(ActionItem.category == category)
    if source_briefing_id is not None:
        filters.append(ActionItem.source_briefing_id == source_briefing_id)
    if source_weekly_review_id is not None:
        filters.append(
            ActionItem.source_weekly_review_id == source_weekly_review_id
        )

    count = session.exec(
        select(func.count()).select_from(ActionItem).where(*filters)
    ).one()
    actions = session.exec(
        select(ActionItem)
        .where(*filters)
        .order_by(col(ActionItem.created_at).desc(), col(ActionItem.id).desc())
        .offset(skip)
        .limit(limit)
    ).all()
    return ActionItemsPublic(
        data=[ActionItemPublic.model_validate(action) for action in actions],
        count=count,
    )


@router.get("/{action_id}", response_model=ActionItemPublic)
def read_action(
    session: SessionDep,
    current_user: CurrentUser,
    action_id: uuid.UUID,
) -> ActionItem:
    """Read one action owned by the current user."""

    return _get_owned_action(session, current_user, action_id)


@router.get(
    "/{action_id}/source-briefing",
    response_model=AIDailyBriefingPublic,
)
def read_action_source_briefing(
    session: SessionDep,
    current_user: CurrentUser,
    action_id: uuid.UUID,
) -> AIDailyBriefing:
    """Read the saved briefing that produced an owned action."""

    action = _get_owned_action(session, current_user, action_id)
    if action.source_briefing_id is None:
        raise HTTPException(status_code=404, detail="Action has no source briefing")

    briefing = session.get(AIDailyBriefing, action.source_briefing_id)
    if briefing is None:
        raise HTTPException(status_code=404, detail="Source briefing not found")
    return briefing


@router.get(
    "/{action_id}/source-weekly-review",
    response_model=AIWeeklyReviewPublic,
)
def read_action_source_weekly_review(
    session: SessionDep,
    current_user: CurrentUser,
    action_id: uuid.UUID,
) -> AIWeeklyReview:
    """Read the saved weekly review that produced an owned action."""

    action = _get_owned_action(session, current_user, action_id)
    if action.source_weekly_review_id is None:
        raise HTTPException(
            status_code=404,
            detail="Action has no source weekly review",
        )

    weekly_review = session.get(AIWeeklyReview, action.source_weekly_review_id)
    if weekly_review is None:
        raise HTTPException(status_code=404, detail="Source weekly review not found")
    return weekly_review


@router.patch("/{action_id}", response_model=ActionItemPublic)
def update_action(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    action_id: uuid.UUID,
    action_in: ActionItemUpdate,
) -> ActionItem:
    """Update an owned action and maintain its completion timestamp."""

    action = _get_owned_action(session, current_user, action_id)
    update_data = action_in.model_dump(exclude_unset=True)
    if "outcome_note" in update_data:
        outcome_note = update_data["outcome_note"]
        normalized_outcome_note = (
            outcome_note.strip() if outcome_note is not None else None
        )
        update_data["outcome_note"] = normalized_outcome_note or None
    next_status = update_data.get("status", action.status)
    next_outcome_note = update_data.get("outcome_note", action.outcome_note)

    if next_status == "completed" and not next_outcome_note:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="A completion outcome note is required",
        )

    if next_status == "completed" and action.status != "completed":
        action.completed_at = get_datetime_utc()
    elif action.status == "completed" and next_status != "completed":
        action.completed_at = None

    action.sqlmodel_update(update_data)
    action.updated_at = get_datetime_utc()
    session.add(action)
    session.commit()
    session.refresh(action)
    return action


@router.delete("/{action_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_action(
    session: SessionDep,
    current_user: CurrentUser,
    action_id: uuid.UUID,
) -> Response:
    """Delete one action owned by the current user."""

    action = _get_owned_action(session, current_user, action_id)
    session.delete(action)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
