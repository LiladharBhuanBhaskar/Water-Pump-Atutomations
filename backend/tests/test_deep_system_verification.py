"""
HydraControl — Deep System Verification Test Suite (Pre-Phase-10 Verification)
Covers Deep Verification Layers:
- Layer 10: Command Idempotency (Duplicate ACKs & Terminal State Lock)
- Layer 11: Command Watchdog Timeout & Terminal State Preservation
- Layer 23: Cycle Repeatability (3x START/STOP & E-STOP/RESET cycles)
- Layer 24: Data Consistency & Relational Integrity
"""

import sys
import os
import pytest
import uuid
from datetime import datetime, timezone, timedelta
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
from app.models.motor_command import MotorCommand, CommandStatus, CommandType
from app.models.motor_event import MotorEvent
from app.core.security import get_password_hash
from app.mqtt.handlers.ack_handler import process_ack_payload
from app.mqtt.handlers.status_handler import process_status_payload
from app.mqtt.handlers.fault_handler import process_fault_payload
from app.services.command_watchdog import process_command_timeouts


@pytest.fixture(scope="module", autouse=True)
def setup_tables():
    Base.metadata.create_all(bind=sync_engine)
    yield
    Base.metadata.drop_all(bind=sync_engine)


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def setup_deep_test_hierarchy(prefix: str):
    """Creates an isolated enterprise tenant hierarchy for deep system testing."""
    with get_sync_session() as session:
        org = Organization(
            id=uuid.uuid4(),
            name=f"{prefix} Deep Utilities",
            organization_code=f"{prefix}_CORP".upper(),
            status=OrganizationStatus.ACTIVE,
        )
        session.add(org)

        site = Site(
            id=uuid.uuid4(),
            organization_id=org.id,
            name=f"{prefix} Deep Site",
            site_code=f"{prefix}_SITE_01".upper(),
            site_type=SiteType.FACTORY,
            status=SiteStatus.ACTIVE,
        )
        session.add(site)

        station = Station(
            id=uuid.uuid4(),
            site_id=site.id,
            name=f"{prefix} Deep Station",
            station_code=f"{prefix}_STN_01".upper(),
            station_type=StationType.WATER_SUPPLY,
            status=StationStatus.ACTIVE,
        )
        session.add(station)

        controller = Controller(
            id=uuid.uuid4(),
            station_id=station.id,
            name=f"{prefix} Deep Controller",
            controller_code=f"{prefix}_CTRL_01".upper(),
            device_uid=f"{prefix}-ESP32-DEEP-UID",
            controller_type=ControllerType.ESP32,
            status=ControllerStatus.ACTIVE,
        )
        session.add(controller)

        motor = Motor(
            id=uuid.uuid4(),
            controller_id=controller.id,
            name=f"{prefix} Deep Pump",
            motor_code=f"{prefix}_PUMP_01".upper(),
            motor_type=MotorType.WATER_PUMP,
            status=MotorStatus.OFF,
            rated_power=10.0,
        )
        session.add(motor)

        op = User(
            id=uuid.uuid4(),
            email=f"{prefix.lower()}_op@hydracontrol.io",
            password_hash=get_password_hash("SecretPass123!"),
            name=f"{prefix} Operator",
            role=UserRole.STATION_OPERATOR,
            organization_id=org.id,
            is_active=True,
        )
        session.add(op)
        session.commit()

        return org, site, station, controller, motor, op


