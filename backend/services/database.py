"""Async database connection and session management"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import QueuePool, StaticPool
from contextlib import asynccontextmanager
from config.settings import settings
from models.domain import Base
from utils.logger import logger


# Create async engine with proper connection pooling
# For SQLite: use StaticPool (single connection, thread-safe for async)
# For PostgreSQL: use QueuePool with configurable size
is_sqlite = "sqlite" in settings.database_url

engine = create_async_engine(
    settings.database_url,
    echo=False,
    # SQLite requires StaticPool for async; PostgreSQL uses QueuePool
    poolclass=StaticPool if is_sqlite else QueuePool,
    pool_pre_ping=True,
    # QueuePool settings (ignored for StaticPool/SQLite)
    pool_size=5 if not is_sqlite else None,
    max_overflow=10 if not is_sqlite else None,
    pool_timeout=30 if not is_sqlite else None,
    pool_recycle=1800 if not is_sqlite else None,  # Recycle connections after 30 min
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def init_db():
    """Initialize database - create all tables"""
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("database_initialized")
    except Exception as e:
        logger.error("database_initialization_failed", error=str(e))
        raise


@asynccontextmanager
async def get_db_session():
    """Get async database session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error("database_session_error", error=str(e))
            raise
        finally:
            await session.close()


async def get_db():
    """Dependency for FastAPI routes"""
    async with get_db_session() as session:
        yield session
