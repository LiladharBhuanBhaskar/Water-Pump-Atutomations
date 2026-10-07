import os
import sys
import pytest
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import sessionmaker

# Ensure backend root is in sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

workspace_dir = backend_dir.parent
test_db_path = os.path.join(workspace_dir, "test_hydracontrol.db").replace("\\", "/")

# Override environment variables for test execution
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{test_db_path}"
os.environ["SYNC_DATABASE_URL"] = f"sqlite:///{test_db_path}"

from app.core.config import settings
from app.db.base import Base
import app.models  # Ensure all models are registered
import app.db.session as db_session

# Configure test engines and session factories
test_sync_engine = create_engine(
    f"sqlite:///{test_db_path}",
    connect_args={"check_same_thread": False},
    echo=False
)
test_async_engine = create_async_engine(
    f"sqlite+aiosqlite:///{test_db_path}",
    connect_args={"check_same_thread": False},
    echo=False
)

# Re-bind app db session references for test isolation
db_session.sync_engine = test_sync_engine
db_session.async_engine = test_async_engine
db_session.SyncSessionLocal = sessionmaker(
    bind=test_sync_engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False
)
db_session.AsyncSessionLocal = async_sessionmaker(
    bind=test_async_engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False
)


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Create test database schema before tests and remove test database afterwards."""
    Base.metadata.create_all(bind=test_sync_engine)
    yield
    test_sync_engine.dispose()
    if os.path.exists(test_db_path):
        try:
            os.remove(test_db_path)
        except Exception:
            pass


@pytest.fixture(autouse=True)
def reset_rate_limiter_state():
    """Ensure clean rate limiter state per test for strict test isolation."""
    from app.core.rate_limiter import rate_limiter
    rate_limiter.reset()
    yield
    rate_limiter.reset()
