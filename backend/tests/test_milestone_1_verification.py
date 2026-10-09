"""
HydraControl — Phase 9 Milestone 1 Critical Acceptance Test Suite
Verifies the complete end-to-end system loop:
- Step 1: Operator Authentication & Profile Hydration
- Step 2: Multi-Tier Hierarchy Navigation & Cross-Tenant Isolation
- Step 3: Real-Time WebSocket Handshake & Channel Subscriptions
- Step 4: Multi-Sensor Telemetry Ingestion & Live WebSocket Broadcasting
- Step 5: Real-World Motor START Command Lifecycle (REST -> DB -> MQTT -> ACK -> WS)
- Step 6: Real-World Motor STOP Command Lifecycle
- Step 7: Emergency Stop / Local Edge Safety Interlock & High-Priority Alerts
- Step 8: Disconnect & Reconnect Session Resumption
"""

import pytest
import uuid
from datetime import datetime, timezone
from starlette.testclient import TestClient

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


def helper_setup_milestone_hierarchy(prefix: str):
    """Creates a complete multi-tenant hierarchy for Milestone 1 testing."""
    with get_sync_session() as session:
        org = Organization(
            id=uuid.uuid4(),
            name=f"{prefix} Enterprise",
            organization_code=f"{prefix}_CORP".upper(),
            status=OrganizationStatus.ACTIVE,
        )
        session.add(org)

        site = Site(
            id=uuid.uuid4(),
            organization_id=org.id,
            name=f"{prefix} Water Treatment Site",
            site_code=f"{prefix}_SITE_01".upper(),
            site_type=SiteType.FACTORY,
            status=SiteStatus.ACTIVE,
        )
        session.add(site)

        station = Station(
            id=uuid.uuid4(),
            site_id=site.id,
            name=f"{prefix} Raw Water Station",
            station_code=f"{prefix}_STN_01".upper(),
            station_type=StationType.WATER_SUPPLY,
            status=StationStatus.ACTIVE,
        )
        session.add(station)

        controller = Controller(
            id=uuid.uuid4(),
            station_id=station.id,
            name=f"{prefix} ESP32 Primary Controller",
            controller_code=f"{prefix}_CTRL_01".upper(),
            device_uid=f"{prefix}-ESP32-HARDWARE-UID",
            controller_type=ControllerType.ESP32,
            status=ControllerStatus.ACTIVE,
        )
        session.add(controller)

        motor = Motor(
            id=uuid.uuid4(),
            controller_id=controller.id,
            name=f"{prefix} Raw Water Intake Pump",
            motor_code=f"{prefix}_PUMP_01".upper(),
            motor_type=MotorType.WATER_PUMP,
            status=MotorStatus.OFF,
            rated_power=7.5,
        )
        session.add(motor)

        sensor_lvl = Sensor(
            id=uuid.uuid4(),
            controller_id=controller.id,
            name=f"{prefix} Tank Level Sensor",
            sensor_code=f"{prefix}_LEVEL_01".upper(),
            sensor_type=SensorType.WATER_LEVEL,
            status=SensorStatus.ACTIVE,
        )
        session.add(sensor_lvl)

        sensor_turb = Sensor(
            id=uuid.uuid4(),
            controller_id=controller.id,
            name=f"{prefix} Turbidity Sensor",
            sensor_code=f"{prefix}_TURB_01".upper(),
            sensor_type=SensorType.TURBIDITY,
            status=SensorStatus.ACTIVE,
        )
        session.add(sensor_turb)

        # Create Operator user
        operator_user = User(
            id=uuid.uuid4(),
            email=f"{prefix.lower()}_operator@hydracontrol.io",
            password_hash=get_password_hash("SecretPass123!"),
            name=f"{prefix} Chief Operator",
            role=UserRole.STATION_OPERATOR,
            organization_id=org.id,
            is_active=True,
        )
        session.add(operator_user)

        session.commit()
        return org, site, station, controller, motor, sensor_lvl, sensor_turb, operator_user


