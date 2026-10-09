from datetime import UTC, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, delete, select

from app.models import (
    Booking,
    BookingCreate,
    BookingSlot,
    BookingStatus,
    User,
    UserRole,
    Venue,
    get_datetime_utc,
)

SLOT_MINUTES = 30
MAX_BOOKING_HOURS = 4

ACTIVE_STATUSES = (BookingStatus.pending, BookingStatus.approved)


class BookingError(Exception):
    """Base exception for booking operations."""


class BookingValidationError(BookingError):
    """Raised when a requested booking window is not allowed."""


class BookingConflictError(BookingError):
    """Raised when a booking overlaps an existing active booking."""


def _as_utc(value: datetime) -> datetime:
    """Normalize naive or aware datetimes to timezone-aware UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _is_unaligned(value: datetime) -> bool:
    return (
        value.second != 0
        or value.microsecond != 0
        or value.minute % SLOT_MINUTES != 0
    )


def build_slots(start_time: datetime, end_time: datetime) -> list[datetime]:
    """Return the half-open list of 30-minute slot starts in [start, end)."""
    if end_time <= start_time:
        raise BookingValidationError("end_time must be after start_time")
    if _is_unaligned(start_time) or _is_unaligned(end_time):
        raise BookingValidationError("time must align to 30 minutes")
    if end_time - start_time > timedelta(hours=MAX_BOOKING_HOURS):
        raise BookingValidationError(
            f"a booking cannot exceed {MAX_BOOKING_HOURS} hours"
        )

    slots: list[datetime] = []
    current = start_time
    while current < end_time:
        slots.append(current)
        current += timedelta(minutes=SLOT_MINUTES)
    return slots


def validate_booking_window(
    venue: Venue,
    start_time: datetime,
    end_time: datetime,
    now: datetime | None = None,
) -> None:
    """Validate alignment, duration, opening hours and (optionally) the future."""
    if not venue.is_active:
        raise BookingValidationError("venue is not available")

    build_slots(start_time, end_time)

    if start_time.time() < venue.open_time or end_time.time() > venue.close_time:
        raise BookingValidationError("booking is outside venue hours")

    if now is not None and start_time <= _as_utc(now):
        raise BookingValidationError("booking must be in the future")


def _find_user_overlap(
    session: Session, user_id, start_time: datetime, end_time: datetime
) -> Booking | None:
    statement = select(Booking).where(
        Booking.user_id == user_id,
        Booking.status.in_(ACTIVE_STATUSES),
        Booking.start_time < end_time,
        Booking.end_time > start_time,
    )
    return session.exec(statement).first()


def find_overlap(
    session: Session, venue_id, start_time: datetime, end_time: datetime
) -> Booking | None:
    """Return the first active booking occupying any slot in the window."""
    statement = (
        select(Booking)
        .join(BookingSlot, BookingSlot.booking_id == Booking.id)
        .where(
            BookingSlot.venue_id == venue_id,
            BookingSlot.slot_start >= start_time,
            BookingSlot.slot_start < end_time,
        )
    )
    return session.exec(statement).first()


def _load_venue_for_booking(session: Session, venue_id) -> Venue | None:
    bind = session.get_bind()
    if bind is not None and bind.dialect.name != "sqlite":
        statement = select(Venue).where(Venue.id == venue_id).with_for_update()
        return session.exec(statement).first()
    return session.get(Venue, venue_id)


def create_booking(session: Session, user: User, data: BookingCreate) -> Booking:
    """Create a pending booking and reserve its 30-minute slots atomically."""
    start_time = _as_utc(data.start_time)
    end_time = _as_utc(data.end_time)

    venue = _load_venue_for_booking(session, data.venue_id)
    if venue is None:
        raise BookingValidationError("venue not found")

    validate_booking_window(venue, start_time, end_time)

    if _find_user_overlap(session, user.id, start_time, end_time):
        raise BookingConflictError("USER_TIME_CONFLICT")
    if find_overlap(session, data.venue_id, start_time, end_time):
        raise BookingConflictError("VENUE_SLOT_CONFLICT")

    booking = Booking(
        venue_id=data.venue_id,
        user_id=user.id,
        start_time=start_time,
        end_time=end_time,
        purpose=data.purpose,
        status=BookingStatus.pending,
    )
    slots = [
        BookingSlot(
            booking_id=booking.id,
            venue_id=data.venue_id,
            slot_start=slot_start,
        )
        for slot_start in build_slots(start_time, end_time)
    ]

    session.add(booking)
    session.add_all(slots)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise BookingConflictError("VENUE_SLOT_CONFLICT") from error

    session.refresh(booking)
    return booking


# --- State machine -----------------------------------------------------------

ALLOWED_TRANSITIONS: dict[BookingStatus, set[BookingStatus]] = {
    BookingStatus.pending: {
        BookingStatus.approved,
        BookingStatus.rejected,
        BookingStatus.cancelled,
    },
    BookingStatus.approved: {BookingStatus.cancelled},
}

ACTION_TARGETS: dict[str, BookingStatus] = {
    "approve": BookingStatus.approved,
    "reject": BookingStatus.rejected,
    "cancel": BookingStatus.cancelled,
}


class BookingStateError(BookingError):
    """Raised when a booking status transition is not allowed."""


class BookingPermissionError(BookingError):
    """Raised when an actor is not allowed to perform an action."""


def is_admin(user: User) -> bool:
    return bool(user.is_superuser) or user.role == UserRole.admin


def get_booking(session: Session, booking_id) -> Booking | None:
    return session.get(Booking, booking_id)


def list_bookings(
    session: Session,
    user: User,
    *,
    skip: int = 0,
    limit: int = 100,
    status: BookingStatus | None = None,
) -> tuple[list[Booking], int]:
    filters = []
    if not is_admin(user):
        filters.append(Booking.user_id == user.id)
    if status is not None:
        filters.append(Booking.status == status)

    count_statement = select(func.count()).select_from(Booking)
    list_statement = select(Booking)
    for condition in filters:
        count_statement = count_statement.where(condition)
        list_statement = list_statement.where(condition)

    count = session.exec(count_statement).one()
    bookings = session.exec(
        list_statement.order_by(Booking.start_time.desc())
        .offset(skip)
        .limit(limit)
    ).all()
    return list(bookings), count


def transition_booking(
    session: Session, booking: Booking, actor: User, action: str
) -> Booking:
    if action not in ACTION_TARGETS:
        raise BookingStateError("unknown booking action")

    target = ACTION_TARGETS[action]
    if target not in ALLOWED_TRANSITIONS.get(booking.status, set()):
        raise BookingStateError("invalid booking state transition")

    if action in {"approve", "reject"} and not is_admin(actor):
        raise BookingPermissionError("not allowed to decide bookings")

    if action == "cancel" and booking.user_id != actor.id and not is_admin(actor):
        raise BookingPermissionError("not allowed to cancel this booking")

    if target in {BookingStatus.rejected, BookingStatus.cancelled}:
        session.exec(
            delete(BookingSlot).where(BookingSlot.booking_id == booking.id)
        )

    booking.status = target
    booking.decided_by_id = actor.id
    booking.decided_at = get_datetime_utc()
    session.add(booking)
    session.commit()
    session.refresh(booking)
    return booking


