import pytest
import uuid
from datetime import datetime, timezone, timedelta

from app.db.base import Base
from app.db.session import sync_engine, get_sync_session
from app.models.organization import Organization, OrganizationStatus
from app.models.site import Site, SiteStatus, SiteType
from app.models.station import Station, StationStatus, StationType
from app.models.controller import Controller, ControllerStatus, ControllerType
from app.models.motor import Motor, MotorStatus, MotorType
from app.models.sensor import Sensor, SensorStatus, SensorType
from app.models.motor_command import MotorCommand, CommandType, CommandStatus
from app.models.motor_event import MotorEvent, MotorEventType
from app.models.telemetry import TelemetryReading
from app.mqtt.client import MQTTMessage, MQTTClientService
from app.mqtt.router import mqtt_router
from app.mqtt.handlers import setup_mqtt_handlers
from app.mqtt.handlers.heartbeat_handler import process_heartbeat_payload
from app.mqtt.handlers.telemetry_handler import process_telemetry_payload
from app.mqtt.handlers.ack_handler import process_ack_payload
from app.mqtt.handlers.status_handler import process_status_payload
from app.mqtt.handlers.fault_handler import process_fault_payload


@pytest.fixture(scope="module", autouse=True)
def setup_tables():
    Base.metadata.create_all(bind=sync_engine)
    yield
    Base.metadata.drop_all(bind=sync_engine)


def helper_create_hierarchy(prefix: str):
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
            site_type=SiteType.HOME,
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

        controller = Controller(
            id=uuid.uuid4(),
            station_id=station.id,
            name=f"{prefix} Controller",
            controller_code=f"{prefix}_CTRL",
            device_uid=f"{prefix}-HW-UID",
            controller_type=ControllerType.ESP32,
            status=ControllerStatus.ACTIVE
        )
        session.add(controller)

        motor = Motor(
            id=uuid.uuid4(),
            controller_id=controller.id,
            name=f"{prefix} Pump 1",
            motor_code="PUMP_01",
            motor_type=MotorType.SUBMERSIBLE_PUMP,
            status=MotorStatus.OFF,
            rated_power=5.5
        )
        session.add(motor)

        sensor = Sensor(
            id=uuid.uuid4(),
            controller_id=controller.id,
            name=f"{prefix} Level Sensor",
            sensor_code="LEVEL_01",
            sensor_type=SensorType.WATER_LEVEL,
            status=SensorStatus.ACTIVE
        )
        session.add(sensor)

        session.commit()
        return org, site, station, controller, motor, sensor


@pytest.mark.asyncio
async def test_mqtt_heartbeat_handler():
    _, _, _, controller, _, _ = helper_create_hierarchy("HB_MQTT")

    payload = {
        "firmware_version": "v2.0.4",
        "ip_address": "10.0.0.45",
        "mac_address": "CC:DD:EE:FF:00:11",
        "status": "ACTIVE"
    }

    updated = await process_heartbeat_payload(controller.device_uid, payload)
    assert updated is not None
    assert updated.firmware_version == "v2.0.4"
    assert updated.ip_address == "10.0.0.45"
    assert updated.mac_address == "CC:DD:EE:FF:00:11"
    assert updated.last_seen_at is not None

    # Unknown device UID returns None
    assert await process_heartbeat_payload("UNKNOWN-UID", payload) is None


@pytest.mark.asyncio
async def test_mqtt_telemetry_handler_single_and_batch():
    _, _, _, controller, _, sensor = helper_create_hierarchy("TELEM_MQTT")

    # Single reading payload
    single_payload = {
        "sensor_code": "LEVEL_01",
        "value": 85.25,
        "unit": "%",
        "metadata": {"rssi": -70}
    }
    count = await process_telemetry_payload(controller.device_uid, single_payload)
    assert count == 1

    # Batch reading payload
    batch_payload = [
        {"sensor_code": "LEVEL_01", "value": 86.0, "unit": "%"},
        {"sensor_code": "LEVEL_01", "value": 86.5, "unit": "%"}
    ]
    batch_count = await process_telemetry_payload(controller.device_uid, batch_payload)
    assert batch_count == 2

    # Verify persisted readings in DB
    with get_sync_session() as session:
        readings = session.query(TelemetryReading).filter(TelemetryReading.sensor_id == sensor.id).all()
        assert len(readings) == 3

    # Unauthorized sensor code should be safely rejected
    invalid_sensor_payload = {"sensor_code": "NON_EXISTENT_SENSOR", "value": 10.0}
    rejected_count = await process_telemetry_payload(controller.device_uid, invalid_sensor_payload)
    assert rejected_count == 0


