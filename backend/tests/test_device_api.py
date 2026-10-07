import pytest
import uuid
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from app.main import app
from app.db.base import Base
from app.db.session import sync_engine, get_sync_session
from app.models.user import User, UserRole
from app.models.organization import Organization, OrganizationStatus
from app.models.site import Site, SiteStatus, SiteType
from app.models.station import Station, StationStatus, StationType
from app.models.controller import Controller, ControllerStatus, ControllerType
from app.core.security import create_access_token, create_device_token, decode_access_token, get_password_hash
from app.schemas.device import LivenessState


@pytest.fixture(scope="module", autouse=True)
def setup_tables():
    """Create database tables for Device API tests and drop after."""
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
            station_type=StationType.WATER_SUPPLY,
            status=StationStatus.ACTIVE
        )
        session.add(station)
        session.commit()
        session.refresh(station)
    return station


def helper_create_controller(
    station_id: uuid.UUID,
    code: str,
    device_uid: str,
    name: str = "ESP32 Controller",
    status: ControllerStatus = ControllerStatus.ACTIVE,
    last_seen_at: datetime = None
) -> Controller:
    controller_id = uuid.uuid4()
    with get_sync_session() as session:
        controller = Controller(
            id=controller_id,
            station_id=station_id,
            name=name,
            controller_code=code,
            device_uid=device_uid,
            controller_type=ControllerType.ESP32,
            status=status,
            last_seen_at=last_seen_at
        )
        session.add(controller)
        session.commit()
        session.refresh(controller)
    return controller


def helper_create_user(email: str, role: UserRole, org_id: uuid.UUID = None) -> tuple[User, str]:
    user_id = uuid.uuid4()
    with get_sync_session() as session:
        user = User(
            id=user_id,
            email=email,
            password_hash=get_password_hash("SecretPass123!"),
            name=f"User {email}",
            role=role,
            organization_id=org_id,
            is_active=True
        )
        session.add(user)
        session.commit()
        session.refresh(user)

    token = create_access_token(
        subject=str(user.id),
        extra_claims={
            "role": user.role.value,
            "organization_id": str(user.organization_id) if user.organization_id else None
        }
    )
    return user, token


# =========================================================================
# P4-T01: DEVICE REGISTRATION ENDPOINT TESTS
# =========================================================================

def test_device_registration_happy_path(client: TestClient):
    org = helper_create_org("DEV_REG_ORG", "Dev Reg Org")
    site = helper_create_site(org.id, "SITE_REG", "Site Reg")
    station = helper_create_station(site.id, "STN_REG", "Station Reg")
    controller = helper_create_controller(station.id, "CTRL_REG_1", "ESP32-HW-001", status=ControllerStatus.INACTIVE)

    payload = {
        "device_uid": "ESP32-HW-001",
        "firmware_version": "v1.2.0",
        "ip_address": "192.168.1.150",
        "mac_address": "AA:BB:CC:DD:EE:01",
        "controller_type": "ESP32"
    }

    res = client.post("/api/v1/devices/register", json=payload)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["controller_id"] == str(controller.id)
    assert data["station_id"] == str(station.id)
    assert data["device_uid"] == "ESP32-HW-001"
    assert data["status"] == "ACTIVE"
    assert "device_token" in data
    assert data["mqtt_topic_prefix"] == "hydracontrol/devices/ESP32-HW-001"
    assert data["server_time"] is not None

    # Verify device token is valid JWT
    claims = decode_access_token(data["device_token"])
    assert claims["type"] == "device"
    assert claims["sub"] == "ESP32-HW-001"
    assert claims["controller_id"] == str(controller.id)


def test_device_registration_unprovisioned_uid_returns_404(client: TestClient):
    payload = {
        "device_uid": "NON-EXISTENT-UID",
        "firmware_version": "v1.0.0"
    }
    res = client.post("/api/v1/devices/register", json=payload)
    assert res.status_code == 404
    assert "not provisioned" in res.json()["detail"].lower()


def test_device_registration_suspended_site_returns_403(client: TestClient):
    org = helper_create_org("SUSP_SITE_ORG", "Suspended Site Org")
    site = helper_create_site(org.id, "SITE_SUSP", "Site Susp", status=SiteStatus.SUSPENDED)
    station = helper_create_station(site.id, "STN_SUSP", "Station Susp")
    helper_create_controller(station.id, "CTRL_SUSP", "ESP32-SUSP-001")

    payload = {
        "device_uid": "ESP32-SUSP-001",
        "firmware_version": "v1.0.0"
    }
    res = client.post("/api/v1/devices/register", json=payload)
    assert res.status_code == 403
    assert "suspended" in res.json()["detail"].lower()


