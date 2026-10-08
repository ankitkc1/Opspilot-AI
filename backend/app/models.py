import uuid
from datetime import UTC, date, datetime, time
from decimal import Decimal
from typing import Literal, Self

from pydantic import EmailStr, model_validator
from sqlalchemy import JSON, CheckConstraint, DateTime, Index, SmallInteger, text
from sqlmodel import Field, Relationship, SQLModel


def get_datetime_utc() -> datetime:
    return datetime.now(UTC)


# Shared properties
class UserBase(SQLModel):
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    is_active: bool = True
    is_superuser: bool = False
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on creation
class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)


class UserRegister(SQLModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on update, all are optional
class UserUpdate(SQLModel):
    email: EmailStr | None = Field(default=None, max_length=255)
    is_active: bool | None = None
    is_superuser: bool | None = None
    full_name: str | None = Field(default=None, max_length=255)
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UserUpdateMe(SQLModel):
    full_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)


class UpdatePassword(SQLModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


# Database model, database table inferred from class name
class User(UserBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    hashed_password: str
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


# Properties to return via API, id is always required
class UserPublic(UserBase):
    id: uuid.UUID
    created_at: datetime | None = None


class UsersPublic(SQLModel):
    data: list[UserPublic]
    count: int


# Shared properties
# -------------------------
# OpsPilot Product models
# -------------------------


class ProductBase(SQLModel):
    name: str = Field(
        min_length=1,
        max_length=255,
        index=True,
    )

    category: str = Field(
        min_length=1,
        max_length=100,
        index=True,
    )

    selling_price: Decimal = Field(
        ge=0,
        max_digits=10,
        decimal_places=2,
    )

    unit: str = Field(
        min_length=1,
        max_length=50,
    )

    is_active: bool = True

    track_inventory: bool = False

    reorder_level: Decimal = Field(
        default=Decimal("0.000"),
        ge=0,
        max_digits=12,
        decimal_places=3,
    )


class ProductCreate(ProductBase):
    pass


class ProductUpdate(SQLModel):
    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
    )

    category: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )

    selling_price: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=10,
        decimal_places=2,
    )

    unit: str | None = Field(
        default=None,
        min_length=1,
        max_length=50,
    )

    is_active: bool | None = None

    track_inventory: bool | None = None

    reorder_level: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=12,
        decimal_places=3,
    )


class Product(ProductBase, table=True):
    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
    )

    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class ProductPublic(ProductBase):
    id: uuid.UUID
    created_at: datetime


class ProductsPublic(SQLModel):
    data: list[ProductPublic]
    count: int


# -------------------------
# OpsPilot Sales models
# -------------------------


class SaleItemCreate(SQLModel):
    product_id: uuid.UUID
    quantity: Decimal = Field(
        gt=0,
        max_digits=10,
        decimal_places=3,
    )


class SaleCreate(SQLModel):
    sold_at: datetime = Field(default_factory=get_datetime_utc)
    items: list[SaleItemCreate] = Field(min_length=1)


class SaleBase(SQLModel):
    sold_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
        index=True,
    )
    total_amount: Decimal = Field(
        ge=0,
        max_digits=12,
        decimal_places=2,
    )


class Sale(SaleBase, table=True):
    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    items: list[SaleItem] = Relationship(
        back_populates="sale",
        cascade_delete=True,
    )


class SaleItemBase(SQLModel):
    product_id: uuid.UUID
    quantity: Decimal = Field(
        gt=0,
        max_digits=10,
        decimal_places=3,
    )
    unit_price: Decimal = Field(
        ge=0,
        max_digits=10,
        decimal_places=2,
    )
    line_total: Decimal = Field(
        ge=0,
        max_digits=12,
        decimal_places=2,
    )


class SaleItem(SaleItemBase, table=True):
    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
    )
    sale_id: uuid.UUID = Field(
        foreign_key="sale.id",
        nullable=False,
        ondelete="CASCADE",
        index=True,
    )
    product_id: uuid.UUID = Field(
        foreign_key="product.id",
        nullable=False,
        ondelete="RESTRICT",
        index=True,
    )
    sale: Sale | None = Relationship(back_populates="items")
    product: Product | None = Relationship()