@pytest.mark.asyncio
async def test_mqtt_ack_handler_and_anti_spoofing():
    _, _, _, controller_a, motor_a, _ = helper_create_hierarchy("ACK_A")
    _, _, _, controller_b, _, _ = helper_create_hierarchy("ACK_B")

    # Create pending motor command for Motor A
    cmd_id = uuid.uuid4()
    with get_sync_session() as session:
        cmd = MotorCommand(
            id=cmd_id,
            motor_id=motor_a.id,
            command_type=CommandType.START,
            status=CommandStatus.PENDING,
            requested_at=datetime.now(timezone.utc)
        )
        session.add(cmd)
        session.commit()

    # Controller B tries to ACK command belonging to Controller A -> Spoofing rejected
    spoof_payload = {
        "command_id": str(cmd_id),
        "status": "EXECUTED"
    }
    res_spoof = await process_ack_payload(controller_b.device_uid, spoof_payload)
    assert res_spoof is None

    # Controller A legitimately ACKs command
    legit_payload = {
        "command_id": str(cmd_id),
        "status": "EXECUTED"
    }
    res_legit = await process_ack_payload(controller_a.device_uid, legit_payload)
    assert res_legit is not None
    assert res_legit.status == CommandStatus.EXECUTED
    assert res_legit.executed_at is not None


@pytest.mark.asyncio
async def test_mqtt_status_handler():
    _, _, _, controller, motor, _ = helper_create_hierarchy("STATUS_MQTT")

    payload = {
        "controller_status": "ACTIVE",
        "motors": [
            {"motor_code": "PUMP_01", "status": "ON"}
        ]
    }
    success = await process_status_payload(controller.device_uid, payload)
    assert success is True

    with get_sync_session() as session:
        refreshed_motor = session.get(Motor, motor.id)
        assert refreshed_motor.status == MotorStatus.ON


@pytest.mark.asyncio
async def test_mqtt_fault_handler():
    _, _, _, controller, motor, _ = helper_create_hierarchy("FAULT_MQTT")

    payload = {
        "motor_code": "PUMP_01",
        "fault_type": "EMERGENCY_STOP",
        "description": "Emergency stop button pressed locally",
        "payload": {"e_stop_pin": 15}
    }
    event = await process_fault_payload(controller.device_uid, payload)
    assert event is not None
    assert event.event_type == MotorEventType.EMERGENCY_STOP

    with get_sync_session() as session:
        refreshed_motor = session.get(Motor, motor.id)
        assert refreshed_motor.status == MotorStatus.FAULT


@pytest.mark.asyncio
async def test_end_to_end_mqtt_router_to_handlers():
    _, _, _, controller, _, sensor = helper_create_hierarchy("E2E_MQTT")

    # Send incoming MQTT telemetry message through the router
    topic = f"hydracontrol/devices/{controller.device_uid}/telemetry"
    payload_bytes = b'{"sensor_code": "LEVEL_01", "value": 91.3, "unit": "%"}'
    msg = MQTTMessage(topic=topic, payload=payload_bytes)

    routed = await mqtt_router.route_message(msg)
    assert routed is True

    # Verify that telemetry handler executed and saved to DB
    with get_sync_session() as session:
        saved = session.query(TelemetryReading).filter(TelemetryReading.sensor_id == sensor.id).all()
        assert any(float(r.value) == pytest.approx(91.3) for r in saved)