def test_device_registration_decommissioned_returns_400(client: TestClient):
    org = helper_create_org("DECOM_ORG", "Decom Org")
    site = helper_create_site(org.id, "SITE_DECOM", "Site Decom")
    station = helper_create_station(site.id, "STN_DECOM", "Station Decom")
    helper_create_controller(station.id, "CTRL_DECOM", "ESP32-DECOM-001", status=ControllerStatus.DECOMMISSIONED)

    payload = {
        "device_uid": "ESP32-DECOM-001",
        "firmware_version": "v1.0.0"
    }
    res = client.post("/api/v1/devices/register", json=payload)
    assert res.status_code == 400
    assert "decommissioned" in res.json()["detail"].lower()


# =========================================================================
# P4-T02: DEVICE HEARTBEAT & LIVENESS TESTS
# =========================================================================

def test_device_heartbeat_happy_path(client: TestClient):
    org = helper_create_org("HB_ORG", "Heartbeat Org")
    site = helper_create_site(org.id, "SITE_HB", "Site HB")
    station = helper_create_station(site.id, "STN_HB", "Station HB")
    controller = helper_create_controller(station.id, "CTRL_HB", "ESP32-HB-001", status=ControllerStatus.OFFLINE)

    payload = {
        "device_uid": "ESP32-HB-001",
        "firmware_version": "v1.2.1",
        "ip_address": "192.168.1.155",
        "uptime_seconds": 3600,
        "free_heap": 184000,
        "rssi": -65
    }

    res = client.post("/api/v1/devices/heartbeat", json=payload)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["device_uid"] == "ESP32-HB-001"
    assert data["status"] == "ACTIVE"  # Transitioned from OFFLINE to ACTIVE
    assert data["acknowledged"] is True
    assert data["commands_pending"] == 0
    assert "server_time" in data


def test_device_heartbeat_with_matching_device_token(client: TestClient):
    org = helper_create_org("HB_AUTH_ORG", "Heartbeat Auth Org")
    site = helper_create_site(org.id, "SITE_HB_AUTH", "Site HB Auth")
    station = helper_create_station(site.id, "STN_HB_AUTH", "Station HB Auth")
    controller = helper_create_controller(station.id, "CTRL_HB_AUTH", "ESP32-HBAUTH-001")

    dev_token = create_device_token(device_uid="ESP32-HBAUTH-001", controller_id=controller.id)

    payload = {
        "device_uid": "ESP32-HBAUTH-001",
        "uptime_seconds": 120
    }

    res = client.post(
        "/api/v1/devices/heartbeat",
        json=payload,
        headers={"Authorization": f"Bearer {dev_token}"}
    )
    assert res.status_code == 200
    assert res.json()["acknowledged"] is True


def test_device_heartbeat_with_mismatched_device_token_returns_403(client: TestClient):
    org = helper_create_org("HB_MIS_ORG", "Heartbeat Mismatch Org")
    site = helper_create_site(org.id, "SITE_HB_MIS", "Site HB Mismatch")
    station = helper_create_station(site.id, "STN_HB_MIS", "Station HB Mismatch")
    controller = helper_create_controller(station.id, "CTRL_HB_MIS", "ESP32-MIS-001")

    # Generate token for a different device UID
    fake_token = create_device_token(device_uid="DIFFERENT-DEVICE-UID", controller_id=controller.id)

    payload = {
        "device_uid": "ESP32-MIS-001",
        "uptime_seconds": 120
    }

    res = client.post(
        "/api/v1/devices/heartbeat",
        json=payload,
        headers={"Authorization": f"Bearer {fake_token}"}
    )
    assert res.status_code == 403
    assert "does not match" in res.json()["detail"].lower()


def test_device_heartbeat_unprovisioned_returns_404(client: TestClient):
    payload = {
        "device_uid": "UNPROVISIONED-HB",
        "uptime_seconds": 50
    }
    res = client.post("/api/v1/devices/heartbeat", json=payload)
    assert res.status_code == 404


