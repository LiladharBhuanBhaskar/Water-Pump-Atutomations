import pytest
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from fastapi.testclient import TestClient

from app.main import app
from app.db.base import Base
from app.db.session import sync_engine, get_sync_session
from app.models.user import User, UserRole
from app.models.organization import Organization, OrganizationStatus
from app.models.site import Site, SiteStatus, SiteType
from app.models.station import Station, StationStatus, StationType
from app.models.controller import Controller, ControllerStatus, ControllerType
from app.models.motor import Motor, MotorStatus, MotorType
from app.models.motor_command import MotorCommand, CommandType, CommandStatus
from app.models.motor_event import MotorEvent, MotorEventType, MotorEventSource
from app.models.automation_rule import AutomationRule, AutomationRuleType, AutomationRuleStatus, AutomationAction
from app.core.security import create_access_token, get_password_hash

@pytest.fixture(scope="module", autouse=True)
def setup_tables():
    """Create database tables for Motor API tests and drop after."""
    Base.metadata.create_all(bind=sync_engine)
    yield
    Base.metadata.drop_all(bind=sync_engine)

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c

def helper_create_org(code: str, name: str) -> Organization:
    org_id = uuid.uuid4()
    with get_sync_session() as session:
        org = Organization(
            id=org_id,
            name=name,
            organization_code=code,
            status=OrganizationStatus.ACTIVE
        )
        session.add(org)
        session.commit()
        session.refresh(org)
    return org

def helper_create_site(org_id: uuid.UUID, code: str, name: str, status: SiteStatus = SiteStatus.ACTIVE) -> Site:
    site_id = uuid.uuid4()
    with get_sync_session() as session:
        site = Site(
            id=site_id,
            organization_id=org_id,
            name=name,
            site_code=code,
            site_type=SiteType.HOME,
            status=status
        )
        session.add(site)
        session.commit()
        session.refresh(site)
    return site

def helper_create_station(site_id: uuid.UUID, code: str, name: str) -> Station:
    station_id = uuid.uuid4()
    with get_sync_session() as session:
        station = Station(
            id=station_id,
            site_id=site_id,
            name=name,
            station_code=code,
            station_type=StationType.HOME_PUMP,
            status=StationStatus.ACTIVE
        )
        session.add(station)
        session.commit()
        session.refresh(station)
    return station

def helper_create_controller(station_id: uuid.UUID, code: str, uid: str) -> Controller:
    ctrl_id = uuid.uuid4()
    with get_sync_session() as session:
        ctrl = Controller(
            id=ctrl_id,
            station_id=station_id,
            name="Parent Controller",
            controller_code=code,
            device_uid=uid,
            controller_type=ControllerType.ESP32,
            status=ControllerStatus.ACTIVE
        )
        session.add(ctrl)
        session.commit()
        session.refresh(ctrl)
    return ctrl

def helper_create_user(email: str, role: UserRole, organization_id: uuid.UUID = None) -> tuple[User, str]:
    user_id = uuid.uuid4()
    with get_sync_session() as session:
        user = User(
            id=user_id,
            name=f"User {role.value}",
            email=email,
            password_hash=get_password_hash("password123"),
            role=role,
            is_active=True,
            organization_id=organization_id
        )
        session.add(user)
        session.commit()
    token = create_access_token(subject=str(user_id))
    return user, token

# ============================================================================
# 1. AUTHENTICATION & RBAC TESTS FOR CREATE (POST /motors)
# ============================================================================

def test_create_motor_unauthenticated(client: TestClient):
    payload = {"controller_id": str(uuid.uuid4()), "name": "Unauth Motor", "motor_code": "MTR-UNAUTH"}
    res = client.post("/api/v1/motors", json=payload)
    assert res.status_code == 401