class SaleItemPublic(SaleItemBase):
    id: uuid.UUID
    sale_id: uuid.UUID


class SalePublic(SaleBase):
    id: uuid.UUID
    created_at: datetime
    items: list[SaleItemPublic]


class SalesPublic(SQLModel):
    data: list[SalePublic]
    count: int


# -------------------------
# OpsPilot Inventory models
# -------------------------


class InventoryMovementCreate(SQLModel):
    product_id: uuid.UUID
    movement_type: Literal["opening", "receipt", "adjustment"]
    quantity_delta: Decimal = Field(
        max_digits=12,
        decimal_places=3,
    )
    occurred_at: datetime = Field(default_factory=get_datetime_utc)
    note: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def validate_quantity_delta(self) -> Self:
        if self.quantity_delta == 0:
            raise ValueError("quantity_delta must not be zero")
        if self.movement_type in {"opening", "receipt"} and self.quantity_delta < 0:
            raise ValueError(f"{self.movement_type} quantity_delta must be positive")
        return self


class InventoryMovement(SQLModel, table=True):
    __table_args__ = (
        CheckConstraint(
            "quantity_delta <> 0",
            name="ck_inventorymovement_quantity_nonzero",
        ),
        CheckConstraint(
            "movement_type IN ('opening', 'receipt', 'adjustment', 'sale')",
            name="ck_inventorymovement_type",
        ),
        CheckConstraint(
            "movement_type NOT IN ('opening', 'receipt') OR quantity_delta > 0",
            name="ck_inventorymovement_inbound_positive",
        ),
        CheckConstraint(
            "(movement_type = 'sale' AND sale_id IS NOT NULL) OR "
            "(movement_type <> 'sale' AND sale_id IS NULL)",
            name="ck_inventorymovement_sale_reference",
        ),
        Index(
            "uq_inventorymovement_one_opening_per_product",
            "product_id",
            unique=True,
            postgresql_where=text("movement_type = 'opening'"),
        ),
    )

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
    )
    product_id: uuid.UUID = Field(
        foreign_key="product.id",
        nullable=False,
        ondelete="RESTRICT",
        index=True,
    )
    sale_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="sale.id",
        ondelete="CASCADE",
        index=True,
    )
    movement_type: str = Field(max_length=20, index=True)
    quantity_delta: Decimal = Field(
        max_digits=12,
        decimal_places=3,
    )
    occurred_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
        index=True,
    )
    note: str | None = Field(default=None, max_length=255)
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class InventoryMovementPublic(SQLModel):
    id: uuid.UUID
    product_id: uuid.UUID
    sale_id: uuid.UUID | None
    movement_type: str
    quantity_delta: Decimal
    occurred_at: datetime
    note: str | None
    created_at: datetime


class InventoryMovementsPublic(SQLModel):
    data: list[InventoryMovementPublic]
    count: int


class InventoryBalancePublic(SQLModel):
    product_id: uuid.UUID
    product_name: str
    unit: str
    is_active: bool
    track_inventory: bool
    reorder_level: Decimal
    quantity_on_hand: Decimal
    is_low_stock: bool


class InventoryBalancesPublic(SQLModel):
    data: list[InventoryBalancePublic]
    count: int


# -------------------------
# OpsPilot Dashboard models
# -------------------------


class DashboardTopProductPublic(SQLModel):
    product_id: uuid.UUID
    product_name: str
    quantity_sold: Decimal
    revenue: Decimal


class DashboardSummaryPublic(SQLModel):
    report_date: date
    timezone: str
    revenue: Decimal
    sales_count: int
    units_sold: Decimal
    average_sale_value: Decimal
    top_products: list[DashboardTopProductPublic]
    low_stock_count: int
    low_stock: list[InventoryBalancePublic]


