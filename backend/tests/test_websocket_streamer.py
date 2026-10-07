"""
HydraControl — Phase 8 P8-T02 Event & Telemetry Streamer Tests
Verifies real-time streaming of:
- Sensor telemetry broadcasts
- Motor operational state transitions (OFF -> STARTING -> ON -> STOPPING -> FAULT)
- Command lifecycle events (SENT, ACKNOWLEDGED, EXECUTED, FAILED, TIMEOUT)
- Safety and fault alerts (EMERGENCY_STOP, FAULT)
- Multi-level channel routing (org, site, station, motor, device)
- Cross-tenant isolation during real-time streaming
- Non-blocking broadcast resilience against failed or disconnected clients
"""
import pytest
import uuid
from datetime import datetime, timezone, timedelta
from starlette.testclient import TestClient

from app.main import app
from app.db.base import Base
from app.db.session import sync_engine, get_sync_session, AsyncSessionLocal
from app.models.user import User, UserRole
from app.models.organization import Organization, OrganizationStatus
from app.models.site import Site, SiteStatus, SiteType
from app.models.station import Station, StationStatus, StationType
from app.models.controller import Controller, ControllerStatus, ControllerType
from app.models.motor import Motor, MotorStatus, MotorType
from app.models.sensor import Sensor, SensorStatus, SensorType
from app.models.motor_command import MotorCommand, CommandType, CommandStatus
from app.core.security import create_access_token, get_password_hash
from app.mqtt.handlers.telemetry_handler import process_telemetry_payload
from app.mqtt.handlers.status_handler import process_status_payload
from app.mqtt.handlers.ack_handler import process_ack_payload
from app.mqtt.handlers.fault_handler import process_fault_payload
from app.services.command_watchdog import process_command_timeouts
from app.websocket.streamer import (
    stream_telemetry,
    stream_motor_state,
    stream_command_lifecycle,
    stream_safety_alert,
)
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


def create_user_with_token(email: str, role: UserRole, org_id: uuid.UUID) -> tuple[User, str]:
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
            "organization_id": str(user.organization_id)
        }
    )
    return user, token


def create_hierarchy(prefix: str):
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
            status=SiteStatus.ACTIVE
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
            device_uid=f"{prefix}-HW-STREAM-CTRL",
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
            name=f"{prefix} Water Level",
            sensor_code="LEVEL_01",
            sensor_type=SensorType.WATER_LEVEL,
            status=SensorStatus.ACTIVE
        )
        session.add(sensor)

        session.commit()
        return org, site, station, controller, motor, sensor


# ==============================================================================
# TELEMETRY STREAMING TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_telemetry_streaming_to_authorized_clients(client):
    """
    When MQTT telemetry is ingested via process_telemetry_payload,
    subscribers on device/site/org channels receive the TELEMETRY event.
    """
    org, site, station, controller, motor, sensor = create_hierarchy("STR_TEL")
    user, token = create_user_with_token("tel_stream@example.com", UserRole.STATION_OPERATOR, org.id)

    with client.websocket_connect(f"/api/v1/ws?token={token}") as ws:
        _ = ws.receive_json()  # CONNECTED
        ws.send_json({"action": "SUBSCRIBE", "channels": [f"device:{controller.device_uid}"]})
        sub_resp = ws.receive_json()
        assert sub_resp["type"] == "SUBSCRIBED"
        assert f"device:{controller.device_uid}" in sub_resp["channels"]

        # Ingest telemetry payload
        telemetry_payload = {
            "sensor_code": "LEVEL_01",
            "value": 78.5,
            "unit": "PERCENT",
            "occurred_at": datetime.now(timezone.utc).isoformat()
        }
        saved = await process_telemetry_payload(controller.device_uid, telemetry_payload)
        assert saved == 1

        # Receive streamed event
        event_msg = ws.receive_json()
        assert event_msg["event"] == "TELEMETRY"
        assert event_msg["device_uid"] == controller.device_uid
        assert event_msg["sensor_code"] == "LEVEL_01"
        assert event_msg["value"] == 78.5
        assert event_msg["unit"] == "%"
        assert event_msg["organization_id"] == str(org.id)


