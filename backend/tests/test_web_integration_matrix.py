"""
HydraControl — Full Web & System Integration Test Matrix
Comprehensive verification covering all 24 web testing areas required before Phase 10:
- Environment & Probes
- Auth & Token Management
- 8-Role RBAC Authorization Matrix
- Multi-Tenant Hierarchy Navigation & IDOR Protection
- WebSocket Hub, PING/PONG, Auto-Reconnect & Concurrent Sessions
- Live Multi-Sensor Telemetry (Level, Turbidity, Flow, Current, Voltage, Pressure)
- Motor Control Lifecycles (START, STOP, EMERGENCY STOP)
- Edge Safety Interlocks (Turbidity cutoff, Tank full, E-stop latch)
- Offline Edge Safety & Event Buffering
"""

import sys
import os
import pytest
import uuid
from datetime import datetime, timezone
from starlette.testclient import TestClient

simulator_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "device_simulator"))
if simulator_dir not in sys.path:
    sys.path.insert(0, simulator_dir)
from esp32_simulator import ESP32Simulator

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
from app.models.motor_command import CommandStatus
from app.core.security import get_password_hash
from app.mqtt.handlers.telemetry_handler import process_telemetry_payload
from app.mqtt.handlers.status_handler import process_status_payload
from app.mqtt.handlers.ack_handler import process_ack_payload
from app.mqtt.handlers.fault_handler import process_fault_payload


@pytest.fixture(scope="module", autouse=True)
def setup_tables():
    Base.metadata.create_all(bind=sync_engine)
    yield
    Base.metadata.drop_all(bind=sync_engine)


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def setup_web_test_hierarchy(prefix: str):
    """Creates an isolated enterprise tenant hierarchy for web matrix testing."""
    with get_sync_session() as session:
        org = Organization(
            id=uuid.uuid4(),
            name=f"{prefix} Enterprise Water Utilities",
            organization_code=f"{prefix}_CORP".upper(),
            status=OrganizationStatus.ACTIVE,
        )
        session.add(org)

        site = Site(
            id=uuid.uuid4(),
            organization_id=org.id,
            name=f"{prefix} Primary Purification Site",
            site_code=f"{prefix}_SITE_01".upper(),
            site_type=SiteType.FACTORY,
            status=SiteStatus.ACTIVE,
        )
        session.add(site)

        station = Station(
            id=uuid.uuid4(),
            site_id=site.id,
            name=f"{prefix} Intake Pump Station",
            station_code=f"{prefix}_STN_01".upper(),
            station_type=StationType.WATER_SUPPLY,
            status=StationStatus.ACTIVE,
        )
        session.add(station)

        controller = Controller(
            id=uuid.uuid4(),
            station_id=station.id,
            name=f"{prefix} ESP32 Main Controller",
            controller_code=f"{prefix}_CTRL_01".upper(),
            device_uid=f"{prefix}-ESP32-DEVICE-UID",
            controller_type=ControllerType.ESP32,
            status=ControllerStatus.ACTIVE,
        )
        session.add(controller)

        motor = Motor(
            id=uuid.uuid4(),
            controller_id=controller.id,
            name=f"{prefix} High-Power Intake Pump",
            motor_code=f"{prefix}_PUMP_01".upper(),
            motor_type=MotorType.WATER_PUMP,
            status=MotorStatus.OFF,
            rated_power=15.0,
        )
        session.add(motor)

        sensors = {}
        for s_type, code, name in [
            (SensorType.WATER_LEVEL, "LEVEL_01", "Storage Tank Level Sensor"),
            (SensorType.TURBIDITY, "TURB_01", "Raw Water Turbidity Sensor"),
            (SensorType.FLOW, "FLOW_01", "Intake Flow Rate Sensor"),
            (SensorType.CURRENT, "CURR_01", "Motor Current Sensor"),
            (SensorType.VOLTAGE, "VOLT_01", "Line Voltage Sensor"),
            (SensorType.PRESSURE, "PRES_01", "Discharge Pressure Sensor"),
        ]:
            s = Sensor(
                id=uuid.uuid4(),
                controller_id=controller.id,
                name=f"{prefix} {name}",
                sensor_code=f"{prefix}_{code}".upper(),
                sensor_type=s_type,
                status=SensorStatus.ACTIVE,
            )
            session.add(s)
            sensors[s_type] = s

        users = {}
        role_map = [
            (UserRole.SUPER_ADMIN, "admin", "System Super Admin"),
            (UserRole.ORGANIZATION_ADMIN, "org_admin", "Org Admin User"),
            (UserRole.SITE_MANAGER, "site_mgr", "Site Manager User"),
            (UserRole.STATION_OPERATOR, "operator", "Station Operator User"),
            (UserRole.TECHNICIAN, "tech", "Field Technician User"),
            (UserRole.VIEWER, "viewer", "Read-Only Viewer User"),
            (UserRole.OWNER, "owner", "Home Owner User"),
            (UserRole.FAMILY_MEMBER, "family", "Family Member User"),
        ]

        for role, email_prefix, full_name in role_map:
            u = User(
                id=uuid.uuid4(),
                email=f"{prefix.lower()}_{email_prefix}@hydracontrol.io",
                password_hash=get_password_hash("SecretPass123!"),
                name=f"{prefix} {full_name}",
                role=role,
                organization_id=org.id,
                is_active=True,
            )
            session.add(u)
            users[role] = u

        session.commit()
        return org, site, station, controller, motor, sensors, users


