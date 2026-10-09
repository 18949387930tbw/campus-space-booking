from datetime import time

from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine, select

from app import crud
from app.core.config import settings
from app.models import User, UserCreate, UserRole, Venue

database_url = str(settings.DATABASE_URL)
connect_args = (
    {"check_same_thread": False, "timeout": 30}
    if database_url.startswith("sqlite")
    else {}
)
engine = create_engine(
    database_url,
    pool_pre_ping=True,
    connect_args=connect_args,
)


if database_url.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def _configure_sqlite(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()


DEMO_VENUES: list[dict] = [
    {
        "name": "Library 101",
        "location": "Library Building, Floor 1",
        "capacity": 40,
        "open_time": time(8, 0),
        "close_time": time(22, 0),
        "description": "Quiet study room with a whiteboard.",
    },
    {
        "name": "Innovation Lab",
        "location": "Engineering Building, Floor 3",
        "capacity": 24,
        "open_time": time(9, 0),
        "close_time": time(21, 0),
        "description": "Project space with power outlets and monitors.",
    },
    {
        "name": "Sports Hall",
        "location": "Sports Center",
        "capacity": 100,
        "open_time": time(7, 0),
        "close_time": time(23, 0),
        "description": "Indoor court for team activities.",
    },
]


def init_db(session: Session) -> None:
    # Alembic is used for PostgreSQL deployments. Calling create_all here also
    # makes the local SQLite setup work without PostgreSQL-specific migrations.
    SQLModel.metadata.create_all(engine)

    user = session.exec(
        select(User).where(User.email == settings.FIRST_SUPERUSER)
    ).first()
    if not user:
        user_in = UserCreate(
            email=settings.FIRST_SUPERUSER,
            password=settings.FIRST_SUPERUSER_PASSWORD,
            is_superuser=True,
            role=UserRole.admin,
        )
        user = crud.create_user(session=session, user_create=user_in)
    elif user.role != UserRole.admin:
        user.role = UserRole.admin
        session.add(user)
        session.commit()

    _seed_demo_venues(session)


def _seed_demo_venues(session: Session) -> None:
    for payload in DEMO_VENUES:
        existing = session.exec(
            select(Venue).where(Venue.name == payload["name"])
        ).first()
        if existing is None:
            session.add(Venue(**payload))
    session.commit()
