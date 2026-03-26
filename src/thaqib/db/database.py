"""
Database session management.

Uses synchronous SQLAlchemy with SQLite for MVP (SRS §2.3).
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.thaqib.config.settings import get_settings

settings = get_settings()

engine = create_engine(
    settings.database_url,
    echo=settings.debug,
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_db():
    """FastAPI dependency that yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
