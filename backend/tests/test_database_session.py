import pytest
from sqlalchemy import text
try:
    from app.db.session import (
        get_db,
        get_async_session,
        get_sync_session,
        check_db_health,
        AsyncSessionLocal,
        SyncSessionLocal
    )
except ImportError:
    from backend.app.db.session import (
        get_db,
        get_async_session,
        get_sync_session,
        check_db_health,
        AsyncSessionLocal,
        SyncSessionLocal
    )


@pytest.mark.asyncio
async def test_check_db_health():
    """Verify database ping health check returns status connected."""
    health = await check_db_health()
    assert health["status"] == "connected"
    assert health.get("ping") == "ok"


@pytest.mark.asyncio
async def test_async_session_query():
    """Verify executing async scalar queries using AsyncSessionLocal."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(text("SELECT 42"))
        val = result.scalar()
        assert val == 42


@pytest.mark.asyncio
async def test_get_db_generator():
    """Verify get_db FastAPI dependency lifecycle."""
    generator = get_db()
    session = await anext(generator)
    assert session is not None
    result = await session.execute(text("SELECT 'hydracontrol'"))
    assert result.scalar() == "hydracontrol"
    # Clean termination
    try:
        await anext(generator)
    except StopAsyncIteration:
        pass


@pytest.mark.asyncio
async def test_get_async_session_context_manager():
    """Verify get_async_session context manager."""
    async with get_async_session() as session:
        result = await session.execute(text("SELECT 100"))
        assert result.scalar() == 100


def test_sync_session_context_manager():
    """Verify get_sync_session synchronous context manager for seeds & scripts."""
    with get_sync_session() as session:
        result = session.execute(text("SELECT 200"))
        assert result.scalar() == 200
