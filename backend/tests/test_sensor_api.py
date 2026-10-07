import pytest
import uuid
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from app.main import app
from app.db.base import Base
from app.db.session import sync_engine, get_sync_session
from app.models.user import User, UserRole
from app.models.organization import Organization, OrganizationStatus
from app.models.site import Site, SiteStatus, SiteType
from app.models.station import Station, StationStatus, StationType
from app.models.controller import Controller, ControllerStatus, ControllerType
from app.models.sensor import Sensor, SensorStatus, SensorType
from app.models.telemetry import TelemetryReading
from app.core.security import create_access_token, get_password_hash

@pytest.fixture(scope="module", autouse=True)
def setup_tables():
    """Create database tables for Sensor API tests and drop after."""
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
# 1. AUTHENTICATION & RBAC TESTS FOR CREATE (POST /sensors)
# ============================================================================

def test_create_sensor_unauthenticated(client: TestClient):
    payload = {"controller_id": str(uuid.uuid4()), "name": "Unauth Sensor", "sensor_code": "SNR-UNAUTH"}
    res = client.post("/api/v1/sensors", json=payload)
    assert res.status_code == 401

def test_create_sensor_rbac_roles(client: TestClient):
    org = helper_create_org("SNR-ORG-01", "Snr Org One")
    site = helper_create_site(org.id, "SITE-SNR-01", "Site Snr 1")
    station = helper_create_station(site.id, "STN-SNR-01", "Station Snr 1")
    ctrl = helper_create_controller(station.id, "CTRL-SNR-01", "UID-SNR-01")

    _, super_token = helper_create_user("super.snr@example.com", UserRole.SUPER_ADMIN, org.id)
    _, org_admin_token = helper_create_user("orgadmin.snr@example.com", UserRole.ORGANIZATION_ADMIN, org.id)
    _, site_mgr_token = helper_create_user("sitemgr.snr@example.com", UserRole.SITE_MANAGER, org.id)
    _, operator_token = helper_create_user("operator.snr@example.com", UserRole.STATION_OPERATOR, org.id)
    _, viewer_token = helper_create_user("viewer.snr@example.com", UserRole.VIEWER, org.id)

    payload = {
        "controller_id": str(ctrl.id),
        "name": "Water Level Sensor 1",
        "sensor_code": "SNR-01",
        "sensor_type": "WATER_LEVEL"
    }

    # Forbidden roles
    assert client.post("/api/v1/sensors", json=payload, headers={"Authorization": f"Bearer {operator_token}"}).status_code == 403
    assert client.post("/api/v1/sensors", json=payload, headers={"Authorization": f"Bearer {viewer_token}"}).status_code == 403

    # Allowed roles
    res_mgr = client.post("/api/v1/sensors", json=payload, headers={"Authorization": f"Bearer {site_mgr_token}"})
    assert res_mgr.status_code == 201
    assert res_mgr.json()["sensor_code"] == "SNR-01"
    assert res_mgr.json()["controller_id"] == str(ctrl.id)
    assert res_mgr.json()["sensor_type"] == "WATER_LEVEL"

    res_admin = client.post("/api/v1/sensors", json={"controller_id": str(ctrl.id), "name": "Turbidity Sensor 2", "sensor_code": "SNR-02", "sensor_type": "TURBIDITY"}, headers={"Authorization": f"Bearer {org_admin_token}"})
    assert res_admin.status_code == 201

    res_super = client.post("/api/v1/sensors", json={"controller_id": str(ctrl.id), "name": "Flow Sensor 3", "sensor_code": "SNR-03", "sensor_type": "FLOW"}, headers={"Authorization": f"Bearer {super_token}"})
    assert res_super.status_code == 201

