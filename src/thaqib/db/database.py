from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.thaqib.config.settings import get_settings

settings = get_settings()

# We are using synchronous SQLite mostly according to settings, but supporting SQLAlchemy 2.0.
# The settings show `sqlite:///./data/thaqib.db`
engine = create_engine(
    settings.database_url, 
    echo=settings.debug,
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {}
)

SessionLocal = sessionmaker(
    autocommit=False, 
    autoflush=False, 
    bind=engine
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
