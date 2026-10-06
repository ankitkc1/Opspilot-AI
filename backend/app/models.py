import uuid
from datetime import UTC, datetime
from decimal import Decimal

from pydantic import EmailStr
from sqlalchemy import DateTime
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
    items: list[Item] = Relationship(back_populates="owner", cascade_delete=True)


# Properties to return via API, id is always required
class UserPublic(UserBase):
    id: uuid.UUID
    created_at: datetime | None = None


class UsersPublic(SQLModel):
    data: list[UserPublic]
    count: int


# Shared properties
class ItemBase(SQLModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)


# Properties to receive on item creation
class ItemCreate(ItemBase):
    pass


# Properties to receive on item update
class ItemUpdate(SQLModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)


# Database model, database table inferred from class name
class Item(ItemBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )
    owner: User | None = Relationship(back_populates="items")


# Properties to return via API, id is always required
class ItemPublic(ItemBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    created_at: datetime | None = None


class ItemsPublic(SQLModel):
    data: list[ItemPublic]
    count: int


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