def test_create_motor_rbac_roles(client: TestClient):
    org = helper_create_org("MTR-ORG-01", "Mtr Org One")
    site = helper_create_site(org.id, "SITE-MTR-01", "Site Mtr 1")
    station = helper_create_station(site.id, "STN-MTR-01", "Station Mtr 1")
    ctrl = helper_create_controller(station.id, "CTRL-MTR-01", "UID-MTR-01")

    _, super_token = helper_create_user("super.mtr@example.com", UserRole.SUPER_ADMIN, org.id)
    _, org_admin_token = helper_create_user("orgadmin.mtr@example.com", UserRole.ORGANIZATION_ADMIN, org.id)
    _, site_mgr_token = helper_create_user("sitemgr.mtr@example.com", UserRole.SITE_MANAGER, org.id)
    _, operator_token = helper_create_user("operator.mtr@example.com", UserRole.STATION_OPERATOR, org.id)
    _, viewer_token = helper_create_user("viewer.mtr@example.com", UserRole.VIEWER, org.id)

    payload = {
        "controller_id": str(ctrl.id),
        "name": "Submersible Pump 1",
        "motor_code": "MTR-01",
        "motor_type": "SUBMERSIBLE_PUMP",
        "rated_power": 5.5
    }

    # Forbidden roles
    assert client.post("/api/v1/motors", json=payload, headers={"Authorization": f"Bearer {operator_token}"}).status_code == 403
    assert client.post("/api/v1/motors", json=payload, headers={"Authorization": f"Bearer {viewer_token}"}).status_code == 403

    # Allowed roles
    res_mgr = client.post("/api/v1/motors", json=payload, headers={"Authorization": f"Bearer {site_mgr_token}"})
    assert res_mgr.status_code == 201
    assert res_mgr.json()["motor_code"] == "MTR-01"
    assert res_mgr.json()["controller_id"] == str(ctrl.id)
    assert Decimal(str(res_mgr.json()["rated_power"])) == Decimal("5.50")

    res_admin = client.post("/api/v1/motors", json={"controller_id": str(ctrl.id), "name": "Booster Pump 2", "motor_code": "MTR-02"}, headers={"Authorization": f"Bearer {org_admin_token}"})
    assert res_admin.status_code == 201

    res_super = client.post("/api/v1/motors", json={"controller_id": str(ctrl.id), "name": "Borewell Pump 3", "motor_code": "MTR-03"}, headers={"Authorization": f"Bearer {super_token}"})
    assert res_super.status_code == 201

def test_create_motor_foreign_controller_isolation(client: TestClient):
    org1 = helper_create_org("MTR-LOCK-01", "Mtr Lock Org 1")
    site1 = helper_create_site(org1.id, "SITE-MLOCK-01", "Site MLock 1")
    stn1 = helper_create_station(site1.id, "STN-MLOCK-01", "Stn MLock 1")
    ctrl1 = helper_create_controller(stn1.id, "CTRL-MLOCK-01", "UID-MLOCK-01")

    org2 = helper_create_org("MTR-LOCK-02", "Mtr Lock Org 2")
    site2 = helper_create_site(org2.id, "SITE-MLOCK-02", "Site MLock 2")
    stn2 = helper_create_station(site2.id, "STN-MLOCK-02", "Stn MLock 2")
    ctrl2 = helper_create_controller(stn2.id, "CTRL-MLOCK-02", "UID-MLOCK-02")

    _, user1_token = helper_create_user("user1.mtrlock@example.com", UserRole.ORGANIZATION_ADMIN, org1.id)

    # User 1 from Org 1 attempts to create motor under Controller 2 (Org 2) -> 404 Not Found
    payload = {
        "controller_id": str(ctrl2.id),
        "name": "Tampered Motor",
        "motor_code": "TAMP-MTR-01"
    }
    res = client.post("/api/v1/motors", json=payload, headers={"Authorization": f"Bearer {user1_token}"})
    assert res.status_code == 404
    assert res.json()["detail"] == "Controller not found"