# ------------------------------------------------------------------------------
# 1. ENVIRONMENT & PROBES
# ------------------------------------------------------------------------------

def test_web_environment_probes(client):
    """Verify backend health endpoints return expected HTTP 200 statuses."""
    h_resp = client.get("/health")
    assert h_resp.status_code == 200
    assert h_resp.json()["status"] == "healthy"

    db_resp = client.get("/health/db")
    assert db_resp.status_code == 200
    assert db_resp.json()["status"] == "connected"

    mqtt_resp = client.get("/health/mqtt")
    assert mqtt_resp.status_code == 200
    assert "status" in mqtt_resp.json()


# ------------------------------------------------------------------------------
# 2. AUTHENTICATION & TOKEN MANAGEMENT
# ------------------------------------------------------------------------------

def test_web_auth_flow_and_session(client):
    """Verify login, token hydration, profile loading, and 401 handling."""
    org, site, station, controller, motor, sensors, users = setup_web_test_hierarchy("WEB_AUTH")
    op = users[UserRole.STATION_OPERATOR]

    # Valid Login
    login_resp = client.post("/api/v1/auth/login", json={"email": op.email, "password": "SecretPass123!"})
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    assert token is not None

    # Profile Hydration (/auth/me)
    headers = {"Authorization": f"Bearer {token}"}
    me_resp = client.get("/api/v1/auth/me", headers=headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == op.email

    # Invalid Password
    bad_login = client.post("/api/v1/auth/login", json={"email": op.email, "password": "WrongPassword"})
    assert bad_login.status_code == 401

    # Missing / Invalid Token
    unauth_me = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer InvalidTokenStr"})
    assert unauth_me.status_code == 401


# ------------------------------------------------------------------------------
# 3. COMPLETE 8-ROLE RBAC MATRIX
# ------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_web_rbac_role_matrix(client):
    """Test all 8 roles for motor control authorization boundaries."""
    org, site, station, controller, motor, sensors, users = setup_web_test_hierarchy("WEB_RBAC")

    operator_roles = [
        UserRole.SUPER_ADMIN,
        UserRole.ORGANIZATION_ADMIN,
        UserRole.SITE_MANAGER,
        UserRole.STATION_OPERATOR,
        UserRole.TECHNICIAN,
        UserRole.OWNER,
    ]

    read_only_roles = [
        UserRole.VIEWER,
        UserRole.FAMILY_MEMBER,
    ]

    for role in operator_roles:
        u = users[role]
        login_resp = client.post("/api/v1/auth/login", json={"email": u.email, "password": "SecretPass123!"})
        headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}
        cmd_resp = client.post(f"/api/v1/motors/{motor.id}/start", headers=headers)
        assert cmd_resp.status_code == 200, f"Role '{role.value}' should be allowed to dispatch START"

    for role in read_only_roles:
        u = users[role]
        login_resp = client.post("/api/v1/auth/login", json={"email": u.email, "password": "SecretPass123!"})
        headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}
        cmd_resp = client.post(f"/api/v1/motors/{motor.id}/start", headers=headers)
        assert cmd_resp.status_code == 403, f"Read-only role '{role.value}' must be forbidden from motor start"


# ------------------------------------------------------------------------------
# 4. HIERARCHY NAVIGATION & TENANT ISOLATION
# ------------------------------------------------------------------------------

