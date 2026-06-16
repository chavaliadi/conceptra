"""
Database connection, session management, and initialization for Conceptra.

Usage:
  - FastAPI dependency: `db: AsyncSession = Depends(get_db)`
  - On startup: `await init_db()`
  - On shutdown: `await close_db()`
"""

import os
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Load from env — falls back to local dev default
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://localhost/conceptra",
)

# echo=True logs every SQL statement — useful for debugging, off in prod
engine = create_async_engine(
    DATABASE_URL,
    echo=os.getenv("SQL_ECHO", "false").lower() == "true",
    pool_pre_ping=True,  # reconnect if connection was dropped
    pool_size=5,
    max_overflow=10,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # keep objects usable after commit
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — yields a DB session and closes it after the request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Create all tables on startup (safe to call repeatedly — won't drop existing)."""
    from app.models.database import Base  # import here to avoid circular imports

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Dispose engine connection pool on shutdown."""
    await engine.dispose()
