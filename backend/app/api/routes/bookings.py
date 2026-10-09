import uuid
from typing import Any

from fastapi import APIRouter, HTTPException

from app.api.deps import CurrentAdmin, CurrentUser, SessionDep
from app.models import (
    BookingCreate,
    BookingPublic,
    BookingsPublic,
    BookingStatus,
    Message,
)
from app.services import booking_service

router = APIRouter(prefix="/bookings", tags=["bookings"])


def _raise_booking_error(error: booking_service.BookingError) -> None:
    if isinstance(error, booking_service.BookingPermissionError):
        raise HTTPException(status_code=403, detail=str(error))
    if isinstance(
        error,
        (
            booking_service.BookingConflictError,
            booking_service.BookingStateError,
        ),
    ):
        raise HTTPException(status_code=409, detail=str(error))
    raise HTTPException(status_code=422, detail=str(error))


def _get_booking_or_404(session: SessionDep, booking_id: uuid.UUID):
    booking = booking_service.get_booking(session, booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    return booking


@router.post("/", response_model=BookingPublic)
def create_booking(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    booking_in: BookingCreate,
) -> Any:
    try:
        return booking_service.create_booking(session, current_user, booking_in)
    except booking_service.BookingError as error:
        _raise_booking_error(error)


@router.get("/", response_model=BookingsPublic)
def read_bookings(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
    status: BookingStatus | None = None,
) -> Any:
    bookings, count = booking_service.list_bookings(
        session, current_user, skip=skip, limit=limit, status=status
    )
    return BookingsPublic(
        data=[BookingPublic.model_validate(booking) for booking in bookings],
        count=count,
    )


@router.get("/{booking_id}", response_model=BookingPublic)
def read_booking(
    session: SessionDep,
    current_user: CurrentUser,
    booking_id: uuid.UUID,
) -> Any:
    booking = _get_booking_or_404(session, booking_id)
    if booking.user_id != current_user.id and not booking_service.is_admin(
        current_user
    ):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return booking


@router.post("/{booking_id}/approve", response_model=BookingPublic)
def approve_booking(
    *,
    session: SessionDep,
    current_admin: CurrentAdmin,
    booking_id: uuid.UUID,
) -> Any:
    booking = _get_booking_or_404(session, booking_id)
    try:
        return booking_service.transition_booking(
            session, booking, current_admin, "approve"
        )
    except booking_service.BookingError as error:
        _raise_booking_error(error)


@router.post("/{booking_id}/reject", response_model=BookingPublic)
def reject_booking(
    *,
    session: SessionDep,
    current_admin: CurrentAdmin,
    booking_id: uuid.UUID,
) -> Any:
    booking = _get_booking_or_404(session, booking_id)
    try:
        return booking_service.transition_booking(
            session, booking, current_admin, "reject"
        )
    except booking_service.BookingError as error:
        _raise_booking_error(error)


@router.post("/{booking_id}/cancel", response_model=BookingPublic)
def cancel_booking(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    booking_id: uuid.UUID,
) -> Any:
    booking = _get_booking_or_404(session, booking_id)
    try:
        return booking_service.transition_booking(
            session, booking, current_user, "cancel"
        )
    except booking_service.BookingError as error:
        _raise_booking_error(error)


@router.delete("/{booking_id}", response_model=Message)
def delete_booking(
    *,
    session: SessionDep,
    current_admin: CurrentAdmin,
    booking_id: uuid.UUID,
) -> Any:
    booking = _get_booking_or_404(session, booking_id)
    session.delete(booking)
    session.commit()
    return Message(message="Booking deleted successfully")