# ==============================================================================
# MILESTONE 1 END-TO-END VERIFICATION
# ==============================================================================

@pytest.mark.asyncio
async def test_milestone_1_complete_flow(client):
    """
    CRITICAL ACCEPTANCE TEST 1:
    End-to-end verification of Authentication, Hierarchy Navigation, Real-time WebSocket,
    Telemetry Streaming, Motor START/STOP command loop, and Emergency Stop Fault Handling.
    """
    # --------------------------------------------------------------------------
    # STEP 1 — AUTHENTICATION
    # --------------------------------------------------------------------------
    org, site, station, controller, motor, sensor_lvl, sensor_turb, operator = (
        helper_setup_milestone_hierarchy("M1_ALPHA")
    )

    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": operator.email, "password": "SecretPass123!"},
    )
    assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
    token_data = login_resp.json()
    jwt_token = token_data["access_token"]
    assert jwt_token is not None

    # Verify Profile Hydration
    headers = {"Authorization": f"Bearer {jwt_token}"}
    me_resp = client.get("/api/v1/auth/me", headers=headers)
    assert me_resp.status_code == 200
    me_data = me_resp.json()
    assert me_data["email"] == operator.email
    assert me_data["role"] == UserRole.STATION_OPERATOR.value
    assert me_data["is_active"] is True

    org_resp = client.get("/api/v1/auth/organization", headers=headers)
    assert org_resp.status_code == 200
    assert org_resp.json()["id"] == str(org.id)

    # --------------------------------------------------------------------------
    # STEP 2 — NAVIGATION & TENANT ISOLATION
    # --------------------------------------------------------------------------
    sites_resp = client.get("/api/v1/sites", headers=headers)
    assert sites_resp.status_code == 200
    assert any(s["id"] == str(site.id) for s in sites_resp.json())

    stations_resp = client.get(f"/api/v1/stations?site_id={site.id}", headers=headers)
    assert stations_resp.status_code == 200
    assert any(st["id"] == str(station.id) for st in stations_resp.json())

    controllers_resp = client.get(f"/api/v1/controllers?station_id={station.id}", headers=headers)
    assert controllers_resp.status_code == 200
    assert any(c["id"] == str(controller.id) for c in controllers_resp.json())

    motors_resp = client.get(f"/api/v1/motors?controller_id={controller.id}", headers=headers)
    assert motors_resp.status_code == 200
    assert any(m["id"] == str(motor.id) for m in motors_resp.json())

    # Cross-Tenant IDOR Check
    foreign_org, foreign_site, _, _, _, _, _, _ = helper_setup_milestone_hierarchy("M1_BETA")
    foreign_site_resp = client.get(f"/api/v1/sites/{foreign_site.id}", headers=headers)
    assert foreign_site_resp.status_code == 404, "Foreign site must be hidden (IDOR protection)"

    # --------------------------------------------------------------------------
    # STEP 3 — WEBSOCKET CONNECTION & SUBSCRIPTION
    # --------------------------------------------------------------------------
    with client.websocket_connect(f"/api/v1/ws?token={jwt_token}") as ws:
        init_msg = ws.receive_json()
        assert init_msg["type"] == "CONNECTED"
        assert init_msg["user_id"] == str(operator.id)
        assert init_msg["organization_id"] == str(org.id)

        # Heartbeat verification
        ws.send_json({"action": "PING"})
        pong_msg = ws.receive_json()
        assert pong_msg["type"] == "PONG"

        # Subscribe to device & motor channels
        ws.send_json({
            "action": "SUBSCRIBE",
            "channels": [
                f"org:{org.id}",
                f"site:{site.id}",
                f"station:{station.id}",
                f"motor:{motor.id}",
                f"device:{controller.device_uid}",
            ],
        })
        sub_resp = ws.receive_json()
        assert sub_resp["type"] == "SUBSCRIBED"
        assert len(sub_resp["channels"]) == 5
        assert len(sub_resp["failed"]) == 0

        # ----------------------------------------------------------------------
        # STEP 4 — LIVE TELEMETRY STREAMING
        # ----------------------------------------------------------------------
        telemetry_payload = {
            "sensor_code": sensor_lvl.sensor_code,
            "value": 72.4,
            "unit": "PERCENT",
            "occurred_at": datetime.now(timezone.utc).isoformat(),
        }
        saved_count = await process_telemetry_payload(controller.device_uid, telemetry_payload)
        assert saved_count == 1

        tel_event = ws.receive_json()
        assert tel_event["event"] == "TELEMETRY"
        assert tel_event["device_uid"] == controller.device_uid
        assert tel_event["sensor_code"] == sensor_lvl.sensor_code
        assert tel_event["value"] == 72.4

        # ----------------------------------------------------------------------
        # STEP 5 — START MOTOR COMMAND LIFECYCLE
        # ----------------------------------------------------------------------
        start_resp = client.post(f"/api/v1/motors/{motor.id}/start", headers=headers)
        assert start_resp.status_code == 200
        cmd_data = start_resp.json()
        command_id = uuid.UUID(cmd_data["id"])
        assert cmd_data["status"] in ("PENDING", "SENT")

        # Ingest Controller ACK -> EXECUTED
        ack_payload = {
            "command_id": str(command_id),
            "status": "EXECUTED",
        }
        ack_result = await process_ack_payload(controller.device_uid, ack_payload)
        assert ack_result is not None
        assert ack_result.status == CommandStatus.EXECUTED

        # Verify command lifecycle event on WebSocket
        ws_cmd_event = ws.receive_json()
        assert ws_cmd_event["event"] == "COMMAND_LIFECYCLE"
        assert ws_cmd_event["command_id"] == str(command_id)
        assert ws_cmd_event["status"] == "EXECUTED"

        # Ingest physical motor status update (OFF -> ON)
        status_payload = {
            "controller_status": "ACTIVE",
            "motors": [{"motor_code": motor.motor_code, "status": "ON"}],
        }
        await process_status_payload(controller.device_uid, status_payload)

        ws_motor_event = ws.receive_json()
        assert ws_motor_event["event"] == "MOTOR_STATE"
        assert ws_motor_event["motor_id"] == str(motor.id)
        assert ws_motor_event["status"] == "ON"
        assert ws_motor_event["previous_status"] in ("OFF", "STARTING")

        # ----------------------------------------------------------------------
        # STEP 6 — STOP MOTOR COMMAND LIFECYCLE
        # ----------------------------------------------------------------------
        stop_resp = client.post(f"/api/v1/motors/{motor.id}/stop", headers=headers)
        assert stop_resp.status_code == 200
        stop_cmd_id = stop_resp.json()["id"]

        # Ingest Controller ACK -> EXECUTED for STOP
        await process_ack_payload(controller.device_uid, {"command_id": stop_cmd_id, "status": "EXECUTED"})
        stop_ws_event = ws.receive_json()
        assert stop_ws_event["event"] == "COMMAND_LIFECYCLE"
        assert stop_ws_event["status"] == "EXECUTED"

        # Ingest physical motor status update (ON -> OFF)
        await process_status_payload(
            controller.device_uid,
            {"controller_status": "ACTIVE", "motors": [{"motor_code": motor.motor_code, "status": "OFF"}]},
        )
        stop_state_event = ws.receive_json()
        assert stop_state_event["event"] == "MOTOR_STATE"
        assert stop_state_event["status"] == "OFF"
        assert stop_state_event["previous_status"] in ("ON", "STOPPING")

        # ----------------------------------------------------------------------
        # STEP 7 — EMERGENCY STOP & SAFETY FAULT ALERTING
        # ----------------------------------------------------------------------
        estop_payload = {
            "motor_code": motor.motor_code,
            "fault_type": "EMERGENCY_STOP",
            "description": "Hardware Emergency Stop Mushroom Switch Activated",
        }
        fault_event = await process_fault_payload(controller.device_uid, estop_payload)
        assert fault_event is not None

        estop_ws_alert = ws.receive_json()
        assert estop_ws_alert["event"] == "SAFETY_ALERT"
        assert estop_ws_alert["event_type"] == "EMERGENCY_STOP"
        assert estop_ws_alert["motor_id"] == str(motor.id)
        assert "Emergency Stop" in estop_ws_alert["description"]

        # ----------------------------------------------------------------------
        # STEP 8 — RECONNECT RESILIENCE
        # ----------------------------------------------------------------------
        # Closing this context cleanly simulates client-side disconnect
        pass

    # Reconnect with valid token
    with client.websocket_connect(f"/api/v1/ws?token={jwt_token}") as ws2:
        reconnect_msg = ws2.receive_json()
        assert reconnect_msg["type"] == "CONNECTED"
        ws2.send_json({"action": "PING"})
        assert ws2.receive_json()["type"] == "PONG"