class DashboardTrendDayPublic(SQLModel):
    report_date: date
    revenue: Decimal
    sales_count: int
    units_sold: Decimal
    average_sale_value: Decimal


class DashboardTrendComparisonPublic(SQLModel):
    start_date: date
    end_date: date
    revenue: Decimal
    sales_count: int
    units_sold: Decimal
    revenue_change_percent: Decimal | None
    sales_count_change_percent: Decimal | None
    units_sold_change_percent: Decimal | None


class DashboardTrendsPublic(SQLModel):
    start_date: date
    end_date: date
    timezone: str
    days: int
    revenue: Decimal
    sales_count: int
    units_sold: Decimal
    average_sale_value: Decimal
    previous_period: DashboardTrendComparisonPublic
    daily: list[DashboardTrendDayPublic]


# -------------------------
# Local AI models
# -------------------------


class AIStatusPublic(SQLModel):
    provider: Literal["ollama"] = "ollama"
    status: Literal["ready", "unavailable", "model_missing"]
    model: str
    available_models: list[str]
    message: str


AIGenerationMode = Literal["manual", "automation"]


class AIDailyBriefingContent(SQLModel):
    headline: str = Field(min_length=1, max_length=120)
    summary: str = Field(min_length=1, max_length=600)
    priorities: list[str] = Field(min_length=1, max_length=3)
    risks: list[str] = Field(max_length=3)
    opportunities: list[str] = Field(max_length=3)