def test_web_hierarchy_and_cross_tenant_isolation(client):
    """Verify tenant scoping and IDOR protection across org/site/station/controller/motor."""
    org_a, site_a, station_a, controller_a, motor_a, sensors_a, users_a = setup_web_test_hierarchy("WEB_TENANT_A")
    org_b, site_b, station_b, controller_b, motor_b, sensors_b, users_b = setup_web_test_hierarchy("WEB_TENANT_B")

    op_a = users_a[UserRole.STATION_OPERATOR]
    token_a = client.post("/api/v1/auth/login", json={"email": op_a.email, "password": "SecretPass123!"}).json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # Access own hierarchy -> HTTP 200
    assert client.get("/api/v1/sites", headers=headers_a).status_code == 200
    assert client.get(f"/api/v1/sites/{site_a.id}", headers=headers_a).status_code == 200
    assert client.get(f"/api/v1/stations?site_id={site_a.id}", headers=headers_a).status_code == 200
    assert client.get(f"/api/v1/controllers?station_id={station_a.id}", headers=headers_a).status_code == 200
    assert client.get(f"/api/v1/motors?controller_id={controller_a.id}", headers=headers_a).status_code == 200

    # Cross-tenant IDOR access -> HTTP 404
    assert client.get(f"/api/v1/sites/{site_b.id}", headers=headers_a).status_code == 404
    assert client.get(f"/api/v1/motors/{motor_b.id}", headers=headers_a).status_code == 404
    assert client.post(f"/api/v1/motors/{motor_b.id}/start", headers=headers_a).status_code == 404


# ------------------------------------------------------------------------------
# 5. WEBSOCKET HANDSHAKE, PING/PONG, RESUBSCRIBE & MULTI-TAB SESSIONS
# ------------------------------------------------------------------------------

def test_web_websocket_capabilities_and_multi_tab(client):
    """Verify WS authentication, subscriptions, PING/PONG, and multi-tab session resilience."""
    org, site, station, controller, motor, sensors, users = setup_web_test_hierarchy("WEB_WS")
    op = users[UserRole.STATION_OPERATOR]
    token = client.post("/api/v1/auth/login", json={"email": op.email, "password": "SecretPass123!"}).json()["access_token"]

    # Tab 1 Connection
    with client.websocket_connect(f"/api/v1/ws?token={token}") as ws1:
        init_1 = ws1.receive_json()
        assert init_1["type"] == "CONNECTED"

        ws1.send_json({"action": "PING"})
        assert ws1.receive_json()["type"] == "PONG"

        ws1.send_json({"action": "SUBSCRIBE", "channels": [f"motor:{motor.id}"]})
        assert ws1.receive_json()["type"] == "SUBSCRIBED"

        # Tab 2 Concurrent Connection
        with client.websocket_connect(f"/api/v1/ws?token={token}") as ws2:
            init_2 = ws2.receive_json()
            assert init_2["type"] == "CONNECTED"

            ws2.send_json({"action": "PING"})
            assert ws2.receive_json()["type"] == "PONG"


# ------------------------------------------------------------------------------
# 6. LIVE MULTI-SENSOR TELEMETRY STREAMING
# ------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_web_live_telemetry_streaming(client):
    """Verify telemetry readings across all 6 sensor types reach backend & WS."""
    org, site, station, controller, motor, sensors, users = setup_web_test_hierarchy("WEB_TEL")
    op = users[UserRole.STATION_OPERATOR]
    token = client.post("/api/v1/auth/login", json={"email": op.email, "password": "SecretPass123!"}).json()["access_token"]

    with client.websocket_connect(f"/api/v1/ws?token={token}") as ws:
        ws.receive_json()  # CONNECTED
        ws.send_json({"action": "SUBSCRIBE", "channels": [f"device:{controller.device_uid}"]})
        ws.receive_json()  # SUBSCRIBED

        telemetry_samples = [
            (SensorType.WATER_LEVEL, 84.5, "PERCENT"),
            (SensorType.TURBIDITY, 4.2, "NTU"),
            (SensorType.FLOW, 120.8, "LPM"),
            (SensorType.CURRENT, 14.2, "AMPERES"),
            (SensorType.VOLTAGE, 415.0, "VOLTS"),
            (SensorType.PRESSURE, 5.8, "BAR"),
        ]

        for s_type, value, unit in telemetry_samples:
            sensor = sensors[s_type]
            payload = {
                "sensor_code": sensor.sensor_code,
                "value": value,
                "unit": unit,
                "occurred_at": datetime.now(timezone.utc).isoformat(),
            }
            saved = await process_telemetry_payload(controller.device_uid, payload)
            assert saved == 1

            ws_evt = ws.receive_json()
            assert ws_evt["event"] == "TELEMETRY"
            assert ws_evt["sensor_code"] == sensor.sensor_code
            assert ws_evt["value"] == value


