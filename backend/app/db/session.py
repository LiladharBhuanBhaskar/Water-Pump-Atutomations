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
# echo=False: SQL queries are NOT printed to console. Set to True only when debugging specific queries.
async_engine_kwargs = {"echo": False}
sync_engine_kwargs = {"echo": False}

if is_sqlite:
    from sqlalchemy.pool import NullPool
    async_engine_kwargs["poolclass"] = NullPool
    sync_engine_kwargs["poolclass"] = NullPool
    async_engine_kwargs["connect_args"] = {"check_same_thread": False, "timeout": 30}
    sync_engine_kwargs["connect_args"] = {"check_same_thread": False, "timeout": 30}
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

# 2.1 SQLite High-Concurrency & Zero-Lock Optimization (WAL Mode + Memory Cache)
if is_sqlite:
    from sqlalchemy import event

    @event.listens_for(async_engine.sync_engine, "connect")
    def _set_async_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA cache_size=-64000")
        cursor.execute("PRAGMA temp_store=MEMORY")
        cursor.execute("PRAGMA mmap_size=268435456")
        cursor.close()

    @event.listens_for(sync_engine, "connect")
    def _set_sync_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA cache_size=-64000")
        cursor.execute("PRAGMA temp_store=MEMORY")
        cursor.execute("PRAGMA mmap_size=268435456")
        cursor.close()


# 3. FastAPI Async Database Dependency
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that provides an isolated async database session per request.
    Handles automatic commit on success (only if modified) and rollback on exceptions.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            if session.dirty or session.new or session.deleted:
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
            if session.dirty or session.new or session.deleted:
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
