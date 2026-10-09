from app.core.db import engine


def test_sqlite_uses_wal() -> None:
    with engine.connect() as connection:
        journal_mode = connection.exec_driver_sql("PRAGMA journal_mode").scalar()
        busy_timeout = connection.exec_driver_sql("PRAGMA busy_timeout").scalar()

    assert journal_mode.lower() == "wal"
    assert busy_timeout >= 5000