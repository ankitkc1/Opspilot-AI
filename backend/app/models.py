import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Literal, Self

from pydantic import EmailStr, model_validator
from sqlalchemy import CheckConstraint, DateTime, Index, text
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
            raise ValueError(
                f"{self.movement_type} quantity_delta must be positive"
            )
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


# -------------------------
# Local AI models
# -------------------------


class AIStatusPublic(SQLModel):
    provider: Literal["ollama"] = "ollama"
    status: Literal["ready", "unavailable", "model_missing"]
    model: str
    available_models: list[str]
    message: str


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
