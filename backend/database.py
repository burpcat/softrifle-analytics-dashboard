from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from config import get_settings

settings = get_settings()

# --- SQLite requires check_same_thread=False for FastAPI's threaded request
# handling. This arg is silently ignored by other DB drivers, but we apply it
# conditionally to keep intent explicit if the DB ever changes.
_connect_args = (
    {"check_same_thread": False}
    if settings.DATABASE_URL.startswith("sqlite")
    else {}
)

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=_connect_args,
)

SessionLocal: sessionmaker[Session] = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    # expire_on_commit=False: the data pipeline passes in-memory ORM objects
    # between stages after commits. The default True would expire all attributes
    # on commit, triggering N+1 lazy reloads across the full campaign/creator
    # lists inside health_score.py and alerts.py.
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# FastAPI dependency — yields a DB session, always closes on exit
# ---------------------------------------------------------------------------

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Table creation utility
#
# ⚠️  IMPORTANT: All model modules must be imported BEFORE this function is
# called, otherwise SQLAlchemy's metadata registry will be empty and no tables
# will be created — silently, with no error.
#
# Correct call order (in seed.py and main.py lifespan):
#     import models          # registers all Table definitions on Base.metadata
#     from database import create_tables
#     create_tables()
#
# NOTE: This uses create_all() which is suitable for development / seeding.
# For production, replace with Alembic migrations.
# ---------------------------------------------------------------------------

def create_tables() -> None:
    Base.metadata.create_all(bind=engine)