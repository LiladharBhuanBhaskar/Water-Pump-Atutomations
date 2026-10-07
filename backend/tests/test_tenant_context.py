"""
HydraControl — Organization Context Dependency Tests (LOOP 1)
Tests get_current_organization dependency and /api/v1/auth/organization endpoint.
"""
import uuid
import pytest
from fastapi import HTTPException, status
from fastapi.testclient import TestClient

from app.main import app
from app.api.deps import get_current_organization
from app.db.base import Base
from app.db.session import sync_engine, get_async_session, get_sync_session
from app.models.user import User, UserRole
from app.models.organization import Organization, OrganizationStatus
from app.core.security import create_access_token, get_password_hash

@pytest.fixture(scope="module", autouse=True)
def setup_tables():
    Base.metadata.create_all(bind=sync_engine)
    yield
    Base.metadata.drop_all(bind=sync_engine)

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c

@pytest.mark.asyncio
async def test_get_current_organization_success():
    async with get_async_session() as session:
        org = Organization(
            id=uuid.uuid4(),
            name="Alpha Corp",
            organization_code="ALPHA-001",
            status=OrganizationStatus.ACTIVE
        )
        session.add(org)
        await session.commit()
        await session.refresh(org)

        user = User(
            id=uuid.uuid4(),
            name="Alpha User",
            email="alpha_user@example.com",
            password_hash=get_password_hash("pass123"),
            role=UserRole.ORGANIZATION_ADMIN,
            is_active=True,
            organization_id=org.id
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

        current_org = await get_current_organization(current_user=user, session=session)
        assert current_org.id == org.id
        assert current_org.organization_code == "ALPHA-001"
        assert current_org.status == OrganizationStatus.ACTIVE


@pytest.mark.asyncio
async def test_get_current_organization_user_without_org():
    async with get_async_session() as session:
        user = User(
            id=uuid.uuid4(),
            name="No Org User",
            email="no_org@example.com",
            password_hash=get_password_hash("pass123"),
            role=UserRole.SUPER_ADMIN,
            is_active=True,
            organization_id=None
        )
        session.add(user)
        await session.commit()

        with pytest.raises(HTTPException) as exc:
            await get_current_organization(current_user=user, session=session)
        assert exc.value.status_code == status.HTTP_403_FORBIDDEN
        assert "does not belong to any organization" in exc.value.detail


@pytest.mark.asyncio
async def test_get_current_organization_nonexistent_org():
    async with get_async_session() as session:
        fake_org_id = uuid.uuid4()
        user = User(
            id=uuid.uuid4(),
            name="Ghost Org User",
            email="ghost_org@example.com",
            password_hash=get_password_hash("pass123"),
            role=UserRole.VIEWER,
            is_active=True,
            organization_id=fake_org_id
        )
        session.add(user)
        await session.commit()

        with pytest.raises(HTTPException) as exc:
            await get_current_organization(current_user=user, session=session)
        assert exc.value.status_code == status.HTTP_404_NOT_FOUND
        assert exc.value.detail == "Organization not found"


@pytest.mark.asyncio
async def test_get_current_organization_inactive_org():
    async with get_async_session() as session:
        inactive_org = Organization(
            id=uuid.uuid4(),
            name="Inactive Corp",
            organization_code="INACT-001",
            status=OrganizationStatus.INACTIVE
        )
        session.add(inactive_org)
        await session.commit()

        user = User(
            id=uuid.uuid4(),
            name="Inactive Org User",
            email="user_inact@example.com",
            password_hash=get_password_hash("pass123"),
            role=UserRole.ORGANIZATION_ADMIN,
            is_active=True,
            organization_id=inactive_org.id
        )
        session.add(user)
        await session.commit()

        with pytest.raises(HTTPException) as exc:
            await get_current_organization(current_user=user, session=session)
        assert exc.value.status_code == status.HTTP_403_FORBIDDEN
        assert "Organization is inactive" in exc.value.detail


@pytest.mark.asyncio
async def test_get_current_organization_suspended_org():
    async with get_async_session() as session:
        suspended_org = Organization(
            id=uuid.uuid4(),
            name="Suspended Corp",
            organization_code="SUSP-001",
            status=OrganizationStatus.SUSPENDED
        )
        session.add(suspended_org)
        await session.commit()

        user = User(
            id=uuid.uuid4(),
            name="Suspended Org User",
            email="user_susp@example.com",
            password_hash=get_password_hash("pass123"),
            role=UserRole.ORGANIZATION_ADMIN,
            is_active=True,
            organization_id=suspended_org.id
        )
        session.add(user)
        await session.commit()

        with pytest.raises(HTTPException) as exc:
            await get_current_organization(current_user=user, session=session)
        assert exc.value.status_code == status.HTTP_403_FORBIDDEN
        assert "Organization is suspended" in exc.value.detail


def test_auth_organization_endpoint_http(client: TestClient):
    # Setup test org and user via sync session
    with get_sync_session() as session:
        org = Organization(
            id=uuid.uuid4(),
            name="HTTP Org",
            organization_code="HTTP-ORG-01",
            status=OrganizationStatus.ACTIVE
        )
        session.add(org)
        session.commit()

        user = User(
            id=uuid.uuid4(),
            name="HTTP Org User",
            email="httporguser@example.com",
            password_hash=get_password_hash("securepass123"),
            role=UserRole.VIEWER,
            is_active=True,
            organization_id=org.id
        )
        session.add(user)
        session.commit()
        user_id = str(user.id)
        org_id = str(org.id)

    token = create_access_token(subject=user_id)
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/api/v1/auth/organization", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == org_id
    assert data["organization_code"] == "HTTP-ORG-01"
    assert data["status"] == "ACTIVE"