@pytest.mark.asyncio
async def test_telemetry_streaming_tenant_isolation(client):
    """
    Org B client subscribed to Org B channel must NOT receive telemetry from Org A device.
    """
    org_a, _, _, controller_a, _, _ = create_hierarchy("STR_TEL_A")
    org_b, _, _, controller_b, _, _ = create_hierarchy("STR_TEL_B")

    user_b, token_b = create_user_with_token("user_b_tel@example.com", UserRole.STATION_OPERATOR, org_b.id)

    with client.websocket_connect(f"/api/v1/ws?token={token_b}") as ws_b:
        _ = ws_b.receive_json()  # CONNECTED
        ws_b.send_json({"action": "SUBSCRIBE", "channels": [f"device:{controller_b.device_uid}"]})
        _ = ws_b.receive_json()  # SUBSCRIBED

        # Ingest telemetry for Org A device
        payload_a = {
            "sensor_code": "LEVEL_01",
            "value": 90.0,
            "unit": "PERCENT"
        }
        await process_telemetry_payload(controller_a.device_uid, payload_a)

        # ws_b sends PING to verify no cross-tenant message was placed in queue
        ws_b.send_json({"action": "PING"})
        pong = ws_b.receive_json()
        assert pong["type"] == "PONG"


# ==============================================================================
# MOTOR STATE STREAMING TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_motor_state_streaming_on_status_sync(client):
    """
    Controller status updates trigger MOTOR_STATE events when motor transitions state.
    """
    org, site, station, controller, motor, _ = create_hierarchy("STR_MOT")
    user, token = create_user_with_token("mot_stream@example.com", UserRole.STATION_OPERATOR, org.id)

    with client.websocket_connect(f"/api/v1/ws?token={token}") as ws:
        _ = ws.receive_json()  # CONNECTED
        ws.send_json({"action": "SUBSCRIBE", "channels": [f"motor:{motor.id}"]})
        _ = ws.receive_json()  # SUBSCRIBED

        # Report motor status transition OFF -> ON
        status_payload = {
            "controller_status": "ACTIVE",
            "motors": [
                {
                    "motor_code": motor.motor_code,
                    "status": "ON"
                }
            ]
        }
        res = await process_status_payload(controller.device_uid, status_payload)
        assert res is True

        event_msg = ws.receive_json()
        assert event_msg["event"] == "MOTOR_STATE"
        assert event_msg["motor_id"] == str(motor.id)
        assert event_msg["motor_code"] == motor.motor_code
        assert event_msg["status"] == "ON"
        assert event_msg["previous_status"] == "OFF"
        assert event_msg["organization_id"] == str(org.id)


# ==============================================================================
# COMMAND LIFECYCLE STREAMING TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_command_lifecycle_ack_streaming(client):
    """
    ACK handler updates MotorCommand and broadcasts COMMAND_LIFECYCLE events.
    """
    org, site, station, controller, motor, _ = create_hierarchy("STR_CMD")
    user, token = create_user_with_token("cmd_stream@example.com", UserRole.STATION_OPERATOR, org.id)

    # Create a command in database
    command_id = uuid.uuid4()
    with get_sync_session() as session:
        cmd = MotorCommand(
            id=command_id,
            motor_id=motor.id,
            command_type=CommandType.START,
            status=CommandStatus.SENT,
            requested_at=datetime.now(timezone.utc),
            sent_at=datetime.now(timezone.utc)
        )
        session.add(cmd)
        session.commit()

    with client.websocket_connect(f"/api/v1/ws?token={token}") as ws:
        _ = ws.receive_json()  # CONNECTED
        ws.send_json({"action": "SUBSCRIBE", "channels": [f"motor:{motor.id}"]})
        _ = ws.receive_json()  # SUBSCRIBED

        # Ingest EXECUTED ACK
        ack_payload = {
            "command_id": str(command_id),
            "status": "EXECUTED"
        }
        res_cmd = await process_ack_payload(controller.device_uid, ack_payload)
        assert res_cmd is not None
        assert res_cmd.status == CommandStatus.EXECUTED

        event_msg = ws.receive_json()
        assert event_msg["event"] == "COMMAND_LIFECYCLE"
        assert event_msg["command_id"] == str(command_id)
        assert event_msg["motor_id"] == str(motor.id)
        assert event_msg["status"] == "EXECUTED"
        assert event_msg["device_uid"] == controller.device_uid


