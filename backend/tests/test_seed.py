from sqlmodel import Session, select

from app.core.config import settings
from app.models import User, UserRole, Venue


def test_seed_creates_demo_venues(db: Session) -> None:
    names = {venue.name for venue in db.exec(select(Venue)).all()}

    assert {"Library 101", "Innovation Lab", "Sports Hall"} <= names


def test_superuser_has_admin_role(db: Session) -> None:
    user = db.exec(
        select(User).where(User.email == settings.FIRST_SUPERUSER)
    ).first()

    assert user is not None
    assert user.role == UserRole.admin
