import pytest
import uuid
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
from app.models.sensor import Sensor, SensorStatus, SensorType
from app.core.security import create_access_token, get_password_hash

@pytest.fixture(scope="module", autouse=True)
def setup_tables():
    """Create database tables for Controller API tests and drop after."""
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
# 1. AUTHENTICATION & RBAC TESTS FOR CREATE (POST /controllers)
# ============================================================================

def test_create_controller_unauthenticated(client: TestClient):
    payload = {"station_id": str(uuid.uuid4()), "name": "Unauth Ctrl", "controller_code": "CTRL-UNAUTH", "device_uid": "UID-UNAUTH"}
    res = client.post("/api/v1/controllers", json=payload)
    assert res.status_code == 401

def test_create_controller_rbac_roles(client: TestClient):
    org = helper_create_org("CTRL-ORG-01", "Ctrl Org One")
    site = helper_create_site(org.id, "SITE-CTRL-01", "Site Ctrl 1")
    station = helper_create_station(site.id, "STN-CTRL-01", "Station Ctrl 1")

    _, super_token = helper_create_user("super.ctrl@example.com", UserRole.SUPER_ADMIN, org.id)
    _, org_admin_token = helper_create_user("orgadmin.ctrl@example.com", UserRole.ORGANIZATION_ADMIN, org.id)
    _, site_mgr_token = helper_create_user("sitemgr.ctrl@example.com", UserRole.SITE_MANAGER, org.id)
    _, operator_token = helper_create_user("operator.ctrl@example.com", UserRole.STATION_OPERATOR, org.id)
    _, viewer_token = helper_create_user("viewer.ctrl@example.com", UserRole.VIEWER, org.id)

    payload = {
        "station_id": str(station.id),
        "name": "Main Pump Controller",
        "controller_code": "CTRL-01",
        "device_uid": "ESP32-UID-0001",
        "controller_type": "ESP32"
    }

    # Forbidden roles
    assert client.post("/api/v1/controllers", json=payload, headers={"Authorization": f"Bearer {operator_token}"}).status_code == 403
    assert client.post("/api/v1/controllers", json=payload, headers={"Authorization": f"Bearer {viewer_token}"}).status_code == 403

    # Allowed roles
    res_mgr = client.post("/api/v1/controllers", json=payload, headers={"Authorization": f"Bearer {site_mgr_token}"})
    assert res_mgr.status_code == 201
    assert res_mgr.json()["controller_code"] == "CTRL-01"
    assert res_mgr.json()["station_id"] == str(station.id)
    assert res_mgr.json()["device_uid"] == "ESP32-UID-0001"

    res_admin = client.post("/api/v1/controllers", json={"station_id": str(station.id), "name": "Borewell Controller", "controller_code": "CTRL-02", "device_uid": "ESP32-UID-0002"}, headers={"Authorization": f"Bearer {org_admin_token}"})
    assert res_admin.status_code == 201

    res_super = client.post("/api/v1/controllers", json={"station_id": str(station.id), "name": "RO Controller", "controller_code": "CTRL-03", "device_uid": "ESP32-UID-0003"}, headers={"Authorization": f"Bearer {super_token}"})
    assert res_super.status_code == 201

def test_create_controller_foreign_station_isolation(client: TestClient):
    org1 = helper_create_org("CTRL-LOCK-01", "Ctrl Lock Org 1")
    site1 = helper_create_site(org1.id, "SITE-CLOCK-01", "Site Clock 1")
    station1 = helper_create_station(site1.id, "STN-CLOCK-01", "Stn Clock 1")

    org2 = helper_create_org("CTRL-LOCK-02", "Ctrl Lock Org 2")
    site2 = helper_create_site(org2.id, "SITE-CLOCK-02", "Site Clock 2")
    station2 = helper_create_station(site2.id, "STN-CLOCK-02", "Stn Clock 2")

    _, user1_token = helper_create_user("user1.ctrllock@example.com", UserRole.ORGANIZATION_ADMIN, org1.id)

    # User 1 from Org 1 attempts to create controller under Station 2 (Org 2) -> 404 Not Found
    payload = {
        "station_id": str(station2.id),
        "name": "Tampered Controller",
        "controller_code": "TAMP-CTRL-01",
        "device_uid": "ESP32-TAMP-001"
    }
    res = client.post("/api/v1/controllers", json=payload, headers={"Authorization": f"Bearer {user1_token}"})
    assert res.status_code == 404
    assert res.json()["detail"] == "Station not found"

