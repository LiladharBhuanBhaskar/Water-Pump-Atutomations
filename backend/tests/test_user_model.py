import uuid
import pytest
import asyncio
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

try:
    from app.db.base import Base, BaseModel
    from app.models.user import User, UserRole
    from app.db.session import (
        sync_engine,
        get_async_session,
        get_sync_session
    )
except ImportError:
    from backend.app.db.base import Base, BaseModel
    from backend.app.models.user import User, UserRole
    from backend.app.db.session import (
        sync_engine,
        get_async_session,
        get_sync_session
    )


@pytest.fixture(scope="module", autouse=True)
def setup_user_tables():
    """Create user tables before running tests and clean up after."""
    Base.metadata.create_all(bind=sync_engine)
    yield
    Base.metadata.drop_all(bind=sync_engine)


def test_user_model_inheritance_and_metadata():
    """Verify User model inherits from BaseModel and is present in Base.metadata."""
    assert issubclass(User, BaseModel)
    assert "users" in Base.metadata.tables
    table = Base.metadata.tables["users"]
    assert "id" in table.columns
    assert "email" in table.columns
    assert "password_hash" in table.columns
    assert "role" in table.columns
    assert "is_active" in table.columns
    assert "organization_id" in table.columns
    assert "created_at" in table.columns
    assert "updated_at" in table.columns


def test_user_creation_sync():
    """Verify sync session creation, default values, and UUID generation."""
    with get_sync_session() as session:
        user = User(
            name="Bhaskar Singh",
            email="bhaskar.singh@example.com",
            password_hash="$2b$12$e8Yt8LgN7mD2Zc5wF0RkJu9Xk1t4...",
            role=UserRole.SUPER_ADMIN
        )
        session.add(user)
        session.flush()

        assert user.id is not None
        assert isinstance(user.id, uuid.UUID)
        assert user.name == "Bhaskar Singh"
        assert user.email == "bhaskar.singh@example.com"
        assert user.role == UserRole.SUPER_ADMIN
        assert user.is_active is True
        assert user.organization_id is None
        assert isinstance(user.created_at, datetime)
        assert isinstance(user.updated_at, datetime)
        user_id = user.id

    # Verify query
    with get_sync_session() as session:
        queried = session.get(User, user_id)
        assert queried is not None
        assert queried.id == user_id
        assert queried.email == "bhaskar.singh@example.com"
        assert str(queried).startswith("<User bhaskar.singh@example.com")


def test_user_email_uniqueness():
    """Verify database enforces unique constraint on email."""
    with pytest.raises(IntegrityError):
        with get_sync_session() as session:
            duplicate_user = User(
                name="Duplicate User",
                email="bhaskar.singh@example.com",  # Already exists
                password_hash="some_hash",
                role=UserRole.VIEWER
            )
            session.add(duplicate_user)
            session.flush()


def test_user_roles_coverage():
    """Verify both Enterprise and Home user roles can be persisted and retrieved."""
    roles_to_test = [
        (UserRole.ORGANIZATION_ADMIN, "org_admin@hydracontrol.io"),
        (UserRole.SITE_MANAGER, "site_mgr@hydracontrol.io"),
        (UserRole.STATION_OPERATOR, "operator@hydracontrol.io"),
        (UserRole.TECHNICIAN, "tech@hydracontrol.io"),
        (UserRole.VIEWER, "viewer@hydracontrol.io"),
        (UserRole.OWNER, "home_owner@hydracontrol.io"),
        (UserRole.FAMILY_MEMBER, "family@hydracontrol.io"),
    ]

    with get_sync_session() as session:
        for role, email in roles_to_test:
            u = User(
                name=f"Test {role.value}",
                email=email,
                password_hash="hash_dummy",
                role=role
            )
            session.add(u)
        session.flush()

    # Query back and verify roles
    with get_sync_session() as session:
        for role, email in roles_to_test:
            result = session.execute(select(User).where(User.email == email)).scalar_one()
            assert result.role == role


@pytest.mark.asyncio
async def test_user_async_crud_and_updated_at():
    """Verify async session creation, query, and updated_at modification."""
    async with get_async_session() as session:
        user = User(
            name="Async Operator",
            email="async.operator@hydracontrol.io",
            password_hash="hashed_async_password",
            role=UserRole.STATION_OPERATOR
        )
        session.add(user)
        await session.flush()
        user_id = user.id
        initial_updated_at = user.updated_at

    await asyncio.sleep(0.05)

    async with get_async_session() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user_to_update = result.scalar_one()
        user_to_update.name = "Async Senior Operator"
        user_to_update.role = UserRole.SITE_MANAGER
        await session.flush()

        assert user_to_update.name == "Async Senior Operator"
        assert user_to_update.role == UserRole.SITE_MANAGER
        assert user_to_update.updated_at >= initial_updated_at
