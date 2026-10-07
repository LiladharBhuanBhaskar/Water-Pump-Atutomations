"""
HydraControl — P6-T03 ACK & Status Ingestion Tests
Verifies MQTT ACK handling, command lifecycle transitions, motor status updates,
MotorEvent creation on state changes, idempotency, anti-spoofing security, and error handling.
"""

import pytest
import uuid
from datetime import datetime, timezone
from app.db.base import Base
from app.db.session import sync_engine, get_sync_session
from app.models.organization import Organization, OrganizationStatus
from app.models.site import Site, SiteStatus, SiteType
from app.models.station import Station, StationStatus, StationType
from app.models.controller import Controller, ControllerStatus, ControllerType
from app.models.motor import Motor, MotorStatus, MotorType
from app.models.motor_command import MotorCommand, CommandType, CommandStatus
from app.models.motor_event import MotorEvent, MotorEventType, MotorEventSource
from app.mqtt.handlers.ack_handler import process_ack_payload
from app.mqtt.handlers.status_handler import process_status_payload


@pytest.fixture(scope="module", autouse=True)
def setup_tables():
    Base.metadata.create_all(bind=sync_engine)
    yield
    Base.metadata.drop_all(bind=sync_engine)


def helper_create_ack_setup(prefix: str):
    """Sets up a complete hierarchy with organization, site, station, controller, motor, and command."""
    with get_sync_session() as session:
        org = Organization(
            id=uuid.uuid4(),
            name=f"{prefix} Org",
            organization_code=f"{prefix}_ORG",
            status=OrganizationStatus.ACTIVE
        )
        session.add(org)

        site = Site(
            id=uuid.uuid4(),
            organization_id=org.id,
            name=f"{prefix} Site",
            site_code=f"{prefix}_SITE",
            site_type=SiteType.BUILDING,
            status=SiteStatus.ACTIVE
        )
        session.add(site)

        station = Station(
            id=uuid.uuid4(),
            site_id=site.id,
            name=f"{prefix} Station",
            station_code=f"{prefix}_STN",
            station_type=StationType.WATER_SUPPLY,
            status=StationStatus.ACTIVE
        )
        session.add(station)

        device_uid = f"{prefix}-HW-UID"
        controller = Controller(
            id=uuid.uuid4(),
            station_id=station.id,
            name=f"{prefix} Controller",
            controller_code=f"{prefix}_CTRL",
            device_uid=device_uid,
            controller_type=ControllerType.ESP32,
            status=ControllerStatus.ACTIVE
        )
        session.add(controller)

        motor = Motor(
            id=uuid.uuid4(),
            controller_id=controller.id,
            name=f"{prefix} Pump A",
            motor_code="M-PUMP-A",
            motor_type=MotorType.WATER_PUMP,
            status=MotorStatus.OFF
        )
        session.add(motor)

        command = MotorCommand(
            id=uuid.uuid4(),
            motor_id=motor.id,
            command_type=CommandType.START,
            status=CommandStatus.SENT,
            requested_at=datetime.now(timezone.utc),
            sent_at=datetime.now(timezone.utc)
        )
        session.add(command)
        session.commit()

        return {
            "org": org,
            "site": site,
            "station": station,
            "controller": controller,
            "motor": motor,
            "command": command,
            "device_uid": device_uid,
        }


@pytest.mark.asyncio
async def test_ack_acknowledged_success():
    """Valid ACK transitions command from SENT to ACKNOWLEDGED and populates acknowledged_at."""
    setup = helper_create_ack_setup("ACK_ACK")
    device_uid = setup["device_uid"]
    command = setup["command"]

    payload = {
        "command_id": str(command.id),
        "status": "ACKNOWLEDGED",
        "message": "Command received by device"
    }

    result = await process_ack_payload(device_uid, payload)
    assert result is not None
    assert result.status == CommandStatus.ACKNOWLEDGED
    assert result.acknowledged_at is not None

    with get_sync_session() as session:
        refreshed = session.get(MotorCommand, command.id)
        assert refreshed.status == CommandStatus.ACKNOWLEDGED


@pytest.mark.asyncio
async def test_ack_executed_success():
    """Valid EXECUTED ACK transitions command to EXECUTED and populates executed_at and acknowledged_at."""
    setup = helper_create_ack_setup("ACK_EXEC")
    device_uid = setup["device_uid"]
    command = setup["command"]

    payload = {
        "command_id": str(command.id),
        "status": "EXECUTED",
        "message": "Motor started successfully"
    }

    result = await process_ack_payload(device_uid, payload)
    assert result is not None
    assert result.status == CommandStatus.EXECUTED
    assert result.executed_at is not None
    assert result.acknowledged_at is not None


@pytest.mark.asyncio
async def test_ack_failed_success():
    """Valid FAILED ACK transitions command to FAILED and populates failed_at and error_message."""
    setup = helper_create_ack_setup("ACK_FAIL")
    device_uid = setup["device_uid"]
    command = setup["command"]

    payload = {
        "command_id": str(command.id),
        "status": "FAILED",
        "error_message": "Relay contactor failed to close"
    }

    result = await process_ack_payload(device_uid, payload)
    assert result is not None
    assert result.status == CommandStatus.FAILED
    assert result.failed_at is not None
    assert "Relay contactor failed to close" in result.error_message


