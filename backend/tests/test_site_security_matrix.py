"""
HydraControl — Site Authorization Security Attack Matrix (LOOP 5 & LOOP 6)
Verifies full end-to-end security chain:
JWT -> get_current_user -> require_roles -> get_current_organization -> get_current_site -> resource -> response.
Includes IDOR, cross-site, cross-org, and role permutation attacks.
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
from app.api.deps import get_current_user, require_roles, get_current_organization, get_current_site
from app.services.site_auth import get_site_scoped_resource
from app.core.security import create_access_token, get_password_hash

site_security_app = FastAPI()

@site_security_app.get("/api/v1/sites/{site_id}/motors/{motor_id}")
async def site_scoped_motor_endpoint(
    motor_id: uuid.UUID,
    client_site_override: uuid.UUID = None,  # Parameter tampering simulation
    current_site: Site = Depends(get_current_site),
    current_org: Organization = Depends(get_current_organization),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    # Enforces site-level authorization and tenant boundaries
    motor = await get_site_scoped_resource(
        session, Motor, motor_id, current_site.id, current_org.id
    )
    if motor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Motor not found"
        )
    return {
        "id": str(motor.id),
        "name": motor.name,
        "site": current_site.site_code,
        "organization": current_org.organization_code
    }


@site_security_app.get("/api/v1/admin/sites/{site_id}/motors/{motor_id}")
async def admin_site_motor_endpoint(
    motor_id: uuid.UUID,
    current_site: Site = Depends(get_current_site),
    current_org: Organization = Depends(get_current_organization),
    current_user: User = Depends(require_roles([UserRole.SUPER_ADMIN, UserRole.ORGANIZATION_ADMIN, UserRole.SITE_MANAGER])),
    session: AsyncSession = Depends(get_db)
):
    motor = await get_site_scoped_resource(
        session, Motor, motor_id, current_site.id, current_org.id
    )
    if motor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Motor not found"
        )
    return {
        "id": str(motor.id),
        "name": motor.name,
        "site": current_site.site_code,
        "admin": current_user.email
    }


@pytest.fixture(scope="module", autouse=True)
def setup_tables():
    Base.metadata.create_all(bind=sync_engine)
    yield
    Base.metadata.drop_all(bind=sync_engine)


@pytest.fixture(scope="module")
def matrix_env():
    with get_sync_session() as session:
        # 1. Organization A and Organization B
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

        # 2. Site A1 and Site A2 (under Org A), Site B1 (under Org B)
        site_a1 = Site(id=uuid.uuid4(), organization_id=org_a.id, name="Site A1", site_code="SA1", site_type=SiteType.HOME)
        site_a2 = Site(id=uuid.uuid4(), organization_id=org_a.id, name="Site A2", site_code="SA2", site_type=SiteType.HOME)
        site_b1 = Site(id=uuid.uuid4(), organization_id=org_b.id, name="Site B1", site_code="SB1", site_type=SiteType.HOME)
        session.add_all([site_a1, site_a2, site_b1])
        session.commit()

        # 3. Hierarchy under Site A1: Station -> Controller -> Motor A1
        stn_a1 = Station(id=uuid.uuid4(), site_id=site_a1.id, name="Stn A1", station_code="STA1", station_type=StationType.HOME_PUMP)
        ctrl_a1 = Controller(id=uuid.uuid4(), station_id=stn_a1.id, name="Ctrl A1", controller_code="CA1", device_uid="UID-A1", controller_type=ControllerType.ESP32)
        motor_a1 = Motor(id=uuid.uuid4(), controller_id=ctrl_a1.id, name="Motor A1", motor_code="MA1", motor_type=MotorType.WATER_PUMP)
        session.add_all([stn_a1, ctrl_a1, motor_a1])

        # 4. Hierarchy under Site A2: Station -> Controller -> Motor A2
        stn_a2 = Station(id=uuid.uuid4(), site_id=site_a2.id, name="Stn A2", station_code="STA2", station_type=StationType.HOME_PUMP)
        ctrl_a2 = Controller(id=uuid.uuid4(), station_id=stn_a2.id, name="Ctrl A2", controller_code="CA2", device_uid="UID-A2", controller_type=ControllerType.ESP32)
        motor_a2 = Motor(id=uuid.uuid4(), controller_id=ctrl_a2.id, name="Motor A2", motor_code="MA2", motor_type=MotorType.WATER_PUMP)
        session.add_all([stn_a2, ctrl_a2, motor_a2])

        # 5. Hierarchy under Site B1: Station -> Controller -> Motor B1
        stn_b1 = Station(id=uuid.uuid4(), site_id=site_b1.id, name="Stn B1", station_code="STB1", station_type=StationType.HOME_PUMP)
        ctrl_b1 = Controller(id=uuid.uuid4(), station_id=stn_b1.id, name="Ctrl B1", controller_code="CB1", device_uid="UID-B1", controller_type=ControllerType.ESP32)
        motor_b1 = Motor(id=uuid.uuid4(), controller_id=ctrl_b1.id, name="Motor B1", motor_code="MB1", motor_type=MotorType.WATER_PUMP)
        session.add_all([stn_b1, ctrl_b1, motor_b1])
        session.commit()

        # 6. Users for Org A and Org B
        user_admin_a = User(
            id=uuid.uuid4(),
            name="Admin A",
            email="admin_a@alpha.com",
            password_hash=get_password_hash("pass"),
            role=UserRole.ORGANIZATION_ADMIN,
            is_active=True,
            organization_id=org_a.id
        )
        user_operator_a = User(
            id=uuid.uuid4(),
            name="Operator A",
            email="operator_a@alpha.com",
            password_hash=get_password_hash("pass"),
            role=UserRole.STATION_OPERATOR,
            is_active=True,
            organization_id=org_a.id
        )
        user_viewer_a = User(
            id=uuid.uuid4(),
            name="Viewer A",
            email="viewer_a@alpha.com",
            password_hash=get_password_hash("pass"),
            role=UserRole.VIEWER,
            is_active=True,
            organization_id=org_a.id
        )
        user_admin_b = User(
            id=uuid.uuid4(),
            name="Admin B",
            email="admin_b@beta.com",
            password_hash=get_password_hash("pass"),
            role=UserRole.ORGANIZATION_ADMIN,
            is_active=True,
            organization_id=org_b.id
        )
        session.add_all([user_admin_a, user_operator_a, user_viewer_a, user_admin_b])
        session.commit()

        return {
            "site_a1": site_a1.id,
            "site_a2": site_a2.id,
            "site_b1": site_b1.id,
            "motor_a1": motor_a1.id,
            "motor_a2": motor_a2.id,
            "motor_b1": motor_b1.id,
            "admin_a": user_admin_a.id,
            "operator_a": user_operator_a.id,
            "viewer_a": user_viewer_a.id,
            "admin_b": user_admin_b.id,
        }


def test_site_authorized_access(matrix_env):
    client = TestClient(site_security_app)
    token = create_access_token(subject=str(matrix_env["operator_a"]))
    headers = {"Authorization": f"Bearer {token}"}

    site_a1 = str(matrix_env["site_a1"])
    motor_a1 = str(matrix_env["motor_a1"])

    # User A -> Site A1 -> Motor A1: ALLOW (200)
    res = client.get(f"/api/v1/sites/{site_a1}/motors/{motor_a1}", headers=headers)
    assert res.status_code == 200
    assert res.json()["id"] == motor_a1
    assert res.json()["site"] == "SA1"


def test_cross_site_mismatch_denied(matrix_env):
    client = TestClient(site_security_app)
    token = create_access_token(subject=str(matrix_env["operator_a"]))
    headers = {"Authorization": f"Bearer {token}"}

    site_a1 = str(matrix_env["site_a1"])
    motor_a2 = str(matrix_env["motor_a2"])  # Motor belongs to Site A2, not Site A1

    # Request Motor A2 under Site A1 route: DENIED (404 Not Found)
    res = client.get(f"/api/v1/sites/{site_a1}/motors/{motor_a2}", headers=headers)
    assert res.status_code == 404
    assert res.json()["detail"] == "Motor not found"


def test_cross_org_site_denied(matrix_env):
    client = TestClient(site_security_app)
    token = create_access_token(subject=str(matrix_env["operator_a"]))
    headers = {"Authorization": f"Bearer {token}"}

    site_b1 = str(matrix_env["site_b1"])  # Site belongs to Org B
    motor_b1 = str(matrix_env["motor_b1"])

    # User A requesting Site B1: DENIED (404 Not Found)
    res = client.get(f"/api/v1/sites/{site_b1}/motors/{motor_b1}", headers=headers)
    assert res.status_code == 404
    assert res.json()["detail"] == "Site not found"


def test_parameter_tampering_site_override(matrix_env):
    client = TestClient(site_security_app)
    token = create_access_token(subject=str(matrix_env["operator_a"]))
    headers = {"Authorization": f"Bearer {token}"}

    site_a1 = str(matrix_env["site_a1"])
    motor_a2 = str(matrix_env["motor_a2"])
    site_a2 = str(matrix_env["site_a2"])

    # Attempting to override site context via query parameter
    res = client.get(
        f"/api/v1/sites/{site_a1}/motors/{motor_a2}?client_site_override={site_a2}",
        headers=headers
    )
    assert res.status_code == 404
    assert res.json()["detail"] == "Motor not found"


def test_rbac_and_site_full_chain(matrix_env):
    client = TestClient(site_security_app)
    
    token_admin_a = create_access_token(subject=str(matrix_env["admin_a"]))
    token_viewer_a = create_access_token(subject=str(matrix_env["viewer_a"]))
    token_admin_b = create_access_token(subject=str(matrix_env["admin_b"]))

    headers_admin_a = {"Authorization": f"Bearer {token_admin_a}"}
    headers_viewer_a = {"Authorization": f"Bearer {token_viewer_a}"}
    headers_admin_b = {"Authorization": f"Bearer {token_admin_b}"}

    site_a1 = str(matrix_env["site_a1"])
    motor_a1 = str(matrix_env["motor_a1"])

    # 1. Admin A on Admin Endpoint (RBAC allowed + Site valid) -> ALLOW (200)
    res = client.get(f"/api/v1/admin/sites/{site_a1}/motors/{motor_a1}", headers=headers_admin_a)
    assert res.status_code == 200
    assert res.json()["id"] == motor_a1

    # 2. Viewer A on Admin Endpoint (RBAC denied) -> 403 Forbidden
    res = client.get(f"/api/v1/admin/sites/{site_a1}/motors/{motor_a1}", headers=headers_viewer_a)
    assert res.status_code == 403
    assert res.json()["detail"] == "Not enough permissions"

    # 3. Admin B on Admin Endpoint for Site A1 (Foreign Org) -> 404 Not Found (RBAC does NOT bypass Site/Org isolation)
    res = client.get(f"/api/v1/admin/sites/{site_a1}/motors/{motor_a1}", headers=headers_admin_b)
    assert res.status_code == 404
    assert res.json()["detail"] == "Site not found"