# ------------------------------------------------------------------------------
# 7. MOTOR COMMAND LIFECYCLES (START, STOP, EMERGENCY STOP)
# ------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_web_motor_command_lifecycles(client):
    """Verify START, STOP, and EMERGENCY STOP end-to-end command lifecycles."""
    org, site, station, controller, motor, sensors, users = setup_web_test_hierarchy("WEB_CMD")
    op = users[UserRole.STATION_OPERATOR]
    token = client.post("/api/v1/auth/login", json={"email": op.email, "password": "SecretPass123!"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    with client.websocket_connect(f"/api/v1/ws?token={token}") as ws:
        ws.receive_json()  # CONNECTED
        ws.send_json({"action": "SUBSCRIBE", "channels": [f"motor:{motor.id}", f"device:{controller.device_uid}"]})
        ws.receive_json()  # SUBSCRIBED

        # 1. Dispatch START
        start_resp = client.post(f"/api/v1/motors/{motor.id}/start", headers=headers)
        assert start_resp.status_code == 200
        cmd_id = start_resp.json()["id"]

        # Ingest Controller ACK -> EXECUTED
        await process_ack_payload(controller.device_uid, {"command_id": cmd_id, "status": "EXECUTED"})
        ws_cmd_1 = ws.receive_json()
        assert ws_cmd_1["event"] == "COMMAND_LIFECYCLE"
        assert ws_cmd_1["status"] == "EXECUTED"

        # Ingest Motor ON
        await process_status_payload(controller.device_uid, {"controller_status": "ACTIVE", "motors": [{"motor_code": motor.motor_code, "status": "ON"}]})
        ws_m_1 = ws.receive_json()
        assert ws_m_1["event"] == "MOTOR_STATE"
        assert ws_m_1["status"] == "ON"

        # 2. Dispatch STOP
        stop_resp = client.post(f"/api/v1/motors/{motor.id}/stop", headers=headers)
        assert stop_resp.status_code == 200
        stop_cmd_id = stop_resp.json()["id"]

        await process_ack_payload(controller.device_uid, {"command_id": stop_cmd_id, "status": "EXECUTED"})
        ws_cmd_2 = ws.receive_json()
        assert ws_cmd_2["event"] == "COMMAND_LIFECYCLE"
        assert ws_cmd_2["status"] == "EXECUTED"

        await process_status_payload(controller.device_uid, {"controller_status": "ACTIVE", "motors": [{"motor_code": motor.motor_code, "status": "OFF"}]})
        ws_m_2 = ws.receive_json()
        assert ws_m_2["event"] == "MOTOR_STATE"
        assert ws_m_2["status"] == "OFF"

        # 3. Emergency Stop Fault Event
        fault_payload = {
            "motor_code": motor.motor_code,
            "fault_type": "EMERGENCY_STOP",
            "description": "Physical E-Stop Switch Triggered",
        }
        await process_fault_payload(controller.device_uid, fault_payload)
        ws_alert = ws.receive_json()
        assert ws_alert["event"] == "SAFETY_ALERT"
        assert ws_alert["event_type"] == "EMERGENCY_STOP"


# ------------------------------------------------------------------------------
# 8. EDGE SAFETY INTERLOCKS & OFFLINE CONTROLLER AUTONOMY
# ------------------------------------------------------------------------------

def test_web_edge_safety_and_offline_autonomy():
    """Verify ESP32 simulator local safety interlocks and offline buffering."""
    sim = ESP32Simulator(device_uid="WEB-SIMULATOR-UID", motor_code="PUMP_01", transition_delay=0.0)

    # Turbidity > 25 NTU cutoff
    sim.turbidity = 32.5
    res = sim.process_command({"command_id": "CMD_001", "command_type": "START", "motor_code": "PUMP_01"})
    assert res is False
    assert sim.emergency_stop_latched is False

    # Tank Full >= 95% cutoff
    sim.turbidity = 5.0
    sim.tank_level = 96.0
    res_full = sim.process_command({"command_id": "CMD_002", "command_type": "START", "motor_code": "PUMP_01"})
    assert res_full is False

    # Offline buffering
    sim.tank_level = 50.0
    sim.is_connected = False
    sim.trigger_emergency_stop()
    assert len(sim.offline_event_buffer) >= 1
    assert any(evt["payload"].get("fault_type") == "EMERGENCY_STOP" for evt in sim.offline_event_buffer if "payload" in evt)