def test_device_liveness_status_endpoint_and_states(client: TestClient):
    org = helper_create_org("LIVE_ORG", "Liveness Org")
    site = helper_create_site(org.id, "SITE_LIVE", "Site Live")
    station = helper_create_station(site.id, "STN_LIVE", "Station Live")

    now = datetime.now(timezone.utc)

    # 1. Online controller (seen 10s ago)
    c_online = helper_create_controller(
        station.id, "CTRL_ONLINE", "ESP32-ONLINE-01",
        last_seen_at=now - timedelta(seconds=10)
    )

    # 2. Stale controller (seen 90s ago; stale_threshold=60, offline_threshold=180)
    c_stale = helper_create_controller(
        station.id, "CTRL_STALE", "ESP32-STALE-01",
        last_seen_at=now - timedelta(seconds=90)
    )

    # 3. Offline controller (seen 300s ago)
    c_offline = helper_create_controller(
        station.id, "CTRL_OFFLINE", "ESP32-OFFLINE-01",
        last_seen_at=now - timedelta(seconds=300)
    )

    _, token = helper_create_user("live_admin@example.com", UserRole.ORGANIZATION_ADMIN, org.id)
    headers = {"Authorization": f"Bearer {token}"}

    # Verify ONLINE state
    res_on = client.get(f"/api/v1/devices/{c_online.device_uid}/status", headers=headers)
    assert res_on.status_code == 200
    assert res_on.json()["liveness_state"] == "ONLINE"
    assert res_on.json()["seconds_since_last_seen"] < 30

    # Verify STALE state
    res_st = client.get(f"/api/v1/devices/{c_stale.device_uid}/status", headers=headers)
    assert res_st.status_code == 200
    assert res_st.json()["liveness_state"] == "STALE"

    # Verify OFFLINE state
    res_off = client.get(f"/api/v1/devices/{c_offline.device_uid}/status", headers=headers)
    assert res_off.status_code == 200
    assert res_off.json()["liveness_state"] == "OFFLINE"


def test_device_status_organization_isolation(client: TestClient):
    org_a = helper_create_org("ISOL_ORG_A", "Isol Org A")
    site_a = helper_create_site(org_a.id, "SITE_ISOL_A", "Site Isol A")
    stn_a = helper_create_station(site_a.id, "STN_ISOL_A", "Station Isol A")
    c_a = helper_create_controller(stn_a.id, "CTRL_ISOL_A", "ESP32-ISOL-A")

    org_b = helper_create_org("ISOL_ORG_B", "Isol Org B")
    _, token_b = helper_create_user("user_b@example.com", UserRole.ORGANIZATION_ADMIN, org_b.id)
    _, super_token = helper_create_user("super_admin_live@example.com", UserRole.SUPER_ADMIN, None)

    # Org B user querying Org A device gets 404 (IDOR protection)
    res_b = client.get(f"/api/v1/devices/{c_a.device_uid}/status", headers={"Authorization": f"Bearer {token_b}"})
    assert res_b.status_code == 404

    # Super admin querying Org A device gets 200
    res_super = client.get(f"/api/v1/devices/{c_a.device_uid}/status", headers={"Authorization": f"Bearer {super_token}"})
    assert res_super.status_code == 200
    assert res_super.json()["device_uid"] == c_a.device_uid


def test_trigger_liveness_sync_endpoint(client: TestClient):
    org = helper_create_org("SYNC_LIVE_ORG", "Sync Live Org")
    site = helper_create_site(org.id, "SITE_SYNC", "Site Sync")
    station = helper_create_station(site.id, "STN_SYNC", "Station Sync")

    # Create active controller seen 500s ago
    now = datetime.now(timezone.utc)
    c_inactive = helper_create_controller(
        station.id, "CTRL_SYNC_OFF", "ESP32-SYNC-OFF-01",
        status=ControllerStatus.ACTIVE,
        last_seen_at=now - timedelta(seconds=500)
    )

    _, admin_token = helper_create_user("sync_admin@example.com", UserRole.SUPER_ADMIN, None)
    _, viewer_token = helper_create_user("sync_viewer@example.com", UserRole.VIEWER, org.id)

    # Viewer cannot trigger liveness sync (403)
    res_viewer = client.post("/api/v1/devices/liveness-check", headers={"Authorization": f"Bearer {viewer_token}"})
    assert res_viewer.status_code == 403

    # Admin triggers liveness check
    res_admin = client.post("/api/v1/devices/liveness-check", headers={"Authorization": f"Bearer {admin_token}"})
    assert res_admin.status_code == 200
    data = res_admin.json()
    assert data["total_checked"] > 0
    assert data["offline_count"] > 0

    # Verify controller in DB was transitioned to OFFLINE
    with get_sync_session() as session:
        refreshed = session.get(Controller, c_inactive.id)
        assert refreshed.status == ControllerStatus.OFFLINE
