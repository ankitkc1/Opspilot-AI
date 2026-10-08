import uuid
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from app.core.config import settings
from app.models import (
    AIAutomationRun,
    AIAutomationRunPublic,
    AIAutomationSetting,
    AIAutomationTrigger,
    AIDailyAutomationPublic,
    AIDailyAutomationUpdate,
    User,
    get_datetime_utc,
)
from app.services.ai_briefing import (
    AIBriefingResponseError,
    generate_daily_briefing,
    save_daily_briefing,
)
from app.services.dashboard import get_dashboard_summary, resolve_report_date
from app.services.ollama import OllamaClient, OllamaServiceError


def get_or_create_daily_automation(
    session: Session,
    *,
    user_id: uuid.UUID,
) -> AIAutomationSetting:
    automation = session.exec(
        select(AIAutomationSetting).where(AIAutomationSetting.user_id == user_id)
    ).first()
    if automation is not None:
        return automation

    automation = AIAutomationSetting(user_id=user_id)
    session.add(automation)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        existing = session.exec(
            select(AIAutomationSetting).where(
                AIAutomationSetting.user_id == user_id
            )
        ).one()
        return existing
    session.refresh(automation)
    return automation


def update_daily_automation(
    session: Session,
    *,
    user_id: uuid.UUID,
    automation_in: AIDailyAutomationUpdate,
) -> AIAutomationSetting:
    automation = get_or_create_daily_automation(session, user_id=user_id)
    update_data = automation_in.model_dump(exclude_unset=True)
    if update_data.get("enabled") is not None:
        automation.daily_briefing_enabled = update_data["enabled"]
    if update_data.get("run_time") is not None:
        automation.daily_briefing_time = update_data["run_time"].replace(
            second=0,
            microsecond=0,
        )
    automation.updated_at = get_datetime_utc()
    session.add(automation)
    session.commit()
    session.refresh(automation)
    return automation


def to_public_run(run: AIAutomationRun) -> AIAutomationRunPublic:
    return AIAutomationRunPublic.model_validate(run)


def get_latest_automation_run(
    session: Session,
    *,
    user_id: uuid.UUID,
) -> AIAutomationRun | None:
    return session.exec(
        select(AIAutomationRun)
        .where(AIAutomationRun.user_id == user_id)
        .order_by(
            col(AIAutomationRun.started_at).desc(),
            col(AIAutomationRun.id).desc(),
        )
        .limit(1)
    ).first()


def _get_scheduled_run(
    session: Session,
    *,
    user_id: uuid.UUID,
    report_date: date,
) -> AIAutomationRun | None:
    return session.exec(
        select(AIAutomationRun).where(
            AIAutomationRun.user_id == user_id,
            AIAutomationRun.trigger == "scheduled",
            AIAutomationRun.scheduled_for == report_date,
        )
    ).first()


def _next_run_at(
    session: Session,
    *,
    automation: AIAutomationSetting,
    now: datetime,
) -> datetime | None:
    if not automation.daily_briefing_enabled:
        return None

    timezone = ZoneInfo(settings.BUSINESS_TIMEZONE)
    local_now = now.astimezone(timezone)
    today = local_now.date()
    scheduled_today = datetime.combine(
        today,
        automation.daily_briefing_time,
        tzinfo=timezone,
    )
    existing_run = _get_scheduled_run(
        session,
        user_id=automation.user_id,
        report_date=today,
    )
    if local_now < scheduled_today:
        return scheduled_today.astimezone(UTC)
    if existing_run is None:
        return now.astimezone(UTC)
    return datetime.combine(
        today + timedelta(days=1),
        automation.daily_briefing_time,
        tzinfo=timezone,
    ).astimezone(UTC)


