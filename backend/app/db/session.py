from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from app.core.config import settings

# Create SQLAlchemy engine with low-memory pool settings suitable for container instances
engine = create_engine(
    settings.sync_database_url,
    pool_pre_ping=True,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_recycle=settings.DB_POOL_RECYCLE,
)

# Session factory for generating database sessions
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for future SQLAlchemy ORM models
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides a transactional database session per request.
    Automatically closes the session upon request completion.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db_connection() -> tuple[bool, str]:
    """
    Executes a simple 'SELECT 1' query to verify database connectivity.
    Returns a tuple of (is_successful, detail_message).
    Secrets or connection strings are never exposed in details.
    """
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True, "PostgreSQL database is reachable and accepting connections."
    except Exception as e:
        return False, "Could not establish connection to the PostgreSQL database."
