"""Database session management for the dental backend system."""

from contextlib import contextmanager
from typing import Generator

from dental_backend_common.config import get_settings
from dental_backend_common.database import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# Get database settings
settings = get_settings()

# Create database engine
engine = create_engine(
    settings.database.url,
    pool_size=settings.database.pool_size,
    max_overflow=settings.database.max_overflow,
    echo=settings.database.echo,
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Dependency to get database session for FastAPI."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """Context manager for database sessions."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db() -> None:
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)


def drop_db() -> None:
    """Drop all database tables."""
    Base.metadata.drop_all(bind=engine)


def check_db_connection() -> bool:
    """Check if database connection is working."""
    try:
        with get_db_session() as db:
            db.execute("SELECT 1")
        return True
    except Exception:
        return False