def test_create_motor_duplicate_code(client: TestClient):
    org = helper_create_org("DUP-MTR-ORG", "Dup Mtr Org")
    site = helper_create_site(org.id, "DUP-MTR-SITE", "Dup Mtr Site")
    stn = helper_create_station(site.id, "DUP-MTR-STN", "Dup Mtr Station")
    ctrl = helper_create_controller(stn.id, "DUP-MTR-CTRL", "UID-DUP-MTR-01")
    _, token = helper_create_user("admin.dupmtr@example.com", UserRole.ORGANIZATION_ADMIN, org.id)

    payload = {"controller_id": str(ctrl.id), "name": "Motor One", "motor_code": "DUP-MTR-01"}
    res1 = client.post("/api/v1/motors", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert res1.status_code == 201

    # Duplicate code in same controller -> 409
    res2 = client.post("/api/v1/motors", json={"controller_id": str(ctrl.id), "name": "Motor Two", "motor_code": "dup-mtr-01"}, headers={"Authorization": f"Bearer {token}"})
    assert res2.status_code == 409
    assert "already exists in this controller" in res2.json()["detail"]

# ============================================================================
# 2. LIST MOTORS (GET /motors) & TENANT/CONTROLLER ISOLATION
# ============================================================================

def test_list_motors_tenant_isolation(client: TestClient):
    org_a = helper_create_org("LIST-MTR-A", "List Mtr Org A")
    site_a = helper_create_site(org_a.id, "MSA-01", "Mtr Site A")
    stn_a = helper_create_station(site_a.id, "MSTNA-01", "Mtr Stn A")
    ctrl_a = helper_create_controller(stn_a.id, "MCTRLA-01", "UID-MTR-A1")

    org_b = helper_create_org("LIST-MTR-B", "List Mtr Org B")
    site_b = helper_create_site(org_b.id, "MSB-01", "Mtr Site B")
    stn_b = helper_create_station(site_b.id, "MSTNB-01", "Mtr Stn B")
    ctrl_b = helper_create_controller(stn_b.id, "MCTRLB-01", "UID-MTR-B1")

    _, super_token = helper_create_user("super.listmtr@example.com", UserRole.SUPER_ADMIN, org_a.id)
    _, admin_a_token = helper_create_user("admin.listmtra@example.com", UserRole.ORGANIZATION_ADMIN, org_a.id)

    client.post("/api/v1/motors", json={"controller_id": str(ctrl_a.id), "name": "Motor A1", "motor_code": "MA1"}, headers={"Authorization": f"Bearer {super_token}"})
    client.post("/api/v1/motors", json={"controller_id": str(ctrl_b.id), "name": "Motor B1", "motor_code": "MB1"}, headers={"Authorization": f"Bearer {super_token}"})

    # User A lists motors -> receives ONLY Motor A1
    res_a = client.get("/api/v1/motors", headers={"Authorization": f"Bearer {admin_a_token}"})
    assert res_a.status_code == 200
    codes_a = [m["motor_code"] for m in res_a.json()]
    assert "MA1" in codes_a
    assert "MB1" not in codes_a

    # User A filters by foreign controller_id -> empty list
    res_a_foreign = client.get(f"/api/v1/motors?controller_id={ctrl_b.id}", headers={"Authorization": f"Bearer {admin_a_token}"})
    assert res_a_foreign.status_code == 200
    assert res_a_foreign.json() == []

# ============================================================================
# 3. RETRIEVE MOTOR (GET /motors/{id}) & IDOR / SITE LIFECYCLE CHECKS
# ============================================================================

def test_get_motor_idor_protection(client: TestClient):
    org_a = helper_create_org("GET-MTR-A", "Get Mtr Org A")
    site_a = helper_create_site(org_a.id, "GMSA-01", "Get Mtr Site A")
    stn_a = helper_create_station(site_a.id, "GMSTNA-01", "Get Mtr Stn A")
    ctrl_a = helper_create_controller(stn_a.id, "GMCTRLA-01", "UID-GMTR-A1")

    org_b = helper_create_org("GET-MTR-B", "Get Mtr Org B")
    site_b = helper_create_site(org_b.id, "GMSB-01", "Get Mtr Site B")
    stn_b = helper_create_station(site_b.id, "GMSTNB-01", "Get Mtr Stn B")
    ctrl_b = helper_create_controller(stn_b.id, "GMCTRLB-01", "UID-GMTR-B1")

    _, super_token = helper_create_user("super.getmtr@example.com", UserRole.SUPER_ADMIN, org_a.id)
    _, admin_a_token = helper_create_user("admin.getmtra@example.com", UserRole.ORGANIZATION_ADMIN, org_a.id)

    res_b = client.post("/api/v1/motors", json={"controller_id": str(ctrl_b.id), "name": "Private Mtr B", "motor_code": "PRMB"}, headers={"Authorization": f"Bearer {super_token}"})
    mtr_b_id = uuid.UUID(res_b.json()["id"])

    # Admin A attempts IDOR access to Org B motor -> 404 Not Found
    res_idor = client.get(f"/api/v1/motors/{mtr_b_id}", headers={"Authorization": f"Bearer {admin_a_token}"})
    assert res_idor.status_code == 404
    assert res_idor.json()["detail"] == "Motor not found"

def test_get_motor_parent_site_operational_status(client: TestClient):
    org = helper_create_org("MTR-STAT-ORG", "Mtr Stat Org")
    site = helper_create_site(org.id, "INACT-MSITE", "Active Site Initially", status=SiteStatus.ACTIVE)
    stn = helper_create_station(site.id, "INACT-MSTN", "Parent Station")
    ctrl = helper_create_controller(stn.id, "INACT-MCTRL", "UID-INACT-M01")

    _, super_token = helper_create_user("super.mtrstat@example.com", UserRole.SUPER_ADMIN, org.id)
    _, operator_token = helper_create_user("operator.mtrstat@example.com", UserRole.STATION_OPERATOR, org.id)

    res_mtr = client.post("/api/v1/motors", json={"controller_id": str(ctrl.id), "name": "Inactive Parent Motor", "motor_code": "INACT-MTR"}, headers={"Authorization": f"Bearer {super_token}"})
    mtr_id = uuid.UUID(res_mtr.json()["id"])

    # Update site to INACTIVE directly in DB
    with get_sync_session() as session:
        db_site = session.get(Site, site.id)
        db_site.status = SiteStatus.INACTIVE
        session.commit()

    # Access motor under inactive site -> 403 Forbidden
    res = client.get(f"/api/v1/motors/{mtr_id}", headers={"Authorization": f"Bearer {operator_token}"})
    assert res.status_code == 403
    assert "Site is inactive" in res.json()["detail"]

# ============================================================================
# 4. UPDATE MOTOR (PUT/PATCH /motors/{id})
# ============================================================================

def test_update_motor(client: TestClient):
    org = helper_create_org("UPD-MTR-ORG", "Upd Mtr Org")
    site = helper_create_site(org.id, "UPD-MTR-SITE", "Upd Mtr Site")
    stn = helper_create_station(site.id, "UPD-MTR-STN", "Upd Mtr Stn")
    ctrl = helper_create_controller(stn.id, "UPD-MTR-CTRL", "UID-UPD-MTR")

    _, super_token = helper_create_user("super.updmtr@example.com", UserRole.SUPER_ADMIN, org.id)
    _, admin_token = helper_create_user("admin.updmtr@example.com", UserRole.ORGANIZATION_ADMIN, org.id)
    _, viewer_token = helper_create_user("viewer.updmtr@example.com", UserRole.VIEWER, org.id)

    res = client.post("/api/v1/motors", json={"controller_id": str(ctrl.id), "name": "Old Motor Name", "motor_code": "OLD-MTR", "rated_power": 3.0}, headers={"Authorization": f"Bearer {super_token}"})
    mtr_id = uuid.UUID(res.json()["id"])

    # Viewer cannot update -> 403 Forbidden
    assert client.patch(f"/api/v1/motors/{mtr_id}", json={"name": "Hacked Name"}, headers={"Authorization": f"Bearer {viewer_token}"}).status_code == 403

    # Org Admin update -> 200 OK
    res_upd = client.put(f"/api/v1/motors/{mtr_id}", json={"name": "New Motor Name", "motor_code": "NEW-MTR", "rated_power": 7.5, "description": "Updated heavy pump"}, headers={"Authorization": f"Bearer {admin_token}"})
    assert res_upd.status_code == 200
    assert res_upd.json()["name"] == "New Motor Name"
    assert res_upd.json()["motor_code"] == "NEW-MTR"
    assert Decimal(str(res_upd.json()["rated_power"])) == Decimal("7.50")
    assert res_upd.json()["description"] == "Updated heavy pump"

# ============================================================================
# 5. DELETE MOTOR (DELETE /motors/{id}) & RESTRICT CHECKS
# ============================================================================

def test_delete_motor_success(client: TestClient):
    org = helper_create_org("DEL-MTR-ORG", "Del Mtr Org")
    site = helper_create_site(org.id, "DEL-MTR-SITE", "Del Mtr Site")
    stn = helper_create_station(site.id, "DEL-MTR-STN", "Del Mtr Stn")
    ctrl = helper_create_controller(stn.id, "DEL-MTR-CTRL", "UID-DEL-MTR-01")

    _, super_token = helper_create_user("super.delmtr@example.com", UserRole.SUPER_ADMIN, org.id)
    _, admin_token = helper_create_user("admin.delmtr@example.com", UserRole.ORGANIZATION_ADMIN, org.id)

    res = client.post("/api/v1/motors", json={"controller_id": str(ctrl.id), "name": "Motor To Delete", "motor_code": "DEL-MTR-01"}, headers={"Authorization": f"Bearer {super_token}"})
    mtr_id = uuid.UUID(res.json()["id"])

    res_del = client.delete(f"/api/v1/motors/{mtr_id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert res_del.status_code == 204

    res_get = client.get(f"/api/v1/motors/{mtr_id}", headers={"Authorization": f"Bearer {super_token}"})
    assert res_get.status_code == 404

def test_delete_motor_with_dependent_commands_fails(client: TestClient):
    org = helper_create_org("CMD-MTR-ORG", "Cmd Mtr Org")
    site = helper_create_site(org.id, "CMD-MTR-SITE", "Cmd Mtr Site")
    stn = helper_create_station(site.id, "CMD-MTR-STN", "Cmd Mtr Stn")
    ctrl = helper_create_controller(stn.id, "CMD-MTR-CTRL", "UID-CMD-MTR")

    _, super_token = helper_create_user("super.cmdmtr@example.com", UserRole.SUPER_ADMIN, org.id)

    res_mtr = client.post("/api/v1/motors", json={"controller_id": str(ctrl.id), "name": "Motor With Command", "motor_code": "CMD-MTR-01"}, headers={"Authorization": f"Bearer {super_token}"})
    mtr_id = uuid.UUID(res_mtr.json()["id"])

    # Attach dependent command in DB
    with get_sync_session() as session:
        cmd = MotorCommand(
            id=uuid.uuid4(),
            motor_id=mtr_id,
            command_type=CommandType.START,
            status=CommandStatus.PENDING,
            requested_at=datetime.now(timezone.utc)
        )
        session.add(cmd)
        session.commit()

    # Delete motor fails with 400 Bad Request
    res_del = client.delete(f"/api/v1/motors/{mtr_id}", headers={"Authorization": f"Bearer {super_token}"})
    assert res_del.status_code == 400
    assert "Cannot delete motor with active commands, events, or automation rules" in res_del.json()["detail"]

def test_delete_motor_with_dependent_events_fails(client: TestClient):
    org = helper_create_org("EVT-MTR-ORG", "Evt Mtr Org")
    site = helper_create_site(org.id, "EVT-MTR-SITE", "Evt Mtr Site")
    stn = helper_create_station(site.id, "EVT-MTR-STN", "Evt Mtr Stn")
    ctrl = helper_create_controller(stn.id, "EVT-MTR-CTRL", "UID-EVT-MTR")

    _, super_token = helper_create_user("super.evtmtr@example.com", UserRole.SUPER_ADMIN, org.id)

    res_mtr = client.post("/api/v1/motors", json={"controller_id": str(ctrl.id), "name": "Motor With Event", "motor_code": "EVT-MTR-01"}, headers={"Authorization": f"Bearer {super_token}"})
    mtr_id = uuid.UUID(res_mtr.json()["id"])

    # Attach dependent event in DB
    with get_sync_session() as session:
        evt = MotorEvent(
            id=uuid.uuid4(),
            motor_id=mtr_id,
            event_type=MotorEventType.STARTED,
            source=MotorEventSource.USER,
            occurred_at=datetime.now(timezone.utc)
        )
        session.add(evt)
        session.commit()

    # Delete motor fails with 400 Bad Request
    res_del = client.delete(f"/api/v1/motors/{mtr_id}", headers={"Authorization": f"Bearer {super_token}"})
    assert res_del.status_code == 400
    assert "Cannot delete motor with active commands, events, or automation rules" in res_del.json()["detail"]
