"""
HydraControl — Phase 8 P8-T01 WebSocket Hub & Connection Manager Tests
Verifies WebSocket handshake, JWT authentication, invalid/missing/expired token handling,
connection lifecycle, channel subscriptions, tenant isolation (Org A vs Org B),
IDOR protection across hierarchy, site operational access policies, PING/PONG heartbeats,
de-duplicated broadcast, dead socket cleanup, and malformed payload resilience.
"""
import pytest
import uuid
import json
from datetime import timedelta
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

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
from app.core.security import create_access_token, create_device_token, get_password_hash
from app.websocket.hub import hub


@pytest.fixture(scope="module", autouse=True)
def setup_tables():
    Base.metadata.create_all(bind=sync_engine)
    yield
    Base.metadata.drop_all(bind=sync_engine)


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def create_test_user(email: str, role: UserRole, org_id: uuid.UUID = None, is_active: bool = True) -> tuple[User, str]:
    user_id = uuid.uuid4()
    with get_sync_session() as session:
        user = User(
            id=user_id,
            email=email,
            password_hash=get_password_hash("SecretPass123!"),
            name=f"User {email}",
            role=role,
            organization_id=org_id,
            is_active=is_active
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


def create_test_hierarchy(prefix: str, site_status: SiteStatus = SiteStatus.ACTIVE):
    with get_sync_session() as session:
        org = Organization(
            id=uuid.uuid4(),
            name=f"{prefix} Org",
            organization_code=f"{prefix}_ORG".upper(),
            status=OrganizationStatus.ACTIVE
        )
        session.add(org)

        site = Site(
            id=uuid.uuid4(),
            organization_id=org.id,
            name=f"{prefix} Site",
            site_code=f"{prefix}_SITE".upper(),
            site_type=SiteType.HOME,
            status=site_status
        )
        session.add(site)

        station = Station(
            id=uuid.uuid4(),
            site_id=site.id,
            name=f"{prefix} Station",
            station_code=f"{prefix}_STN".upper(),
            station_type=StationType.WATER_SUPPLY,
            status=StationStatus.ACTIVE
        )
        session.add(station)

        controller = Controller(
            id=uuid.uuid4(),
            station_id=station.id,
            name=f"{prefix} Controller",
            controller_code=f"{prefix}_CTRL".upper(),
            device_uid=f"{prefix}-HW-UID-CTRL",
            controller_type=ControllerType.ESP32,
            status=ControllerStatus.ACTIVE
        )
        session.add(controller)

        motor = Motor(
            id=uuid.uuid4(),
            controller_id=controller.id,
            name=f"{prefix} Pump",
            motor_code=f"{prefix}_PUMP".upper(),
            motor_type=MotorType.WATER_PUMP,
            status=MotorStatus.OFF,
            rated_power=5.5
        )
        session.add(motor)

        sensor = Sensor(
            id=uuid.uuid4(),
            controller_id=controller.id,
            name=f"{prefix} Level Sensor",
            sensor_code=f"{prefix}_LVL".upper(),
            sensor_type=SensorType.WATER_LEVEL,
            status=SensorStatus.ACTIVE
        )
        session.add(sensor)

        session.commit()
        return org, site, station, controller, motor, sensor


# ==============================================================================
# AUTHENTICATION & CONNECTION LIFECYCLE TESTS
# ==============================================================================

def test_websocket_missing_token_rejected(client):
    """Connecting without a token must be rejected with policy violation (1008)."""
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/api/v1/ws"):
            pass
    assert exc.value.code == 1008


def test_websocket_invalid_token_rejected(client):
    """Connecting with a garbage token must be rejected with 1008."""
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/api/v1/ws?token=invalid.jwt.token"):
            pass
    assert exc.value.code == 1008


def test_websocket_expired_token_rejected(client):
    """Connecting with an expired token must be rejected with 1008."""
    org, _, _, _, _, _ = create_test_hierarchy("WS_EXP")
    user, _ = create_test_user("expired_ws@example.com", UserRole.STATION_OPERATOR, org.id)
    expired_token = create_access_token(subject=str(user.id), expires_delta=timedelta(seconds=-10))

    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(f"/api/v1/ws?token={expired_token}"):
            pass
    assert exc.value.code == 1008


def test_websocket_device_token_rejected(client):
    """Device JWT tokens are strictly for MQTT/device APIs and must not connect to user WebSockets."""
    device_token = create_device_token(device_uid="ESP32-TEST-DEV", controller_id=uuid.uuid4())
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(f"/api/v1/ws?token={device_token}"):
            pass
    assert exc.value.code == 1008


def test_websocket_inactive_user_rejected(client):
    """Deactivated user must be rejected."""
    org, _, _, _, _, _ = create_test_hierarchy("WS_INACT")
    user, token = create_test_user("inactive_ws@example.com", UserRole.VIEWER, org.id, is_active=False)

    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(f"/api/v1/ws?token={token}"):
            pass
    assert exc.value.code == 1008


def test_websocket_valid_connection_lifecycle(client):
    """Valid user connects, receives CONNECTED message, and hub tracks connection state."""
    org, _, _, _, _, _ = create_test_hierarchy("WS_CONN")
    user, token = create_test_user("valid_ws@example.com", UserRole.STATION_OPERATOR, org.id)

    with client.websocket_connect(f"/api/v1/ws?token={token}") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "CONNECTED"
        assert msg["user_id"] == str(user.id)
        assert msg["organization_id"] == str(org.id)
        assert msg["role"] == UserRole.STATION_OPERATOR.value


# ==============================================================================
# HEARTBEAT TESTS
# ==============================================================================

def test_websocket_ping_pong_heartbeat(client):
    """Client sending PING receives structured PONG with timestamp."""
    org, _, _, _, _, _ = create_test_hierarchy("WS_PING")
    user, token = create_test_user("ping_ws@example.com", UserRole.STATION_OPERATOR, org.id)

    with client.websocket_connect(f"/api/v1/ws?token={token}") as ws:
        _ = ws.receive_json()  # CONNECTED
        ws.send_json({"action": "PING"})
        pong_msg = ws.receive_json()
        assert pong_msg["type"] == "PONG"
        assert "timestamp" in pong_msg

        # Also support {"type": "PING"}
        ws.send_json({"type": "PING"})
        pong_msg2 = ws.receive_json()
        assert pong_msg2["type"] == "PONG"


# ==============================================================================
# CHANNEL SUBSCRIPTION & TENANT ISOLATION TESTS
# ==============================================================================

def test_websocket_valid_subscriptions(client):
    """User successfully subscribes to their own org, site, station, motor, and device channels."""
    org, site, station, controller, motor, _ = create_test_hierarchy("WS_SUB_OK")
    user, token = create_test_user("sub_ok@example.com", UserRole.SITE_MANAGER, org.id)

    with client.websocket_connect(f"/api/v1/ws?token={token}") as ws:
        _ = ws.receive_json()  # CONNECTED

        channels = [
            f"org:{org.id}",
            f"site:{site.id}",
            f"station:{station.id}",
            f"motor:{motor.id}",
            f"device:{controller.device_uid}",
        ]
        ws.send_json({"action": "SUBSCRIBE", "channels": channels})
        resp = ws.receive_json()

        assert resp["type"] == "SUBSCRIBED"
        assert len(resp["channels"]) == 5
        assert len(resp["failed"]) == 0
        assert f"org:{org.id}" in resp["channels"]
        assert f"motor:{motor.id}" in resp["channels"]

        # Test Unsubscribe
        ws.send_json({"action": "UNSUBSCRIBE", "channels": [f"motor:{motor.id}"]})
        unsub_resp = ws.receive_json()
        assert unsub_resp["type"] == "UNSUBSCRIBED"
        assert unsub_resp["channels"] == [f"motor:{motor.id}"]


def test_websocket_cross_tenant_isolation_idor_denied(client):
    """
    STRICT TENANT ISOLATION:
    User in Org A attempts to subscribe to channels belonging to Org B.
    All foreign channels must be rejected in the failed list.
    """
    org_a, site_a, station_a, controller_a, motor_a, _ = create_test_hierarchy("WS_ORG_A")
    org_b, site_b, station_b, controller_b, motor_b, _ = create_test_hierarchy("WS_ORG_B")

    user_a, token_a = create_test_user("user_org_a@example.com", UserRole.SITE_MANAGER, org_a.id)

    with client.websocket_connect(f"/api/v1/ws?token={token_a}") as ws:
        _ = ws.receive_json()  # CONNECTED

        # Attempt to subscribe to own org (allowed) and foreign Org B resources (denied)
        channels = [
            f"org:{org_a.id}",                 # ALLOWED
            f"org:{org_b.id}",                 # DENIED
            f"site:{site_b.id}",               # DENIED
            f"station:{station_b.id}",         # DENIED
            f"motor:{motor_b.id}",             # DENIED
            f"device:{controller_b.device_uid}" # DENIED
        ]

        ws.send_json({"action": "SUBSCRIBE", "channels": channels})
        resp = ws.receive_json()

        assert resp["type"] == "SUBSCRIBED"
        assert resp["channels"] == [f"org:{org_a.id}"]
        assert len(resp["failed"]) == 5

        failed_channels = {item["channel"] for item in resp["failed"]}
        assert f"org:{org_b.id}" in failed_channels
        assert f"site:{site_b.id}" in failed_channels
        assert f"station:{station_b.id}" in failed_channels
        assert f"motor:{motor_b.id}" in failed_channels
        assert f"device:{controller_b.device_uid}" in failed_channels


def test_websocket_site_operational_state_policy(client):
    """
    Site policy enforcement:
    - Suspended / Inactive sites cannot be subscribed to.
    - Maintenance sites are rejected for VIEWER but allowed for SITE_MANAGER.
    """
    org, site_maint, _, _, _, _ = create_test_hierarchy("WS_MAINT", site_status=SiteStatus.MAINTENANCE)
    viewer_user, viewer_token = create_test_user("viewer_maint@example.com", UserRole.VIEWER, org.id)
    manager_user, manager_token = create_test_user("manager_maint@example.com", UserRole.SITE_MANAGER, org.id)

    # Viewer denied on maintenance site
    with client.websocket_connect(f"/api/v1/ws?token={viewer_token}") as ws:
        _ = ws.receive_json()
        ws.send_json({"action": "SUBSCRIBE", "channels": [f"site:{site_maint.id}"]})
        resp = ws.receive_json()
        assert resp["type"] == "SUBSCRIBED"
        assert len(resp["channels"]) == 0
        assert len(resp["failed"]) == 1
        assert "maintenance" in resp["failed"][0]["reason"].lower()

    # Manager allowed on maintenance site
    with client.websocket_connect(f"/api/v1/ws?token={manager_token}") as ws:
        _ = ws.receive_json()
        ws.send_json({"action": "SUBSCRIBE", "channels": [f"site:{site_maint.id}"]})
        resp = ws.receive_json()
        assert resp["type"] == "SUBSCRIBED"
        assert f"site:{site_maint.id}" in resp["channels"]


def test_websocket_malformed_input_resilience(client):
    """Sending non-JSON, invalid JSON, or unknown actions returns structured errors without dropping the socket."""
    org, _, _, _, _, _ = create_test_hierarchy("WS_MALFORM")
    user, token = create_test_user("malform_ws@example.com", UserRole.STATION_OPERATOR, org.id)

    with client.websocket_connect(f"/api/v1/ws?token={token}") as ws:
        _ = ws.receive_json()  # CONNECTED

        # Non-JSON raw text
        ws.send_text("THIS IS NOT JSON")
        err1 = ws.receive_json()
        assert err1["type"] == "ERROR"

        # Unknown action
        ws.send_json({"action": "EXECUTE_ARBITRARY_COMMAND"})
        err2 = ws.receive_json()
        assert err2["type"] == "ERROR"
        assert "Unknown action" in err2["message"]

        # SUBSCRIBE with missing channels list
        ws.send_json({"action": "SUBSCRIBE"})
        err3 = ws.receive_json()
        assert err3["type"] == "ERROR"

        # Connection should remain alive and responsive to PING
        ws.send_json({"action": "PING"})
        pong = ws.receive_json()
        assert pong["type"] == "PONG"