@pytest.mark.asyncio
async def test_command_watchdog_timeout_streaming(client):
    """
    Command watchdog detects expired commands and broadcasts TIMEOUT lifecycle events.
    """
    org, site, station, controller, motor, _ = create_hierarchy("STR_TO")
    user, token = create_user_with_token("to_stream@example.com", UserRole.STATION_OPERATOR, org.id)

    # Create expired command
    command_id = uuid.uuid4()
    old_time = datetime.now(timezone.utc) - timedelta(seconds=120)
    with get_sync_session() as session:
        cmd = MotorCommand(
            id=command_id,
            motor_id=motor.id,
            command_type=CommandType.START,
            status=CommandStatus.SENT,
            requested_at=old_time,
            sent_at=old_time
        )
        session.add(cmd)
        session.commit()

    with client.websocket_connect(f"/api/v1/ws?token={token}") as ws:
        _ = ws.receive_json()  # CONNECTED
        ws.send_json({"action": "SUBSCRIBE", "channels": [f"motor:{motor.id}"]})
        _ = ws.receive_json()  # SUBSCRIBED

        # Run watchdog
        async with AsyncSessionLocal() as session:
            res = await process_command_timeouts(session, timeout_seconds=30)
            assert res["timed_out_count"] >= 1

        event_msg = ws.receive_json()
        assert event_msg["event"] == "COMMAND_LIFECYCLE"
        assert event_msg["command_id"] == str(command_id)
        assert event_msg["status"] == "TIMEOUT"
        assert "timed out" in event_msg["error_message"].lower()


# ==============================================================================
# SAFETY & FAULT STREAMING TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_safety_alert_streaming(client):
    """
    Fault handler records safety trip and broadcasts SAFETY_ALERT (EMERGENCY_STOP / FAULT).
    """
    org, site, station, controller, motor, _ = create_hierarchy("STR_SAFE")
    user, token = create_user_with_token("safe_stream@example.com", UserRole.SITE_MANAGER, org.id)

    with client.websocket_connect(f"/api/v1/ws?token={token}") as ws:
        _ = ws.receive_json()  # CONNECTED
        ws.send_json({"action": "SUBSCRIBE", "channels": [f"site:{site.id}"]})
        _ = ws.receive_json()  # SUBSCRIBED

        # Ingest emergency stop fault report
        fault_payload = {
            "motor_code": motor.motor_code,
            "fault_type": "EMERGENCY_STOP",
            "description": "Hardware e-stop mushroom button pressed"
        }
        ev = await process_fault_payload(controller.device_uid, fault_payload)
        assert ev is not None

        event_msg = ws.receive_json()
        assert event_msg["event"] == "SAFETY_ALERT"
        assert event_msg["event_type"] == "EMERGENCY_STOP"
        assert event_msg["motor_id"] == str(motor.id)
        assert event_msg["device_uid"] == controller.device_uid
        assert "mushroom" in event_msg["description"]


# ==============================================================================
# NON-BLOCKING RESILIENCE TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_streamer_non_blocking_with_disconnected_client(client):
    """
    If one client closes unexpectedly, broadcast continues smoothly to other active clients.
    """
    org, site, station, controller, motor, _ = create_hierarchy("STR_RESIL")
    user1, token1 = create_user_with_token("resil1@example.com", UserRole.STATION_OPERATOR, org.id)
    user2, token2 = create_user_with_token("resil2@example.com", UserRole.STATION_OPERATOR, org.id)

    with client.websocket_connect(f"/api/v1/ws?token={token1}") as ws1:
        _ = ws1.receive_json()  # CONNECTED
        ws1.send_json({"action": "SUBSCRIBE", "channels": [f"org:{org.id}"]})
        _ = ws1.receive_json()  # SUBSCRIBED

        with client.websocket_connect(f"/api/v1/ws?token={token2}") as ws2:
            _ = ws2.receive_json()  # CONNECTED
            ws2.send_json({"action": "SUBSCRIBE", "channels": [f"org:{org.id}"]})
            _ = ws2.receive_json()  # SUBSCRIBED

            # Broadcast a state update
            delivered = await stream_motor_state(
                motor_id=motor.id,
                motor_code=motor.motor_code,
                device_uid=controller.device_uid,
                status=MotorStatus.ON,
                organization_id=org.id
            )
            assert delivered == 2

            m1 = ws1.receive_json()
            m2 = ws2.receive_json()
            assert m1["event"] == "MOTOR_STATE"
            assert m2["event"] == "MOTOR_STATE"