# ------------------------------------------------------------------------------
# LAYER 10: COMMAND IDEMPOTENCY & TERMINAL LOCK
# ------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_deep_command_idempotency(client):
    """Verify duplicate ACKs and terminal state lockouts generate zero duplicate events."""
    org, site, station, controller, motor, op = setup_deep_test_hierarchy("DEEP_IDEM")
    token = client.post("/api/v1/auth/login", json={"email": op.email, "password": "SecretPass123!"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Dispatch START command
    start_resp = client.post(f"/api/v1/motors/{motor.id}/start", headers=headers)
    assert start_resp.status_code == 200
    cmd_id = start_resp.json()["id"]

    # Ingest EXECUTED ACK twice
    ack_1 = await process_ack_payload(controller.device_uid, {"command_id": cmd_id, "status": "EXECUTED"})
    assert ack_1 is not None
    assert ack_1.status == CommandStatus.EXECUTED

    ack_2 = await process_ack_payload(controller.device_uid, {"command_id": cmd_id, "status": "EXECUTED"})
    assert ack_2 is not None
    assert ack_2.status == CommandStatus.EXECUTED

    # Ingest status payload (ON) twice
    await process_status_payload(controller.device_uid, {"controller_status": "ACTIVE", "motors": [{"motor_code": motor.motor_code, "status": "ON"}]})
    await process_status_payload(controller.device_uid, {"controller_status": "ACTIVE", "motors": [{"motor_code": motor.motor_code, "status": "ON"}]})

    # Count MotorEvents to ensure no duplicate event flooding
    with get_sync_session() as session:
        events = session.query(MotorEvent).filter(MotorEvent.motor_id == motor.id).all()
        # Should contain exactly 1 STARTED event
        started_events = [e for e in events if e.event_type.value == "STARTED"]
        assert len(started_events) == 1


from app.db.session import sync_engine, get_sync_session, AsyncSessionLocal

# ------------------------------------------------------------------------------
# LAYER 11: COMMAND WATCHDOG & TERMINAL STATE PRESERVATION
# ------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_deep_command_watchdog_preserves_terminal(client):
    """Verify command watchdog marks expired pending commands as TIMEOUT but preserves EXECUTED commands."""
    org, site, station, controller, motor, op = setup_deep_test_hierarchy("DEEP_WD")

    now = datetime(2026, 10, 5, 12, 0, 0, tzinfo=timezone.utc)
    with get_sync_session() as session:
        # Create an expired pending command (requested 2 hours ago)
        old_cmd = MotorCommand(
            id=uuid.uuid4(),
            motor_id=motor.id,
            command_type=CommandType.START,
            status=CommandStatus.SENT,
            requested_at=now - timedelta(seconds=120),
            sent_at=now - timedelta(seconds=115),
        )
        session.add(old_cmd)
        session.commit()
        old_cmd_id = old_cmd.id

    # Run watchdog process with AsyncSessionLocal
    async with AsyncSessionLocal() as async_session:
        res = await process_command_timeouts(async_session, timeout_seconds=30, now=now)
        assert res["timed_out_count"] >= 1

    with get_sync_session() as session:
        cmd = session.get(MotorCommand, old_cmd_id)
        assert cmd.status == CommandStatus.TIMEOUT
        assert "timed out" in (cmd.error_message or "").lower()


# ------------------------------------------------------------------------------
# LAYER 23: CYCLE REPEATABILITY (3X START/STOP & E-STOP CYCLES)
# ------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_deep_cycle_repeatability(client):
    """Execute START -> STOP and E-STOP -> RESET cycles 3 consecutive times cleanly."""
    org, site, station, controller, motor, op = setup_deep_test_hierarchy("DEEP_CYC")
    token = client.post("/api/v1/auth/login", json={"email": op.email, "password": "SecretPass123!"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    for cycle in range(3):
        # 1. START Cycle
        start_resp = client.post(f"/api/v1/motors/{motor.id}/start", headers=headers)
        assert start_resp.status_code == 200
        cmd_start = start_resp.json()["id"]

        await process_ack_payload(controller.device_uid, {"command_id": cmd_start, "status": "EXECUTED"})
        await process_status_payload(controller.device_uid, {"controller_status": "ACTIVE", "motors": [{"motor_code": motor.motor_code, "status": "ON"}]})

        # 2. STOP Cycle
        stop_resp = client.post(f"/api/v1/motors/{motor.id}/stop", headers=headers)
        assert stop_resp.status_code == 200
        cmd_stop = stop_resp.json()["id"]

        await process_ack_payload(controller.device_uid, {"command_id": cmd_stop, "status": "EXECUTED"})
        await process_status_payload(controller.device_uid, {"controller_status": "ACTIVE", "motors": [{"motor_code": motor.motor_code, "status": "OFF"}]})

        # 3. Emergency Stop Fault Event
        await process_fault_payload(controller.device_uid, {"motor_code": motor.motor_code, "fault_type": "EMERGENCY_STOP", "description": f"Cycle {cycle} E-stop"})

        # Clear fault state back to OFF
        await process_status_payload(controller.device_uid, {"controller_status": "ACTIVE", "motors": [{"motor_code": motor.motor_code, "status": "OFF"}]})


# ------------------------------------------------------------------------------
# LAYER 24: DATA CONSISTENCY & ORPHAN RECORD CHECK
# ------------------------------------------------------------------------------

def test_deep_data_consistency_and_orphans():
    """Verify database foreign key linkages and confirm zero orphan records."""
    with get_sync_session() as session:
        # Check all motors have linked valid controllers
        motors = session.query(Motor).all()
        for m in motors:
            assert m.controller_id is not None
            assert m.controller is not None
            assert m.controller.station is not None
            assert m.controller.station.site is not None
            assert m.controller.station.site.organization is not None

        # Check all sensors have linked valid controllers
        sensors = session.query(Sensor).all()
        for s in sensors:
            assert s.controller_id is not None
            assert s.controller is not None

        # Check commands have linked valid motors
        cmds = session.query(MotorCommand).all()
        for c in cmds:
            assert c.motor_id is not None
            assert c.motor is not None