def test_create_sensor_foreign_controller_isolation(client: TestClient):
    org1 = helper_create_org("SNR-LOCK-01", "Snr Lock Org 1")
    site1 = helper_create_site(org1.id, "SITE-SLOCK-01", "Site SLock 1")
    stn1 = helper_create_station(site1.id, "STN-SLOCK-01", "Stn SLock 1")
    ctrl1 = helper_create_controller(stn1.id, "CTRL-SLOCK-01", "UID-SLOCK-01")

    org2 = helper_create_org("SNR-LOCK-02", "Snr Lock Org 2")
    site2 = helper_create_site(org2.id, "SITE-SLOCK-02", "Site SLock 2")
    stn2 = helper_create_station(site2.id, "STN-SLOCK-02", "Stn SLock 2")
    ctrl2 = helper_create_controller(stn2.id, "CTRL-SLOCK-02", "UID-SLOCK-02")

    _, user1_token = helper_create_user("user1.snrlock@example.com", UserRole.ORGANIZATION_ADMIN, org1.id)

    # User 1 from Org 1 attempts to create sensor under Controller 2 (Org 2) -> 404 Not Found
    payload = {
        "controller_id": str(ctrl2.id),
        "name": "Tampered Sensor",
        "sensor_code": "TAMP-SNR-01"
    }
    res = client.post("/api/v1/sensors", json=payload, headers={"Authorization": f"Bearer {user1_token}"})
    assert res.status_code == 404
    assert res.json()["detail"] == "Controller not found"

