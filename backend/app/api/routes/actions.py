import uuid

from fastapi import APIRouter, HTTPException, Query, Response, status
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

    if (
        action_in.source_briefing_id is not None
        and session.get(AIDailyBriefing, action_in.source_briefing_id) is None
    ):
        raise HTTPException(status_code=404, detail="Source briefing not found")

    action = ActionItem.model_validate(
        action_in,
        update={"created_by_id": current_user.id},
    )
    session.add(action)
    session.commit()
    session.refresh(action)
    return action


@router.get("/", response_model=ActionItemsPublic)
def read_actions(
    session: SessionDep,
    current_user: CurrentUser,
    action_status: ActionStatus | None = Query(default=None, alias="status"),
    category: ActionCategory | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
) -> ActionItemsPublic:
    """List the current user's actions, newest first."""

    filters = [ActionItem.created_by_id == current_user.id]
    if action_status is not None:
        filters.append(ActionItem.status == action_status)
    if category is not None:
        filters.append(ActionItem.category == category)

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
    next_status = update_data.get("status", action.status)

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
