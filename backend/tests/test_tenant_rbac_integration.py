"""
HydraControl — Full Security Chain: Authentication + RBAC + Tenant Isolation (LOOP 5)
Verifies the end-to-end security chain:
JWT -> get_current_user -> require_roles -> get_current_organization -> resource ownership -> response.
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
from app.models.station import Station, StationType, StationStatus
from app.models.controller import Controller, ControllerType, ControllerStatus
from app.models.motor import Motor, MotorType, MotorStatus
from app.models.user import User, UserRole
from app.api.deps import get_current_user, require_roles, get_current_organization
from app.services.tenant import get_org_scoped_resource
from app.core.security import create_access_token, get_password_hash

# Integration test app to test combined RBAC + Tenant isolation
integration_app = FastAPI()

@integration_app.get("/api/v1/secure/org-admin/motors/{motor_id}")
async def admin_get_motor_endpoint(
    motor_id: uuid.UUID,
    current_user: User = Depends(require_roles([UserRole.SUPER_ADMIN, UserRole.ORGANIZATION_ADMIN])),
    current_org: Organization = Depends(get_current_organization),
    session: AsyncSession = Depends(get_db)
):
    # Both RBAC (Admin) and Tenant Isolation (Scoped to user's org) are enforced
    motor = await get_org_scoped_resource(session, Motor, motor_id, current_org.id)
    if motor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Motor not found"
        )
    return {
        "id": str(motor.id),
        "name": motor.name,
        "operator": current_user.email,
        "organization": current_org.organization_code
    }


@pytest.fixture(scope="module", autouse=True)
def setup_tables():
    Base.metadata.create_all(bind=sync_engine)
    yield
    Base.metadata.drop_all(bind=sync_engine)


@pytest.fixture(scope="module")
def env_setup():
    with get_sync_session() as session:
        org_a = Organization(
            id=uuid.uuid4(),
            name="Org Alpha",
            organization_code="ORG-A",
            status=OrganizationStatus.ACTIVE
        )
        org_b = Organization(
            id=uuid.uuid4(),
            name="Org Beta",
            organization_code="ORG-B",
            status=OrganizationStatus.ACTIVE
        )
        session.add_all([org_a, org_b])
        session.commit()

        # Users in Org A
        admin_a = User(
            id=uuid.uuid4(),
            name="Admin A",
            email="admin_a@example.com",
            password_hash=get_password_hash("pass"),
            role=UserRole.ORGANIZATION_ADMIN,
            is_active=True,
            organization_id=org_a.id
        )
        viewer_a = User(
            id=uuid.uuid4(),
            name="Viewer A",
            email="viewer_a@example.com",
            password_hash=get_password_hash("pass"),
            role=UserRole.VIEWER,
            is_active=True,
            organization_id=org_a.id
        )
        inactive_a = User(
            id=uuid.uuid4(),
            name="Inactive A",
            email="inactive_a@example.com",
            password_hash=get_password_hash("pass"),
            role=UserRole.ORGANIZATION_ADMIN,
            is_active=False,
            organization_id=org_a.id
        )

        # Users in Org B
        super_admin_b = User(
            id=uuid.uuid4(),
            name="Super Admin B",
            email="super_b@example.com",
            password_hash=get_password_hash("pass"),
            role=UserRole.SUPER_ADMIN,
            is_active=True,
            organization_id=org_b.id
        )

        session.add_all([admin_a, viewer_a, inactive_a, super_admin_b])
        session.commit()

        # Motor A under Org A
        site_a = Site(id=uuid.uuid4(), organization_id=org_a.id, name="S A", site_code="SA", site_type=SiteType.HOME)
        session.add(site_a)
        session.commit()

        stn_a = Station(id=uuid.uuid4(), site_id=site_a.id, name="Stn A", station_code="STA", station_type=StationType.HOME_PUMP)
        session.add(stn_a)
        session.commit()

        ctrl_a = Controller(id=uuid.uuid4(), station_id=stn_a.id, name="Ctrl A", controller_code="CA", device_uid="UID-A", controller_type=ControllerType.ESP32)
        session.add(ctrl_a)
        session.commit()

        motor_a = Motor(id=uuid.uuid4(), controller_id=ctrl_a.id, name="Motor A", motor_code="MA", motor_type=MotorType.WATER_PUMP)
        session.add(motor_a)
        session.commit()

        # Motor B under Org B
        site_b = Site(id=uuid.uuid4(), organization_id=org_b.id, name="S B", site_code="SB", site_type=SiteType.HOME)
        session.add(site_b)
        session.commit()

        stn_b = Station(id=uuid.uuid4(), site_id=site_b.id, name="Stn B", station_code="STB", station_type=StationType.HOME_PUMP)
        session.add(stn_b)
        session.commit()

        ctrl_b = Controller(id=uuid.uuid4(), station_id=stn_b.id, name="Ctrl B", controller_code="CB", device_uid="UID-B", controller_type=ControllerType.ESP32)
        session.add(ctrl_b)
        session.commit()

        motor_b = Motor(id=uuid.uuid4(), controller_id=ctrl_b.id, name="Motor B", motor_code="MB", motor_type=MotorType.WATER_PUMP)
        session.add(motor_b)
        session.commit()

        return {
            "admin_a": admin_a.id,
            "viewer_a": viewer_a.id,
            "inactive_a": inactive_a.id,
            "super_admin_b": super_admin_b.id,
            "motor_a": motor_a.id,
            "motor_b": motor_b.id,
        }


def test_rbac_and_tenant_integration(env_setup):
    client = TestClient(integration_app)
    
    token_admin_a = create_access_token(subject=str(env_setup["admin_a"]))
    token_viewer_a = create_access_token(subject=str(env_setup["viewer_a"]))
    token_inactive_a = create_access_token(subject=str(env_setup["inactive_a"]))
    token_super_b = create_access_token(subject=str(env_setup["super_admin_b"]))

    headers_admin_a = {"Authorization": f"Bearer {token_admin_a}"}
    headers_viewer_a = {"Authorization": f"Bearer {token_viewer_a}"}
    headers_inactive_a = {"Authorization": f"Bearer {token_inactive_a}"}
    headers_super_b = {"Authorization": f"Bearer {token_super_b}"}

    motor_a_id = str(env_setup["motor_a"])
    motor_b_id = str(env_setup["motor_b"])

    # 1. Org A Admin -> Org A Motor: RBAC allowed + Same Org -> ALLOW (200)
    res = client.get(f"/api/v1/secure/org-admin/motors/{motor_a_id}", headers=headers_admin_a)
    assert res.status_code == 200
    assert res.json()["id"] == motor_a_id
    assert res.json()["organization"] == "ORG-A"

    # 2. Org A Viewer -> Org A Motor: RBAC denied -> 403 Forbidden
    res = client.get(f"/api/v1/secure/org-admin/motors/{motor_a_id}", headers=headers_viewer_a)
    assert res.status_code == 403
    assert res.json()["detail"] == "Not enough permissions"

    # 3. Super Admin B -> Org A Motor: RBAC allowed (SUPER_ADMIN), but different org -> 404 DENIED
    # RBAC does not bypass tenant boundary
    res = client.get(f"/api/v1/secure/org-admin/motors/{motor_a_id}", headers=headers_super_b)
    assert res.status_code == 404
    assert res.json()["detail"] == "Motor not found"

    # 4. Super Admin B -> Org B Motor: RBAC allowed + Same Org -> ALLOW (200)
    res = client.get(f"/api/v1/secure/org-admin/motors/{motor_b_id}", headers=headers_super_b)
    assert res.status_code == 200
    assert res.json()["id"] == motor_b_id
    assert res.json()["organization"] == "ORG-B"

    # 5. Inactive User -> 403 Forbidden
    res = client.get(f"/api/v1/secure/org-admin/motors/{motor_a_id}", headers=headers_inactive_a)
    assert res.status_code == 403
    assert res.json()["detail"] == "Inactive user"

    # 6. Unauthenticated User -> 401 Unauthorized
    res = client.get(f"/api/v1/secure/org-admin/motors/{motor_a_id}")
    assert res.status_code == 401

    # 7. Invalid Token -> 401 Unauthorized
    res = client.get(f"/api/v1/secure/org-admin/motors/{motor_a_id}", headers={"Authorization": "Bearer fake.jwt.token"})
    assert res.status_code == 401