@pytest.mark.asyncio
async def test_ack_idempotency_terminal_state_protection():
    """Repeated or delayed ACK does not overwrite an already EXECUTED command."""
    setup = helper_create_ack_setup("ACK_IDEM")
    device_uid = setup["device_uid"]
    command = setup["command"]

    # 1. First ACK marks EXECUTED
    payload_exec = {
        "command_id": str(command.id),
        "status": "EXECUTED"
    }
    await process_ack_payload(device_uid, payload_exec)

    # 2. Delayed ACK received afterwards with status ACKNOWLEDGED
    payload_ack = {
        "command_id": str(command.id),
        "status": "ACKNOWLEDGED"
    }
    await process_ack_payload(device_uid, payload_ack)

    # Verify status is still EXECUTED
    with get_sync_session() as session:
        refreshed = session.get(MotorCommand, command.id)
        assert refreshed.status == CommandStatus.EXECUTED


@pytest.mark.asyncio
async def test_ack_security_device_mismatch_rejected():
    """Device attempting to ACK a command for another controller is rejected."""
    setup = helper_create_ack_setup("ACK_SPOOF")
    command = setup["command"]
    other_device_uid = "esp32-spoof-999"

    payload = {
        "command_id": str(command.id),
        "status": "EXECUTED"
    }

    result = await process_ack_payload(other_device_uid, payload)
    assert result is None


@pytest.mark.asyncio
async def test_ack_unknown_command():
    """ACK for non-existent command UUID is handled safely and returns None."""
    fake_device_uid = "esp32-fake-uid"
    fake_uuid = str(uuid.uuid4())

    payload = {
        "command_id": fake_uuid,
        "status": "ACKNOWLEDGED"
    }

    result = await process_ack_payload(fake_device_uid, payload)
    assert result is None


@pytest.mark.asyncio
async def test_ack_malformed_payload():
    """Malformed ACK payload without dict or invalid UUID is safely rejected."""
    fake_device_uid = "esp32-fake-uid"

    assert await process_ack_payload(fake_device_uid, "not a dict") is None
    assert await process_ack_payload(fake_device_uid, {"command_id": "not-a-uuid"}) is None
    assert await process_ack_payload(fake_device_uid, {}) is None


@pytest.mark.asyncio
async def test_status_ingestion_updates_motor_and_creates_event():
    """Status payload transitions motor state to ON and creates a MotorEvent (STARTED)."""
    setup = helper_create_ack_setup("STAT_START")
    device_uid = setup["device_uid"]
    motor = setup["motor"]

    payload = {
        "controller_status": "ACTIVE",
        "motors": [
            {
                "motor_code": "M-PUMP-A",
                "status": "ON",
                "voltage": 230.5
            }
        ]
    }

    success = await process_status_payload(device_uid, payload)
    assert success is True

    with get_sync_session() as session:
        refreshed_motor = session.get(Motor, motor.id)
        assert refreshed_motor.status == MotorStatus.ON

        events = session.query(MotorEvent).filter(MotorEvent.motor_id == motor.id).all()
        assert len(events) == 1
        assert events[0].event_type == MotorEventType.STARTED
        assert events[0].source == MotorEventSource.CONTROLLER


@pytest.mark.asyncio
async def test_status_ingestion_stopped_and_fault_events():
    """Status payload transitions motor to STOPPED and FAULT with appropriate MotorEvents."""
    setup = helper_create_ack_setup("STAT_EVENTS")
    device_uid = setup["device_uid"]
    motor = setup["motor"]

    # 1. Turn ON
    await process_status_payload(device_uid, {"motors": [{"motor_code": "M-PUMP-A", "status": "ON"}]})

    # 2. Turn OFF (STOPPED event)
    await process_status_payload(device_uid, {"motors": [{"motor_code": "M-PUMP-A", "status": "OFF"}]})

    # 3. Trigger FAULT (FAULT event)
    await process_status_payload(device_uid, {"motors": [{"motor_code": "M-PUMP-A", "status": "FAULT"}]})

    with get_sync_session() as session:
        events = session.query(MotorEvent).filter(MotorEvent.motor_id == motor.id).order_by(MotorEvent.created_at.asc()).all()
        assert len(events) == 3
        assert events[0].event_type == MotorEventType.STARTED
        assert events[1].event_type == MotorEventType.STOPPED
        assert events[2].event_type == MotorEventType.FAULT


@pytest.mark.asyncio
async def test_status_ingestion_duplicate_status_no_extra_event():
    """Repeated identical status report does not create duplicate events."""
    setup = helper_create_ack_setup("STAT_DUP")
    device_uid = setup["device_uid"]
    motor = setup["motor"]

    payload = {"motors": [{"motor_code": "M-PUMP-A", "status": "ON"}]}

    # Process twice
    await process_status_payload(device_uid, payload)
    await process_status_payload(device_uid, payload)

    with get_sync_session() as session:
        events = session.query(MotorEvent).filter(MotorEvent.motor_id == motor.id).all()
        assert len(events) == 1


@pytest.mark.asyncio
async def test_status_ingestion_unknown_device_rejected():
    """Status update from unprovisioned device returns False and is safely rejected."""
    fake_device_uid = f"esp32-unknown-{uuid.uuid4().hex[:8]}"
    payload = {"status": "ACTIVE"}

    success = await process_status_payload(fake_device_uid, payload)
    assert success is False