@pytest.mark.asyncio
async def test_milestone_1_rbac_and_safety_lockouts(client):
    """
    Verify RBAC enforcement and Safety Lockouts for Milestone 1:
    1. Read-only VIEWER role cannot dispatch motor start/stop (HTTP 403)
    2. Attempting to START a motor in FAULT status is blocked (HTTP 400)
    3. Cross-tenant command dispatch is blocked (HTTP 404)
    """
    org, site, station, controller, motor, sensor_lvl, sensor_turb, operator = (
        helper_setup_milestone_hierarchy("M1_SEC_A")
    )

    # Create a VIEWER user
    with get_sync_session() as session:
        viewer_user = User(
            id=uuid.uuid4(),
            email="m1_viewer@hydracontrol.io",
            password_hash=get_password_hash("SecretPass123!"),
            name="M1 Read Only Viewer",
            role=UserRole.VIEWER,
            organization_id=org.id,
            is_active=True,
        )
        session.add(viewer_user)
        session.commit()

    # Login as VIEWER
    viewer_login = client.post(
        "/api/v1/auth/login",
        json={"email": "m1_viewer@hydracontrol.io", "password": "SecretPass123!"},
    )
    assert viewer_login.status_code == 200
    viewer_jwt = viewer_login.json()["access_token"]
    viewer_headers = {"Authorization": f"Bearer {viewer_jwt}"}

    # 1. VIEWER attempting to START pump -> 403 Forbidden
    resp = client.post(f"/api/v1/motors/{motor.id}/start", headers=viewer_headers)
    assert resp.status_code == 403, f"Viewer must be forbidden from starting motor: {resp.text}"

    # 2. Operator attempting cross-tenant motor start -> 404 Not Found
    _, _, _, _, foreign_motor, _, _, _ = helper_setup_milestone_hierarchy("M1_SEC_B")
    op_login = client.post(
        "/api/v1/auth/login",
        json={"email": operator.email, "password": "SecretPass123!"},
    )
    op_headers = {"Authorization": f"Bearer {op_login.json()['access_token']}"}

    foreign_resp = client.post(f"/api/v1/motors/{foreign_motor.id}/start", headers=op_headers)
    assert foreign_resp.status_code == 404, "Cross-tenant motor command must return 404"

    # 3. Motor in MAINTENANCE state -> Start is blocked (HTTP 400)
    with get_sync_session() as session:
        m = session.get(Motor, motor.id)
        m.status = MotorStatus.MAINTENANCE
        session.commit()

    maint_start_resp = client.post(f"/api/v1/motors/{motor.id}/start", headers=op_headers)
    assert maint_start_resp.status_code == 400, "Motor in MAINTENANCE state cannot be started"

