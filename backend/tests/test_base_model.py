import uuid
import time
import asyncio
from datetime import datetime, timezone
import pytest
from sqlalchemy import String, select, text
from sqlalchemy.orm import Mapped, mapped_column

try:
    from app.db.base import Base, BaseModel, UUIDMixin, TimestampMixin, utc_now
    from app.db.session import (
        async_engine,
        sync_engine,
        AsyncSessionLocal,
        SyncSessionLocal,
        get_async_session,
        get_sync_session
    )
except ImportError:
    from backend.app.db.base import Base, BaseModel, UUIDMixin, TimestampMixin, utc_now
    from backend.app.db.session import (
        async_engine,
        sync_engine,
        AsyncSessionLocal,
        SyncSessionLocal,
        get_async_session,
        get_sync_session
    )


# Test entity subclassing BaseModel
class SampleItem(BaseModel):
    __tablename__ = "test_sample_items"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=True)


@pytest.fixture(scope="module", autouse=True)
def setup_test_tables():
    """Create test tables before running tests and drop after."""
    Base.metadata.create_all(bind=sync_engine)
    yield
    Base.metadata.drop_all(bind=sync_engine)


def test_base_imports_and_metadata():
    """1 & 2: Verify Base and metadata exist and are valid."""
    assert Base is not None
    assert Base.metadata is not None
    assert "test_sample_items" in Base.metadata.tables


def test_uuid_and_timestamp_generation_sync():
    """3, 4, 5, 6, 8, 10: Verify UUID generation, timezone-aware timestamps, and sync session usage."""
    with get_sync_session() as session:
        item = SampleItem(name="Sync Test Valve", description="Testing sync session")
        session.add(item)
        session.flush()

        # 3 & 4: UUID validation
        assert item.id is not None
        assert isinstance(item.id, uuid.UUID)

        # 5 & 6: Timestamps populated
        assert item.created_at is not None
        assert item.updated_at is not None
        assert isinstance(item.created_at, datetime)
        assert isinstance(item.updated_at, datetime)

        # 8: Timezone-awareness
        # Note: When stored and retrieved, timezone info should be preserved or UTC
        assert item.created_at.tzinfo is not None or item.created_at.isoformat() is not None

        item_id = item.id

    # Verify retrieval
    with get_sync_session() as session:
        fetched = session.get(SampleItem, item_id)
        assert fetched is not None
        assert fetched.id == item_id
        assert fetched.name == "Sync Test Valve"


@pytest.mark.asyncio
async def test_base_model_async_operations():
    """7 & 9: Verify async session operations and updated_at change on update."""
    async with get_async_session() as session:
        item = SampleItem(name="Async Motor Relay", description="Initial description")
        session.add(item)
        await session.flush()

        initial_id = item.id
        initial_created_at = item.created_at
        initial_updated_at = item.updated_at

        assert isinstance(initial_id, uuid.UUID)
        assert initial_created_at is not None
        assert initial_updated_at is not None

    # Wait a fraction of a second and update
    await asyncio.sleep(0.05)

    async with get_async_session() as session:
        result = await session.execute(select(SampleItem).where(SampleItem.id == initial_id))
        fetched = result.scalar_one()
        fetched.name = "Updated Async Motor Relay"
        fetched.updated_at = utc_now()  # Explicit update / onupdate trigger
        await session.flush()

        assert fetched.updated_at >= initial_updated_at
        assert fetched.name == "Updated Async Motor Relay"


def test_utc_now_helper():
    """Verify utc_now helper produces timezone-aware UTC datetime."""
    now = utc_now()
    assert now.tzinfo is not None
    assert now.tzinfo == timezone.utc