def test_create_sensor_duplicate_code(client: TestClient):
    org = helper_create_org("DUP-SNR-ORG", "Dup Snr Org")
    site = helper_create_site(org.id, "DUP-SNR-SITE", "Dup Snr Site")
    stn = helper_create_station(site.id, "DUP-SNR-STN", "Dup Snr Station")
    ctrl = helper_create_controller(stn.id, "DUP-SNR-CTRL", "UID-DUP-SNR-01")
    _, token = helper_create_user("admin.dupsnr@example.com", UserRole.ORGANIZATION_ADMIN, org.id)

    payload = {"controller_id": str(ctrl.id), "name": "Sensor One", "sensor_code": "DUP-SNR-01"}
    res1 = client.post("/api/v1/sensors", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert res1.status_code == 201

    # Duplicate code in same controller -> 409
    res2 = client.post("/api/v1/sensors", json={"controller_id": str(ctrl.id), "name": "Sensor Two", "sensor_code": "dup-snr-01"}, headers={"Authorization": f"Bearer {token}"})
    assert res2.status_code == 409
    assert "already exists in this controller" in res2.json()["detail"]

# ============================================================================
# 2. LIST SENSORS (GET /sensors) & TENANT/CONTROLLER ISOLATION
# ============================================================================

def test_list_sensors_tenant_isolation(client: TestClient):
    org_a = helper_create_org("LIST-SNR-A", "List Snr Org A")
    site_a = helper_create_site(org_a.id, "SSA-01", "Snr Site A")
    stn_a = helper_create_station(site_a.id, "SSTNA-01", "Snr Stn A")
    ctrl_a = helper_create_controller(stn_a.id, "SCTRLA-01", "UID-SNR-A1")

    org_b = helper_create_org("LIST-SNR-B", "List Snr Org B")
    site_b = helper_create_site(org_b.id, "SSB-01", "Snr Site B")
    stn_b = helper_create_station(site_b.id, "SSTNB-01", "Snr Stn B")
    ctrl_b = helper_create_controller(stn_b.id, "SCTRLB-01", "UID-SNR-B1")

    _, super_token = helper_create_user("super.listsnr@example.com", UserRole.SUPER_ADMIN, org_a.id)
    _, admin_a_token = helper_create_user("admin.listsnra@example.com", UserRole.ORGANIZATION_ADMIN, org_a.id)

    client.post("/api/v1/sensors", json={"controller_id": str(ctrl_a.id), "name": "Sensor A1", "sensor_code": "SA1"}, headers={"Authorization": f"Bearer {super_token}"})
    client.post("/api/v1/sensors", json={"controller_id": str(ctrl_b.id), "name": "Sensor B1", "sensor_code": "SB1"}, headers={"Authorization": f"Bearer {super_token}"})

    # User A lists sensors -> receives ONLY Sensor A1
    res_a = client.get("/api/v1/sensors", headers={"Authorization": f"Bearer {admin_a_token}"})
    assert res_a.status_code == 200
    codes_a = [s["sensor_code"] for s in res_a.json()]
    assert "SA1" in codes_a
    assert "SB1" not in codes_a

    # User A filters by foreign controller_id -> empty list
    res_a_foreign = client.get(f"/api/v1/sensors?controller_id={ctrl_b.id}", headers={"Authorization": f"Bearer {admin_a_token}"})
    assert res_a_foreign.status_code == 200
    assert res_a_foreign.json() == []

# ============================================================================
# 3. RETRIEVE SENSOR (GET /sensors/{id}) & IDOR / SITE LIFECYCLE CHECKS
# ============================================================================

def test_get_sensor_idor_protection(client: TestClient):
    org_a = helper_create_org("GET-SNR-A", "Get Snr Org A")
    site_a = helper_create_site(org_a.id, "GSSA-01", "Get Snr Site A")
    stn_a = helper_create_station(site_a.id, "GSSTNA-01", "Get Snr Stn A")
    ctrl_a = helper_create_controller(stn_a.id, "GSCTRLA-01", "UID-GSNR-A1")

    org_b = helper_create_org("GET-SNR-B", "Get Snr Org B")
    site_b = helper_create_site(org_b.id, "GSSB-01", "Get Snr Site B")
    stn_b = helper_create_station(site_b.id, "GSSTNB-01", "Get Snr Stn B")
    ctrl_b = helper_create_controller(stn_b.id, "GSCTRLB-01", "UID-GSNR-B1")

    _, super_token = helper_create_user("super.getsnr@example.com", UserRole.SUPER_ADMIN, org_a.id)
    _, admin_a_token = helper_create_user("admin.getsnra@example.com", UserRole.ORGANIZATION_ADMIN, org_a.id)

    res_b = client.post("/api/v1/sensors", json={"controller_id": str(ctrl_b.id), "name": "Private Snr B", "sensor_code": "PRSB"}, headers={"Authorization": f"Bearer {super_token}"})
    snr_b_id = uuid.UUID(res_b.json()["id"])

    # Admin A attempts IDOR access to Org B sensor -> 404 Not Found
    res_idor = client.get(f"/api/v1/sensors/{snr_b_id}", headers={"Authorization": f"Bearer {admin_a_token}"})
    assert res_idor.status_code == 404
    assert res_idor.json()["detail"] == "Sensor not found"

def test_get_sensor_parent_site_operational_status(client: TestClient):
    org = helper_create_org("SNR-STAT-ORG", "Snr Stat Org")
    site = helper_create_site(org.id, "INACT-SSITE", "Active Site Initially", status=SiteStatus.ACTIVE)
    stn = helper_create_station(site.id, "INACT-SSTN", "Parent Station")
    ctrl = helper_create_controller(stn.id, "INACT-SCTRL", "UID-INACT-S01")

    _, super_token = helper_create_user("super.snrstat@example.com", UserRole.SUPER_ADMIN, org.id)
    _, operator_token = helper_create_user("operator.snrstat@example.com", UserRole.STATION_OPERATOR, org.id)

    res_snr = client.post("/api/v1/sensors", json={"controller_id": str(ctrl.id), "name": "Inactive Parent Sensor", "sensor_code": "INACT-SNR"}, headers={"Authorization": f"Bearer {super_token}"})
    snr_id = uuid.UUID(res_snr.json()["id"])

    # Update site to INACTIVE directly in DB
    with get_sync_session() as session:
        db_site = session.get(Site, site.id)
        db_site.status = SiteStatus.INACTIVE
        session.commit()

    # Access sensor under inactive site -> 403 Forbidden
    res = client.get(f"/api/v1/sensors/{snr_id}", headers={"Authorization": f"Bearer {operator_token}"})
    assert res.status_code == 403
    assert "Site is inactive" in res.json()["detail"]

# ============================================================================
# 4. UPDATE SENSOR (PUT/PATCH /sensors/{id})
# ============================================================================

def test_update_sensor(client: TestClient):
    org = helper_create_org("UPD-SNR-ORG", "Upd Snr Org")
    site = helper_create_site(org.id, "UPD-SNR-SITE", "Upd Snr Site")
    stn = helper_create_station(site.id, "UPD-SNR-STN", "Upd Snr Stn")
    ctrl = helper_create_controller(stn.id, "UPD-SNR-CTRL", "UID-UPD-SNR")

    _, super_token = helper_create_user("super.updsnr@example.com", UserRole.SUPER_ADMIN, org.id)
    _, admin_token = helper_create_user("admin.updsnr@example.com", UserRole.ORGANIZATION_ADMIN, org.id)
    _, viewer_token = helper_create_user("viewer.updsnr@example.com", UserRole.VIEWER, org.id)

    res = client.post("/api/v1/sensors", json={"controller_id": str(ctrl.id), "name": "Old Sensor Name", "sensor_code": "OLD-SNR", "sensor_type": "WATER_LEVEL"}, headers={"Authorization": f"Bearer {super_token}"})
    snr_id = uuid.UUID(res.json()["id"])

    # Viewer cannot update -> 403 Forbidden
    assert client.patch(f"/api/v1/sensors/{snr_id}", json={"name": "Hacked Name"}, headers={"Authorization": f"Bearer {viewer_token}"}).status_code == 403

    # Org Admin update -> 200 OK
    res_upd = client.put(f"/api/v1/sensors/{snr_id}", json={"name": "New Sensor Name", "sensor_code": "NEW-SNR", "sensor_type": "PRESSURE", "description": "Updated pressure sensor"}, headers={"Authorization": f"Bearer {admin_token}"})
    assert res_upd.status_code == 200
    assert res_upd.json()["name"] == "New Sensor Name"
    assert res_upd.json()["sensor_code"] == "NEW-SNR"
    assert res_upd.json()["sensor_type"] == "PRESSURE"
    assert res_upd.json()["description"] == "Updated pressure sensor"

# ============================================================================
# 5. DELETE SENSOR (DELETE /sensors/{id}) & RESTRICT CHECKS
# ============================================================================

def test_delete_sensor_success(client: TestClient):
    org = helper_create_org("DEL-SNR-ORG", "Del Snr Org")
    site = helper_create_site(org.id, "DEL-SNR-SITE", "Del Snr Site")
    stn = helper_create_station(site.id, "DEL-SNR-STN", "Del Snr Stn")
    ctrl = helper_create_controller(stn.id, "DEL-SNR-CTRL", "UID-DEL-SNR-01")

    _, super_token = helper_create_user("super.delsnr@example.com", UserRole.SUPER_ADMIN, org.id)
    _, admin_token = helper_create_user("admin.delsnr@example.com", UserRole.ORGANIZATION_ADMIN, org.id)

    res = client.post("/api/v1/sensors", json={"controller_id": str(ctrl.id), "name": "Sensor To Delete", "sensor_code": "DEL-SNR-01"}, headers={"Authorization": f"Bearer {super_token}"})
    snr_id = uuid.UUID(res.json()["id"])

    res_del = client.delete(f"/api/v1/sensors/{snr_id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert res_del.status_code == 204

    res_get = client.get(f"/api/v1/sensors/{snr_id}", headers={"Authorization": f"Bearer {super_token}"})
    assert res_get.status_code == 404

def test_delete_sensor_with_dependent_telemetry_fails(client: TestClient):
    org = helper_create_org("TLM-SNR-ORG", "Tlm Snr Org")
    site = helper_create_site(org.id, "TLM-SNR-SITE", "Tlm Snr Site")
    stn = helper_create_station(site.id, "TLM-SNR-STN", "Tlm Snr Stn")
    ctrl = helper_create_controller(stn.id, "TLM-SNR-CTRL", "UID-TLM-SNR")

    _, super_token = helper_create_user("super.tlmsnr@example.com", UserRole.SUPER_ADMIN, org.id)

    res_snr = client.post("/api/v1/sensors", json={"controller_id": str(ctrl.id), "name": "Sensor With Telemetry", "sensor_code": "TLM-SNR-01"}, headers={"Authorization": f"Bearer {super_token}"})
    snr_id = uuid.UUID(res_snr.json()["id"])

    # Attach dependent telemetry reading in DB
    with get_sync_session() as session:
        reading = TelemetryReading(
            id=uuid.uuid4(),
            sensor_id=snr_id,
            value=42.5,
            unit="cm",
            occurred_at=datetime.now(timezone.utc)
        )
        session.add(reading)
        session.commit()

    # Delete sensor fails with 400 Bad Request
    res_del = client.delete(f"/api/v1/sensors/{snr_id}", headers={"Authorization": f"Bearer {super_token}"})
    assert res_del.status_code == 400
    assert "Cannot delete sensor with active telemetry readings" in res_del.json()["detail"]
