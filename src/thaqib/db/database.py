"""
Database session management.

Engine configuration is DB-agnostic and driven by ``settings.database_url``:

* **SQLite** (development default): ``check_same_thread=False`` so the engine can be
  shared across FastAPI's thread pool. SQLite serializes writes (single writer), which
  is fine for local development and the test suite.
* **PostgreSQL** (production / pilot): connection pooling with ``pool_pre_ping`` to drop
  stale connections, plus a recycle window. PostgreSQL supports true concurrent writes
  (MVCC), which is required under live multi-hall detection-event load.

Switch databases by setting ``DATABASE_URL`` — no code change needed.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.thaqib.config.settings import get_settings

settings = get_settings()

_is_sqlite = settings.database_url.startswith("sqlite")

if _is_sqlite:
    _engine_kwargs: dict = {
        # Allow the SQLite connection to be used across threads (FastAPI thread pool).
        "connect_args": {"check_same_thread": False},
    }
else:
    # PostgreSQL (or any networked DB): pool tuning for production load.
    _engine_kwargs = {
        "pool_pre_ping": True,   # detect & replace dropped connections before use
        "pool_size": 10,         # persistent connections kept open
        "max_overflow": 20,      # extra connections allowed under burst load
        "pool_recycle": 1800,    # recycle connections after 30 min (avoids stale sockets)
    }

engine = create_engine(
    settings.database_url,
    echo=settings.database_echo,
    **_engine_kwargs,
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
