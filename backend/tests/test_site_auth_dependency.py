"""
HydraControl — Site Authorization Dependency Tests (LOOP 2)
Tests get_current_site dependency and policy enforcement across statuses and roles.
"""
import uuid
import pytest
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base
from app.db.session import sync_engine, get_sync_session, get_db
from app.models.organization import Organization, OrganizationStatus
from app.models.site import Site, SiteType, SiteStatus
from app.models.user import User, UserRole
from app.api.deps import get_current_site, get_current_user, get_current_organization
from app.core.security import create_access_token, get_password_hash

site_auth_app = FastAPI()

@site_auth_app.get("/api/v1/test/sites/{site_id}")
async def read_site_endpoint(
    site: Site = Depends(get_current_site)
):
    return {
        "id": str(site.id),
        "site_code": site.site_code,
        "name": site.name,
        "status": site.status.value
    }


@pytest.fixture(scope="module", autouse=True)
def setup_tables():
    Base.metadata.create_all(bind=sync_engine)
    yield
    Base.metadata.drop_all(bind=sync_engine)


@pytest.fixture(scope="module")
def site_auth_data():
    with get_sync_session() as session:
        org_a = Organization(
            id=uuid.uuid4(),
            name="Org Alpha",
            organization_code="OA-001",
            status=OrganizationStatus.ACTIVE
        )
        org_b = Organization(
            id=uuid.uuid4(),
            name="Org Beta",
            organization_code="OB-001",
            status=OrganizationStatus.ACTIVE
        )
        session.add_all([org_a, org_b])
        session.commit()

        # Sites under Org A
        active_site = Site(
            id=uuid.uuid4(),
            organization_id=org_a.id,
            name="Active Plant",
            site_code="ACT-01",
            site_type=SiteType.WATER_PLANT,
            status=SiteStatus.ACTIVE
        )
        inactive_site = Site(
            id=uuid.uuid4(),
            organization_id=org_a.id,
            name="Inactive Plant",
            site_code="INACT-01",
            site_type=SiteType.WATER_PLANT,
            status=SiteStatus.INACTIVE
        )
        suspended_site = Site(
            id=uuid.uuid4(),
            organization_id=org_a.id,
            name="Suspended Plant",
            site_code="SUSP-01",
            site_type=SiteType.WATER_PLANT,
            status=SiteStatus.SUSPENDED
        )
        maintenance_site = Site(
            id=uuid.uuid4(),
            organization_id=org_a.id,
            name="Maintenance Plant",
            site_code="MAINT-01",
            site_type=SiteType.WATER_PLANT,
            status=SiteStatus.MAINTENANCE
        )

        # Site under Org B
        foreign_site = Site(
            id=uuid.uuid4(),
            organization_id=org_b.id,
            name="Beta Site",
            site_code="BETA-01",
            site_type=SiteType.FACTORY,
            status=SiteStatus.ACTIVE
        )

        session.add_all([active_site, inactive_site, suspended_site, maintenance_site, foreign_site])
        session.commit()

        # Users under Org A with different roles
        users = {}
        for role in UserRole:
            u = User(
                id=uuid.uuid4(),
                name=f"User {role.value}",
                email=f"user_{role.value.lower()}@alpha.com",
                password_hash=get_password_hash("pass"),
                role=role,
                is_active=True,
                organization_id=org_a.id
            )
            session.add(u)
            users[role] = u

        session.commit()

        return {
            "org_a": org_a.id,
            "org_b": org_b.id,
            "active_site_id": active_site.id,
            "inactive_site_id": inactive_site.id,
            "suspended_site_id": suspended_site.id,
            "maintenance_site_id": maintenance_site.id,
            "foreign_site_id": foreign_site.id,
            "users": {role: u.id for role, u in users.items()}
        }


def test_get_current_site_active_success(site_auth_data):
    client = TestClient(site_auth_app)
    user_id = site_auth_data["users"][UserRole.VIEWER]
    token = create_access_token(subject=str(user_id))
    headers = {"Authorization": f"Bearer {token}"}

    site_id = str(site_auth_data["active_site_id"])
    res = client.get(f"/api/v1/test/sites/{site_id}", headers=headers)
    assert res.status_code == 200
    assert res.json()["id"] == site_id
    assert res.json()["site_code"] == "ACT-01"


def test_get_current_site_inactive_forbidden(site_auth_data):
    client = TestClient(site_auth_app)
    user_id = site_auth_data["users"][UserRole.SITE_MANAGER]
    token = create_access_token(subject=str(user_id))
    headers = {"Authorization": f"Bearer {token}"}

    site_id = str(site_auth_data["inactive_site_id"])
    res = client.get(f"/api/v1/test/sites/{site_id}", headers=headers)
    assert res.status_code == 403
    assert res.json()["detail"] == "Site is inactive"


def test_get_current_site_suspended_forbidden(site_auth_data):
    client = TestClient(site_auth_app)
    user_id = site_auth_data["users"][UserRole.ORGANIZATION_ADMIN]
    token = create_access_token(subject=str(user_id))
    headers = {"Authorization": f"Bearer {token}"}

    site_id = str(site_auth_data["suspended_site_id"])
    res = client.get(f"/api/v1/test/sites/{site_id}", headers=headers)
    assert res.status_code == 403
    assert res.json()["detail"] == "Site is suspended"


@pytest.mark.parametrize("role,expected_status", [
    (UserRole.SUPER_ADMIN, 200),
    (UserRole.ORGANIZATION_ADMIN, 200),
    (UserRole.SITE_MANAGER, 200),
    (UserRole.TECHNICIAN, 200),
    (UserRole.OWNER, 200),
    (UserRole.STATION_OPERATOR, 403),
    (UserRole.VIEWER, 403),
    (UserRole.FAMILY_MEMBER, 403),
])
def test_get_current_site_maintenance_role_policy(site_auth_data, role, expected_status):
    client = TestClient(site_auth_app)
    user_id = site_auth_data["users"][role]
    token = create_access_token(subject=str(user_id))
    headers = {"Authorization": f"Bearer {token}"}

    site_id = str(site_auth_data["maintenance_site_id"])
    res = client.get(f"/api/v1/test/sites/{site_id}", headers=headers)
    assert res.status_code == expected_status
    if expected_status == 403:
        assert res.json()["detail"] == "Site is under maintenance"


def test_get_current_site_foreign_org_returns_404(site_auth_data):
    client = TestClient(site_auth_app)
    user_id = site_auth_data["users"][UserRole.ORGANIZATION_ADMIN]
    token = create_access_token(subject=str(user_id))
    headers = {"Authorization": f"Bearer {token}"}

    # Requesting Org B's site using Org A credentials
    foreign_site_id = str(site_auth_data["foreign_site_id"])
    res = client.get(f"/api/v1/test/sites/{foreign_site_id}", headers=headers)
    assert res.status_code == 404
    assert res.json()["detail"] == "Site not found"
