"""Database session management."""

import logging
import os
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

logger = logging.getLogger(__name__)

# Database URL from environment - no hardcoded credentials
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    logger.warning(
        "DATABASE_URL not set - using default development credentials. "
        "Set DATABASE_URL env var for production."
    )
    DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/agents"

# Create async engine
engine = create_async_engine(
    DATABASE_URL,
    echo=os.getenv("SQL_ECHO", "false").lower() == "true",
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

# Session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_async_session() -> AsyncGenerator[AsyncSession]:
    """Dependency for getting async database sessions."""
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()
