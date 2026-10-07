import uuid
import pytest
import asyncio
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

try:
    from app.db.base import Base, BaseModel
    from app.models.organization import Organization, OrganizationStatus
    from app.models.user import User, UserRole
    from app.db.session import (
        sync_engine,
        get_async_session,
        get_sync_session
    )
except ImportError:
    from backend.app.db.base import Base, BaseModel
    from backend.app.models.organization import Organization, OrganizationStatus
    from backend.app.models.user import User, UserRole
    from backend.app.db.session import (
        sync_engine,
        get_async_session,
        get_sync_session
    )


@pytest.fixture(scope="module", autouse=True)
def setup_org_tables():
    """Create organization & user tables before running tests and clean up after."""
    Base.metadata.create_all(bind=sync_engine)
    yield
    Base.metadata.drop_all(bind=sync_engine)


def test_organization_model_inheritance_and_metadata():
    """Verify Organization model inherits from BaseModel and exists in Base.metadata."""
    assert issubclass(Organization, BaseModel)
    assert "organizations" in Base.metadata.tables
    table = Base.metadata.tables["organizations"]
    assert "id" in table.columns
    assert "name" in table.columns
    assert "organization_code" in table.columns
    assert "status" in table.columns
    assert "created_at" in table.columns
    assert "updated_at" in table.columns


def test_organization_creation_sync():
    """Verify sync session creation, defaults, and UUID generation."""
    with get_sync_session() as session:
        org = Organization(
            name="Acme Water Solutions",
            organization_code="ACME-001"
        )
        session.add(org)
        session.flush()

        assert org.id is not None
        assert isinstance(org.id, uuid.UUID)
        assert org.name == "Acme Water Solutions"
        assert org.organization_code == "ACME-001"
        assert org.status == OrganizationStatus.ACTIVE
        assert isinstance(org.created_at, datetime)
        assert isinstance(org.updated_at, datetime)
        org_id = org.id

    # Verify query
    with get_sync_session() as session:
        queried = session.get(Organization, org_id)
        assert queried is not None
        assert queried.id == org_id
        assert queried.organization_code == "ACME-001"
        assert "ACME-001" in str(queried)


def test_organization_code_uniqueness():
    """Verify unique constraint on organization_code."""
    with pytest.raises(IntegrityError):
        with get_sync_session() as session:
            duplicate_org = Organization(
                name="Another Acme Entity",
                organization_code="ACME-001"  # Already exists
            )
            session.add(duplicate_org)
            session.flush()


def test_organization_status_states():
    """Verify all OrganizationStatus enum values can be stored and retrieved."""
    statuses = [
        (OrganizationStatus.ACTIVE, "JAIPUR-001", "Jaipur Municipal"),
        (OrganizationStatus.INACTIVE, "NOIDA-002", "Noida Industrial"),
        (OrganizationStatus.SUSPENDED, "DELHI-003", "Delhi Commercial"),
    ]

    with get_sync_session() as session:
        for status, code, name in statuses:
            org = Organization(
                name=name,
                organization_code=code,
                status=status
            )
            session.add(org)
        session.flush()

    # Query back
    with get_sync_session() as session:
        for status, code, _ in statuses:
            result = session.execute(
                select(Organization).where(Organization.organization_code == code)
            ).scalar_one()
            assert result.status == status


@pytest.mark.asyncio
async def test_organization_async_crud_and_updated_at():
    """Verify async session creation, query, and updated_at change on update."""
    async with get_async_session() as session:
        org = Organization(
            name="Async Water Utility",
            organization_code="ASYNC-001"
        )
        session.add(org)
        await session.flush()
        org_id = org.id
        initial_updated_at = org.updated_at

    await asyncio.sleep(0.05)

    async with get_async_session() as session:
        result = await session.execute(
            select(Organization).where(Organization.id == org_id)
        )
        org_to_update = result.scalar_one()
        org_to_update.name = "Async Water Utility (Renamed)"
        org_to_update.status = OrganizationStatus.SUSPENDED
        await session.flush()

        assert org_to_update.name == "Async Water Utility (Renamed)"
        assert org_to_update.status == OrganizationStatus.SUSPENDED
        assert org_to_update.updated_at >= initial_updated_at


def test_user_organization_relationship():
    """Verify bidirectional relationship between Organization and User."""
    with get_sync_session() as session:
        # Create Organization
        org = Organization(
            name="Apex Water Systems",
            organization_code="APEX-001"
        )
        session.add(org)
        session.flush()

        # Create Users linked to Organization
        user1 = User(
            name="Admin User",
            email="admin@apexwatersystems.com",
            password_hash="hash1",
            role=UserRole.ORGANIZATION_ADMIN,
            organization=org
        )
        user2 = User(
            name="Tech User",
            email="tech@apexwatersystems.com",
            password_hash="hash2",
            role=UserRole.TECHNICIAN,
            organization_id=org.id
        )
        # Create User with no organization (nullable test)
        unassigned_user = User(
            name="Platform Superadmin",
            email="root@hydracontrol.io",
            password_hash="hash3",
            role=UserRole.SUPER_ADMIN,
            organization_id=None
        )

        session.add_all([user1, user2, unassigned_user])
        session.flush()

        org_id = org.id
        user1_id = user1.id
        unassigned_id = unassigned_user.id

    # Verify Organization -> Users relationship
    with get_sync_session() as session:
        fetched_org = session.get(Organization, org_id)
        assert fetched_org is not None
        assert len(fetched_org.users) == 2
        user_emails = [u.email for u in fetched_org.users]
        assert "admin@apexwatersystems.com" in user_emails
        assert "tech@apexwatersystems.com" in user_emails

    # Verify User -> Organization relationship
    with get_sync_session() as session:
        fetched_user1 = session.get(User, user1_id)
        assert fetched_user1 is not None
        assert fetched_user1.organization is not None
        assert fetched_user1.organization.organization_code == "APEX-001"

        # Verify unassigned user
        fetched_unassigned = session.get(User, unassigned_id)
        assert fetched_unassigned is not None
        assert fetched_unassigned.organization_id is None
        assert fetched_unassigned.organization is None
