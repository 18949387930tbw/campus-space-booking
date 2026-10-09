import uuid
from datetime import UTC, datetime, time
from enum import Enum

from pydantic import EmailStr
from sqlalchemy import UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel


class UserRole(str, Enum):
    student = "student"
    teacher = "teacher"
    admin = "admin"

def get_datetime_utc() -> datetime:
    return datetime.now(UTC)


# Shared properties
class UserBase(SQLModel):
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    is_active: bool = True
    is_superuser: bool = False
    full_name: str | None = Field(default=None, max_length=255)
    role: UserRole = UserRole.student


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
    role: UserRole | None = None
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
    created_at: datetime | None = Field(default_factory=get_datetime_utc)
    items: list["Item"] = Relationship(back_populates="owner", cascade_delete=True)
    bookings: list["Booking"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={"foreign_keys": "[Booking.user_id]"},
        cascade_delete=True,
    )


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
    created_at: datetime | None = Field(default_factory=get_datetime_utc)
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



class BookingStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    cancelled = "cancelled"


class VenueBase(SQLModel):
    name: str = Field(unique=True, index=True, max_length=100)
    location: str = Field(max_length=255)
    capacity: int = Field(gt=0)
    open_time: time
    close_time: time
    description: str | None = Field(default=None, max_length=500)
    is_active: bool = True


class VenueCreate(VenueBase):
    pass


class VenueUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    location: str | None = Field(default=None, min_length=1, max_length=255)
    capacity: int | None = Field(default=None, gt=0)
    open_time: time | None = None
    close_time: time | None = None
    description: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None


class Venue(VenueBase, table=True):
    __tablename__ = "venue"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=get_datetime_utc)
    bookings: list["Booking"] = Relationship(
        back_populates="venue", cascade_delete=True
    )
    slots: list["BookingSlot"] = Relationship(
        back_populates="venue", cascade_delete=True
    )


class VenuePublic(VenueBase):
    id: uuid.UUID
    created_at: datetime


class VenuesPublic(SQLModel):
    data: list[VenuePublic]
    count: int


class BookingBase(SQLModel):
    venue_id: uuid.UUID = Field(foreign_key="venue.id", index=True)
    start_time: datetime = Field(index=True)
    end_time: datetime = Field(index=True)
    purpose: str = Field(min_length=1, max_length=255)


class BookingCreate(BookingBase):
    pass


class Booking(BookingBase, table=True):
    __tablename__ = "booking"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", index=True)
    status: BookingStatus = Field(default=BookingStatus.pending, index=True)
    decided_by_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", index=True
    )
    decided_at: datetime | None = None
    created_at: datetime = Field(default_factory=get_datetime_utc)
    user: User | None = Relationship(
        back_populates="bookings",
        sa_relationship_kwargs={"foreign_keys": "[Booking.user_id]"},
    )
    venue: Venue | None = Relationship(back_populates="bookings")
    slots: list["BookingSlot"] = Relationship(
        back_populates="booking", cascade_delete=True
    )


class BookingPublic(BookingBase):
    id: uuid.UUID
    user_id: uuid.UUID
    status: BookingStatus
    decided_by_id: uuid.UUID | None = None
    decided_at: datetime | None = None
    created_at: datetime


class BookingsPublic(SQLModel):
    data: list[BookingPublic]
    count: int


class BookingSlot(SQLModel, table=True):
    __tablename__ = "booking_slot"
    __table_args__ = (
        UniqueConstraint(
            "venue_id", "slot_start", name="uq_booking_slot_venue_start"
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    booking_id: uuid.UUID = Field(foreign_key="booking.id", index=True)
    venue_id: uuid.UUID = Field(foreign_key="venue.id", index=True)
    slot_start: datetime = Field(index=True)
    booking: Booking | None = Relationship(back_populates="slots")
    venue: Venue | None = Relationship(back_populates="slots")

# Generic message
class Message(SQLModel):
    message: str


# JSON payload containing access token
class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


# Contents of JWT token
class TokenPayload(SQLModel):
    sub: uuid.UUID | None = None


class NewPassword(SQLModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)
