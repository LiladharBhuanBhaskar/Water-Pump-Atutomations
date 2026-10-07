"""
HydraControl — Database Session and Engine Infrastructure
Provides async and sync SQLAlchemy engines, session factories, and dependency injectors.
"""
from typing import AsyncGenerator, Generator
from contextlib import asynccontextmanager, contextmanager
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
    AsyncEngine
)
from sqlalchemy.orm import sessionmaker, Session

try:
    from app.core.config import settings
except ImportError:
    from backend.app.core.config import settings

# Engine configuration arguments based on dialect
is_sqlite = settings.DATABASE_URL.startswith("sqlite")
async_engine_kwargs = {"echo": settings.DEBUG}
sync_engine_kwargs = {"echo": settings.DEBUG}

if is_sqlite:
    async_engine_kwargs["connect_args"] = {"check_same_thread": False}
    sync_engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    # PostgreSQL connection pooling optimizations
    async_engine_kwargs["pool_pre_ping"] = True
    async_engine_kwargs["pool_size"] = 10
    async_engine_kwargs["max_overflow"] = 20
    sync_engine_kwargs["pool_pre_ping"] = True
    sync_engine_kwargs["pool_size"] = 10
    sync_engine_kwargs["max_overflow"] = 20

# 1. Async Engine & Session Factory (FastAPI async request cycle)
async_engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    **async_engine_kwargs
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False
)

# 2. Sync Engine & Session Factory (Alembic migrations, seeds, utilities)
sync_engine = create_engine(
    settings.SYNC_DATABASE_URL,
    **sync_engine_kwargs
)

SyncSessionLocal = sessionmaker(
    bind=sync_engine,
    class_=Session,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False
)


# 3. FastAPI Async Database Dependency
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that provides an isolated async database session per request.
    Handles automatic commit on success and rollback on exceptions.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# 4. Context managers for scripts & background workers
@asynccontextmanager
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Async context manager for background workers and task runners."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@contextmanager
def get_sync_session() -> Generator[Session, None, None]:
    """Sync context manager for CLI scripts, migrations, and synchronous seed utilities."""
    session = SyncSessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


async def check_db_health() -> dict:
    """Probes the database connection using a lightweight scalar query."""
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(text("SELECT 1"))
            scalar = result.scalar()
            if scalar == 1:
                return {
                    "status": "connected",
                    "database": "sqlite" if is_sqlite else "postgresql",
                    "ping": "ok"
                }
            return {
                "status": "unhealthy",
                "details": f"Unexpected ping result: {scalar}"
            }
    except Exception as exc:
        return {
            "status": "disconnected",
            "error": str(exc)
        }
