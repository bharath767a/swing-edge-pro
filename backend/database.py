"""
SwingEdge Pro — Database Setup
SQLAlchemy async with SQLite.

AUDIT FIX P2: WAL mode + busy_timeout enabled for concurrent read/write support.
Was: default journal mode → scheduler writes blocked API reads.
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import event
from backend.config import settings
import logging

logger = logging.getLogger(__name__)

# FIX P2: WAL mode for concurrent reads during writes (scheduler writes won't block API reads)
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
)

# Enable WAL mode + busy_timeout at connection time
@event.listens_for(engine.sync_engine, "connect")
def _set_sqlite_pragma(dbapi_conn, connection_record):
    """Enable WAL mode + 5s busy timeout on every new SQLite connection."""
    import sqlite3
    if isinstance(dbapi_conn, sqlite3.Connection):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA synchronous=NORMAL")  # safe with WAL, faster than FULL
        cursor.close()

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    pass


async def init_db():
    """Create all tables."""
    from backend.models import stock  # noqa: F401 — triggers model registration
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database initialized.")


async def get_db():
    """FastAPI dependency: yields an async DB session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