class AIDailyBriefing(AIDailyBriefingContent, table=True):
    __table_args__ = (
        CheckConstraint(
            "generation_mode IN ('manual', 'automation')",
            name="ck_aidailybriefing_generation_mode",
        ),
        Index(
            "ix_aidailybriefing_report_date_generated_at",
            "report_date",
            "generated_at",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    priorities: list[str] = Field(min_length=1, max_length=3, sa_type=JSON)
    risks: list[str] = Field(max_length=3, sa_type=JSON)
    opportunities: list[str] = Field(max_length=3, sa_type=JSON)
    report_date: date
    generated_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    model: str = Field(max_length=100)
    generation_mode: str = Field(default="manual", max_length=20)
    source: dict[str, object] = Field(sa_type=JSON)
    generated_by_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="user.id",
        ondelete="SET NULL",
        index=True,
    )


class AIDailyBriefingPublic(AIDailyBriefingContent):
    id: uuid.UUID
    report_date: date
    generated_at: datetime
    model: str
    generation_mode: AIGenerationMode
    source: DashboardSummaryPublic
    generated_by_id: uuid.UUID | None


class AIDailyBriefingsPublic(SQLModel):
    data: list[AIDailyBriefingPublic]
    count: int


class AIWeeklyReviewContent(SQLModel):
    headline: str = Field(min_length=1, max_length=120)
    summary: str = Field(min_length=1, max_length=800)
    wins: list[str] = Field(max_length=3)
    concerns: list[str] = Field(max_length=3)
    priorities: list[str] = Field(min_length=1, max_length=3)


class AIWeeklyReview(AIWeeklyReviewContent, table=True):
    __table_args__ = (
        CheckConstraint(
            "generation_mode IN ('manual', 'automation')",
            name="ck_aiweeklyreview_generation_mode",
        ),
        Index(
            "ix_aiweeklyreview_period_end_generated_at",
            "period_end_date",
            "generated_at",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    wins: list[str] = Field(max_length=3, sa_type=JSON)
    concerns: list[str] = Field(max_length=3, sa_type=JSON)
    priorities: list[str] = Field(min_length=1, max_length=3, sa_type=JSON)
    period_start_date: date
    period_end_date: date
    generated_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    model: str = Field(max_length=100)
    generation_mode: str = Field(default="manual", max_length=20)
    source: dict[str, object] = Field(sa_type=JSON)
    generated_by_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="user.id",
        ondelete="SET NULL",
        index=True,
    )


class AIWeeklyReviewPublic(AIWeeklyReviewContent):
    id: uuid.UUID
    period_start_date: date
    period_end_date: date
    generated_at: datetime
    model: str
    generation_mode: AIGenerationMode
    source: DashboardTrendsPublic
    generated_by_id: uuid.UUID | None


class AIWeeklyReviewsPublic(SQLModel):
    data: list[AIWeeklyReviewPublic]
    count: int


# -------------------------
# AI automation models
# -------------------------


AIAutomationTrigger = Literal["manual", "scheduled"]
AIAutomationRunStatus = Literal["running", "succeeded", "failed"]
AIAutomationType = Literal["daily_briefing", "weekly_review"]


class AIAutomationSetting(SQLModel, table=True):
    __table_args__ = (
        CheckConstraint(
            "weekly_review_weekday BETWEEN 0 AND 6",
            name="ck_aiautomationsetting_weekday",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(
        foreign_key="user.id",
        ondelete="CASCADE",
        unique=True,
        index=True,
    )
    daily_briefing_enabled: bool = False
    daily_briefing_time: time = Field(default=time(hour=8))
    weekly_review_enabled: bool = False
    weekly_review_weekday: int = Field(
        default=0,
        ge=0,
        le=6,
        sa_type=SmallInteger,
    )
    weekly_review_time: time = Field(default=time(hour=9))
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class AIDailyAutomationUpdate(SQLModel):
    enabled: bool | None = None
    run_time: time | None = None


class AIWeeklyAutomationUpdate(SQLModel):
    enabled: bool | None = None
    weekday: int | None = Field(default=None, ge=0, le=6)
    run_time: time | None = None


class AIAutomationRun(SQLModel, table=True):
    __table_args__ = (
        CheckConstraint(
            "trigger IN ('manual', 'scheduled')",
            name="ck_aiautomationrun_trigger",
        ),
        CheckConstraint(
            "status IN ('running', 'succeeded', 'failed')",
            name="ck_aiautomationrun_status",
        ),
        CheckConstraint(
            "automation_type IN ('daily_briefing', 'weekly_review')",
            name="ck_aiautomationrun_type",
        ),
        CheckConstraint(
            "NOT (briefing_id IS NOT NULL AND weekly_review_id IS NOT NULL)",
            name="ck_aiautomationrun_single_result",
        ),
        Index(
            "ix_aiautomationrun_user_started_at",
            "user_id",
            "started_at",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    run_key: str = Field(unique=True, index=True, max_length=255)
    user_id: uuid.UUID = Field(
        foreign_key="user.id",
        ondelete="CASCADE",
        index=True,
    )
    automation_type: str = Field(default="daily_briefing", max_length=30)
    trigger: str = Field(max_length=20)
    status: str = Field(default="running", max_length=20)
    scheduled_for: date
    started_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    completed_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    briefing_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="aidailybriefing.id",
        ondelete="SET NULL",
    )
    weekly_review_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="aiweeklyreview.id",
        ondelete="SET NULL",
    )
    error: str | None = Field(default=None, max_length=1000)


class AIAutomationRunPublic(SQLModel):
    id: uuid.UUID
    automation_type: AIAutomationType
    trigger: AIAutomationTrigger
    status: AIAutomationRunStatus
    scheduled_for: date
    started_at: datetime
    completed_at: datetime | None
    briefing_id: uuid.UUID | None
    weekly_review_id: uuid.UUID | None
    error: str | None


class AIDailyAutomationPublic(SQLModel):
    enabled: bool
    run_time: time
    timezone: str
    next_run_at: datetime | None
    last_run: AIAutomationRunPublic | None


class AIWeeklyAutomationPublic(SQLModel):
    enabled: bool
    weekday: int
    run_time: time
    timezone: str
    next_run_at: datetime | None
    last_run: AIAutomationRunPublic | None


# -------------------------
# AI action center models
# -------------------------


ActionCategory = Literal["priority", "risk", "opportunity"]
ActionPriority = Literal["low", "medium", "high"]
ActionStatus = Literal["open", "in_progress", "completed", "dismissed"]


class ActionItemContent(SQLModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    category: ActionCategory = "priority"
    priority: ActionPriority = "medium"
    due_date: date | None = None


class ActionItemCreate(ActionItemContent):
    source_briefing_id: uuid.UUID | None = None
    source_weekly_review_id: uuid.UUID | None = None
    source_suggestion: str | None = Field(default=None, min_length=1, max_length=255)

    @model_validator(mode="after")
    def validate_source_reference(self) -> Self:
        source_count = sum(
            source_id is not None
            for source_id in (
                self.source_briefing_id,
                self.source_weekly_review_id,
            )
        )
        if source_count > 1:
            raise ValueError("only one AI source may be provided")

        has_source = source_count == 1
        has_suggestion = self.source_suggestion is not None
        if has_source != has_suggestion:
            raise ValueError(
                "an AI source and source_suggestion must be provided together"
            )
        return self


class ActionItemUpdate(SQLModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    category: ActionCategory | None = None
    priority: ActionPriority | None = None
    status: ActionStatus | None = None
    due_date: date | None = None
    outcome_note: str | None = Field(default=None, min_length=1, max_length=1000)

    @model_validator(mode="after")
    def reject_null_required_fields(self) -> Self:
        for field_name in ("title", "category", "priority", "status"):
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null")
        return self


class ActionItem(SQLModel, table=True):
    __table_args__ = (
        CheckConstraint(
            "category IN ('priority', 'risk', 'opportunity')",
            name="ck_actionitem_category",
        ),
        CheckConstraint(
            "priority IN ('low', 'medium', 'high')",
            name="ck_actionitem_priority",
        ),
        CheckConstraint(
            "status IN ('open', 'in_progress', 'completed', 'dismissed')",
            name="ck_actionitem_status",
        ),
        CheckConstraint(
            "NOT (source_briefing_id IS NOT NULL "
            "AND source_weekly_review_id IS NOT NULL)",
            name="ck_actionitem_single_ai_source",
        ),
        Index(
            "ix_actionitem_owner_status_created",
            "created_by_id",
            "status",
            "created_at",
        ),
        Index(
            "uq_actionitem_owner_source_suggestion",
            "created_by_id",
            "source_briefing_id",
            "category",
            "source_suggestion",
            unique=True,
            postgresql_where=text(
                "source_briefing_id IS NOT NULL AND source_suggestion IS NOT NULL"
            ),
        ),
        Index(
            "uq_actionitem_owner_weekly_source_suggestion",
            "created_by_id",
            "source_weekly_review_id",
            "category",
            "source_suggestion",
            unique=True,
            postgresql_where=text(
                "source_weekly_review_id IS NOT NULL "
                "AND source_suggestion IS NOT NULL"
            ),
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    category: str = Field(default="priority", max_length=20)
    priority: str = Field(default="medium", max_length=20)
    status: str = Field(default="open", max_length=20)
    due_date: date | None = None
    source_briefing_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="aidailybriefing.id",
        ondelete="SET NULL",
        index=True,
    )
    source_weekly_review_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="aiweeklyreview.id",
        ondelete="SET NULL",
        index=True,
    )
    source_suggestion: str | None = Field(default=None, max_length=255)
    created_by_id: uuid.UUID = Field(
        foreign_key="user.id",
        ondelete="CASCADE",
        index=True,
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    completed_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    outcome_note: str | None = Field(default=None, max_length=1000)


class ActionItemPublic(ActionItemContent):
    category: ActionCategory
    priority: ActionPriority
    id: uuid.UUID
    status: ActionStatus
    source_briefing_id: uuid.UUID | None
    source_weekly_review_id: uuid.UUID | None
    source_suggestion: str | None
    created_by_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
    outcome_note: str | None


class ActionItemsPublic(SQLModel):
    data: list[ActionItemPublic]
    count: int


# Generic message
class Message(SQLModel):
    message: str


# JSON payload containing access token
class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


# Contents of JWT token
class TokenPayload(SQLModel):
    sub: str | None = None


class NewPassword(SQLModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)