def get_daily_automation_public(
    session: Session,
    *,
    user_id: uuid.UUID,
    now: datetime | None = None,
) -> AIDailyAutomationPublic:
    current_time = now or get_datetime_utc()
    automation = get_or_create_daily_automation(session, user_id=user_id)
    last_run = get_latest_automation_run(session, user_id=user_id)
    return AIDailyAutomationPublic(
        enabled=automation.daily_briefing_enabled,
        run_time=automation.daily_briefing_time,
        timezone=settings.BUSINESS_TIMEZONE,
        next_run_at=_next_run_at(
            session,
            automation=automation,
            now=current_time,
        ),
        last_run=to_public_run(last_run) if last_run is not None else None,
    )


def _create_run(
    session: Session,
    *,
    user_id: uuid.UUID,
    report_date: date,
    trigger: AIAutomationTrigger,
) -> tuple[AIAutomationRun, bool]:
    run_key = (
        f"daily:{user_id}:{report_date.isoformat()}"
        if trigger == "scheduled"
        else f"manual:{uuid.uuid4()}"
    )
    run = AIAutomationRun(
        run_key=run_key,
        user_id=user_id,
        trigger=trigger,
        scheduled_for=report_date,
    )
    session.add(run)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        existing = session.exec(
            select(AIAutomationRun).where(AIAutomationRun.run_key == run_key)
        ).one()
        return existing, False
    session.refresh(run)
    return run, True


def _finish_failed_run(
    session: Session,
    *,
    run: AIAutomationRun,
    error: str,
) -> AIAutomationRunPublic:
    run.status = "failed"
    run.error = error
    run.completed_at = get_datetime_utc()
    session.add(run)
    session.commit()
    session.refresh(run)
    return to_public_run(run)


def execute_daily_briefing_automation(
    session: Session,
    *,
    user_id: uuid.UUID,
    ollama: OllamaClient,
    trigger: AIAutomationTrigger,
    report_date: date | None = None,
) -> AIAutomationRunPublic:
    selected_date = resolve_report_date(report_date)
    run, created = _create_run(
        session,
        user_id=user_id,
        report_date=selected_date,
        trigger=trigger,
    )
    if not created:
        return to_public_run(run)

    source = get_dashboard_summary(session, report_date=selected_date)
    try:
        content = generate_daily_briefing(ollama, source)
    except OllamaServiceError:
        return _finish_failed_run(
            session,
            run=run,
            error="Local AI is unavailable. Check Ollama and the configured model.",
        )
    except AIBriefingResponseError:
        return _finish_failed_run(
            session,
            run=run,
            error="Local AI returned a briefing in an invalid format.",
        )

    briefing = save_daily_briefing(
        session,
        content=content,
        source=source,
        model=ollama.model,
        generated_by_id=user_id,
        generation_mode="automation",
    )
    run.status = "succeeded"
    run.briefing_id = briefing.id
    run.completed_at = get_datetime_utc()
    session.add(run)
    session.commit()
    session.refresh(run)
    return to_public_run(run)


def run_due_daily_automations(
    session: Session,
    *,
    ollama: OllamaClient,
    now: datetime | None = None,
) -> list[AIAutomationRunPublic]:
    current_time = now or get_datetime_utc()
    timezone = ZoneInfo(settings.BUSINESS_TIMEZONE)
    local_now = current_time.astimezone(timezone)
    due_runs: list[AIAutomationRunPublic] = []
    automations = session.exec(
        select(AIAutomationSetting).where(
            col(AIAutomationSetting.daily_briefing_enabled).is_(True)
        )
    ).all()

    for automation in automations:
        user = session.get(User, automation.user_id)
        if user is None or not user.is_active:
            continue
        if local_now.time().replace(tzinfo=None) < automation.daily_briefing_time:
            continue
        if (
            _get_scheduled_run(
                session,
                user_id=automation.user_id,
                report_date=local_now.date(),
            )
            is not None
        ):
            continue
        due_runs.append(
            execute_daily_briefing_automation(
                session,
                user_id=automation.user_id,
                ollama=ollama,
                trigger="scheduled",
                report_date=local_now.date(),
            )
        )

    return due_runs