def test_create_controller_uniqueness_checks(client: TestClient):
    org = helper_create_org("DUP-CTRL-ORG", "Dup Ctrl Org")
    site = helper_create_site(org.id, "DUP-CTRL-SITE", "Dup Ctrl Site")
    station = helper_create_station(site.id, "DUP-CTRL-STN", "Dup Ctrl Station")
    _, token = helper_create_user("admin.dupctrl@example.com", UserRole.ORGANIZATION_ADMIN, org.id)

    payload = {"station_id": str(station.id), "name": "Controller One", "controller_code": "DUP-CTRL-01", "device_uid": "ESP32-DUP-01"}
    res1 = client.post("/api/v1/controllers", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert res1.status_code == 201

    # Duplicate code in same station -> 409
    res2 = client.post("/api/v1/controllers", json={"station_id": str(station.id), "name": "Controller Two", "controller_code": "dup-ctrl-01", "device_uid": "ESP32-DUP-02"}, headers={"Authorization": f"Bearer {token}"})
    assert res2.status_code == 409
    assert "already exists in this station" in res2.json()["detail"]

    # Duplicate device_uid globally -> 409
    res3 = client.post("/api/v1/controllers", json={"station_id": str(station.id), "name": "Controller Three", "controller_code": "DUP-CTRL-03", "device_uid": "ESP32-DUP-01"}, headers={"Authorization": f"Bearer {token}"})
    assert res3.status_code == 409
    assert "already exists" in res3.json()["detail"]

# ============================================================================
# 2. LIST CONTROLLERS (GET /controllers) & TENANT/STATION ISOLATION
# ============================================================================

def test_list_controllers_tenant_isolation(client: TestClient):
    org_a = helper_create_org("LIST-CTRL-A", "List Ctrl Org A")
    site_a = helper_create_site(org_a.id, "CSA-01", "Ctrl Site A")
    stn_a = helper_create_station(site_a.id, "STNA-01", "Ctrl Stn A")

    org_b = helper_create_org("LIST-CTRL-B", "List Ctrl Org B")
    site_b = helper_create_site(org_b.id, "CSB-01", "Ctrl Site B")
    stn_b = helper_create_station(site_b.id, "STNB-01", "Ctrl Stn B")

    _, super_token = helper_create_user("super.listctrl@example.com", UserRole.SUPER_ADMIN, org_a.id)
    _, admin_a_token = helper_create_user("admin.listctrla@example.com", UserRole.ORGANIZATION_ADMIN, org_a.id)

    client.post("/api/v1/controllers", json={"station_id": str(stn_a.id), "name": "Ctrl A1", "controller_code": "CA1", "device_uid": "UID-A1"}, headers={"Authorization": f"Bearer {super_token}"})
    client.post("/api/v1/controllers", json={"station_id": str(stn_b.id), "name": "Ctrl B1", "controller_code": "CB1", "device_uid": "UID-B1"}, headers={"Authorization": f"Bearer {super_token}"})

    # User A lists controllers -> receives ONLY Ctrl A1
    res_a = client.get("/api/v1/controllers", headers={"Authorization": f"Bearer {admin_a_token}"})
    assert res_a.status_code == 200
    codes_a = [c["controller_code"] for c in res_a.json()]
    assert "CA1" in codes_a
    assert "CB1" not in codes_a

    # User A filters by foreign station_id -> empty list
    res_a_foreign = client.get(f"/api/v1/controllers?station_id={stn_b.id}", headers={"Authorization": f"Bearer {admin_a_token}"})
    assert res_a_foreign.status_code == 200
    assert res_a_foreign.json() == []

# ============================================================================
# 3. RETRIEVE CONTROLLER (GET /controllers/{id}) & IDOR / SITE LIFECYCLE CHECKS
# ============================================================================

def test_get_controller_idor_protection(client: TestClient):
    org_a = helper_create_org("GET-CTRL-A", "Get Ctrl Org A")
    site_a = helper_create_site(org_a.id, "GCSA-01", "Get Ctrl Site A")
    stn_a = helper_create_station(site_a.id, "GSTNA-01", "Get Ctrl Stn A")

    org_b = helper_create_org("GET-CTRL-B", "Get Ctrl Org B")
    site_b = helper_create_site(org_b.id, "GCSB-01", "Get Ctrl Site B")
    stn_b = helper_create_station(site_b.id, "GSTNB-01", "Get Ctrl Stn B")

    _, super_token = helper_create_user("super.getctrl@example.com", UserRole.SUPER_ADMIN, org_a.id)
    _, admin_a_token = helper_create_user("admin.getctrla@example.com", UserRole.ORGANIZATION_ADMIN, org_a.id)

    res_b = client.post("/api/v1/controllers", json={"station_id": str(stn_b.id), "name": "Private Ctrl B", "controller_code": "PRCB", "device_uid": "UID-PRCB"}, headers={"Authorization": f"Bearer {super_token}"})
    ctrl_b_id = uuid.UUID(res_b.json()["id"])

    # Admin A attempts IDOR access to Org B controller -> 404 Not Found
    res_idor = client.get(f"/api/v1/controllers/{ctrl_b_id}", headers={"Authorization": f"Bearer {admin_a_token}"})
    assert res_idor.status_code == 404
    assert res_idor.json()["detail"] == "Controller not found"

def test_get_controller_parent_site_operational_status(client: TestClient):
    org = helper_create_org("CTRL-STAT-ORG", "Ctrl Stat Org")
    site = helper_create_site(org.id, "INACT-CSITE", "Active Site Initially", status=SiteStatus.ACTIVE)
    station = helper_create_station(site.id, "INACT-CSTN", "Parent Station")

    _, super_token = helper_create_user("super.ctrlstat@example.com", UserRole.SUPER_ADMIN, org.id)
    _, operator_token = helper_create_user("operator.ctrlstat@example.com", UserRole.STATION_OPERATOR, org.id)

    res_ctrl = client.post("/api/v1/controllers", json={"station_id": str(station.id), "name": "Inactive Parent Ctrl", "controller_code": "INACT-CTRL", "device_uid": "UID-INACT-01"}, headers={"Authorization": f"Bearer {super_token}"})
    ctrl_id = uuid.UUID(res_ctrl.json()["id"])

    # Update site to INACTIVE directly in DB
    with get_sync_session() as session:
        db_site = session.get(Site, site.id)
        db_site.status = SiteStatus.INACTIVE
        session.commit()

    # Access controller under inactive site -> 403 Forbidden
    res = client.get(f"/api/v1/controllers/{ctrl_id}", headers={"Authorization": f"Bearer {operator_token}"})
    assert res.status_code == 403
    assert "Site is inactive" in res.json()["detail"]

# ============================================================================
# 4. UPDATE CONTROLLER (PUT/PATCH /controllers/{id})
# ============================================================================

def test_update_controller(client: TestClient):
    org = helper_create_org("UPD-CTRL-ORG", "Upd Ctrl Org")
    site = helper_create_site(org.id, "UPD-CTRL-SITE", "Upd Ctrl Site")
    station = helper_create_station(site.id, "UPD-CTRL-STN", "Upd Ctrl Stn")

    _, super_token = helper_create_user("super.updctrl@example.com", UserRole.SUPER_ADMIN, org.id)
    _, admin_token = helper_create_user("admin.updctrl@example.com", UserRole.ORGANIZATION_ADMIN, org.id)
    _, viewer_token = helper_create_user("viewer.updctrl@example.com", UserRole.VIEWER, org.id)

    res = client.post("/api/v1/controllers", json={"station_id": str(station.id), "name": "Old Controller Name", "controller_code": "OLD-CTRL", "device_uid": "UID-OLD-CTRL"}, headers={"Authorization": f"Bearer {super_token}"})
    ctrl_id = uuid.UUID(res.json()["id"])

    # Viewer cannot update -> 403 Forbidden
    assert client.patch(f"/api/v1/controllers/{ctrl_id}", json={"name": "Hacked Name"}, headers={"Authorization": f"Bearer {viewer_token}"}).status_code == 403

    # Org Admin update -> 200 OK
    res_upd = client.put(f"/api/v1/controllers/{ctrl_id}", json={"name": "New Controller Name", "controller_code": "NEW-CTRL", "device_uid": "UID-NEW-CTRL", "description": "Updated pump controller"}, headers={"Authorization": f"Bearer {admin_token}"})
    assert res_upd.status_code == 200
    assert res_upd.json()["name"] == "New Controller Name"
    assert res_upd.json()["controller_code"] == "NEW-CTRL"
    assert res_upd.json()["device_uid"] == "UID-NEW-CTRL"
    assert res_upd.json()["description"] == "Updated pump controller"

# ============================================================================
# 5. DELETE CONTROLLER (DELETE /controllers/{id}) & RESTRICT CHECKS
# ============================================================================

def test_delete_controller_success(client: TestClient):
    org = helper_create_org("DEL-CTRL-ORG", "Del Ctrl Org")
    site = helper_create_site(org.id, "DEL-CTRL-SITE", "Del Ctrl Site")
    station = helper_create_station(site.id, "DEL-CTRL-STN", "Del Ctrl Stn")

    _, super_token = helper_create_user("super.delctrl@example.com", UserRole.SUPER_ADMIN, org.id)
    _, admin_token = helper_create_user("admin.delctrl@example.com", UserRole.ORGANIZATION_ADMIN, org.id)

    res = client.post("/api/v1/controllers", json={"station_id": str(station.id), "name": "Controller To Delete", "controller_code": "DEL-CTRL-01", "device_uid": "UID-DEL-01"}, headers={"Authorization": f"Bearer {super_token}"})
    ctrl_id = uuid.UUID(res.json()["id"])

    res_del = client.delete(f"/api/v1/controllers/{ctrl_id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert res_del.status_code == 204

    res_get = client.get(f"/api/v1/controllers/{ctrl_id}", headers={"Authorization": f"Bearer {super_token}"})
    assert res_get.status_code == 404

def test_delete_controller_with_dependent_motors_fails(client: TestClient):
    org = helper_create_org("MTR-CTRL-ORG", "Mtr Ctrl Org")
    site = helper_create_site(org.id, "MTR-CTRL-SITE", "Mtr Ctrl Site")
    station = helper_create_station(site.id, "MTR-CTRL-STN", "Mtr Ctrl Stn")

    _, super_token = helper_create_user("super.mtrctrl@example.com", UserRole.SUPER_ADMIN, org.id)

    res_ctrl = client.post("/api/v1/controllers", json={"station_id": str(station.id), "name": "Controller With Motor", "controller_code": "MTR-CTRL-01", "device_uid": "UID-MTR-01"}, headers={"Authorization": f"Bearer {super_token}"})
    ctrl_id = uuid.UUID(res_ctrl.json()["id"])

    # Attach dependent motor in DB
    with get_sync_session() as session:
        motor = Motor(
            id=uuid.uuid4(),
            controller_id=ctrl_id,
            name="Test Motor",
            motor_code="MTR-01",
            motor_type=MotorType.WATER_PUMP,
            status=MotorStatus.OFF
        )
        session.add(motor)
        session.commit()

    # Delete controller fails with 400 Bad Request
    res_del = client.delete(f"/api/v1/controllers/{ctrl_id}", headers={"Authorization": f"Bearer {super_token}"})
    assert res_del.status_code == 400
    assert "Cannot delete controller with active motors or sensors" in res_del.json()["detail"]

def test_delete_controller_with_dependent_sensors_fails(client: TestClient):
    org = helper_create_org("SNR-CTRL-ORG", "Snr Ctrl Org")
    site = helper_create_site(org.id, "SNR-CTRL-SITE", "Snr Ctrl Site")
    station = helper_create_station(site.id, "SNR-CTRL-STN", "Snr Ctrl Stn")

    _, super_token = helper_create_user("super.snrctrl@example.com", UserRole.SUPER_ADMIN, org.id)

    res_ctrl = client.post("/api/v1/controllers", json={"station_id": str(station.id), "name": "Controller With Sensor", "controller_code": "SNR-CTRL-01", "device_uid": "UID-SNR-01"}, headers={"Authorization": f"Bearer {super_token}"})
    ctrl_id = uuid.UUID(res_ctrl.json()["id"])

    # Attach dependent sensor in DB
    with get_sync_session() as session:
        sensor = Sensor(
            id=uuid.uuid4(),
            controller_id=ctrl_id,
            name="Test Sensor",
            sensor_code="SNR-01",
            sensor_type=SensorType.WATER_LEVEL,
            status=SensorStatus.ACTIVE
        )
        session.add(sensor)
        session.commit()

    # Delete controller fails with 400 Bad Request
    res_del = client.delete(f"/api/v1/controllers/{ctrl_id}", headers={"Authorization": f"Bearer {super_token}"})
    assert res_del.status_code == 400
    assert "Cannot delete controller with active motors or sensors" in res_del.json()["detail"]
