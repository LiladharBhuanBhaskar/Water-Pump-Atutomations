"""End-to-end integration tests for Wave 2C Safety Integration (Phases 12-15)."""

import uuid
from datetime import datetime, timezone
import pytest
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.db.session import AsyncSessionLocal, sync_engine, get_sync_session
from app.db.base import Base
from app.models.user import User, UserRole
from app.models.organization import Organization, OrganizationStatus
from app.models.site import Site, SiteStatus, SiteType
from app.models.station import Station, StationStatus, StationType
from app.models.settings import StationSettings
from app.models.controller import Controller, ControllerStatus, ControllerType
from app.models.motor import Motor, MotorStatus, MotorType
from app.models.sensor import Sensor, SensorStatus, SensorType
from app.models.telemetry import TelemetryReading
from app.models.motor_event import MotorEvent, MotorEventType
from app.models.motor_command import CommandType
from app.mqtt.handlers.telemetry_handler import process_telemetry_payload
from app.services.command_service import dispatch_motor_command, MotorCommandValidationException
from app.core.security import get_password_hash


@pytest.fixture(scope="module", autouse=True)
def setup_tables():
    Base.metadata.create_all(bind=sync_engine)
    yield
    Base.metadata.drop_all(bind=sync_engine)


def helper_create_test_environment():
    """Creates a full physical hierarchy for testing safety integration."""
    org_id = uuid.uuid4()
    site_id = uuid.uuid4()
    station_id = uuid.uuid4()
    ctrl_id = uuid.uuid4()
    motor_id = uuid.uuid4()
    uid = f"ESP32_SAFE_{uuid.uuid4().hex[:6].upper()}"

    with get_sync_session() as session:
        org = Organization(id=org_id, name="Safe Org", organization_code=f"SO_{uuid.uuid4().hex[:4].upper()}", status=OrganizationStatus.ACTIVE)
        site = Site(id=site_id, organization_id=org_id, name="Safe Site", site_code=f"SS_{uuid.uuid4().hex[:4].upper()}", site_type=SiteType.HOME, status=SiteStatus.ACTIVE)
        station = Station(id=station_id, site_id=site_id, name="Safe Station", station_code=f"ST_{uuid.uuid4().hex[:4].upper()}", station_type=StationType.HOME_PUMP, status=StationStatus.ACTIVE)
        settings = StationSettings(id=uuid.uuid4(), station_id=station_id, auto_stop_on_tank_full=True, water_level_threshold=95.0, turbidity_threshold=15.0)
        ctrl = Controller(id=ctrl_id, station_id=station_id, name="Safe Controller", controller_code="CTRL_S", device_uid=uid, controller_type=ControllerType.ESP32, status=ControllerStatus.ACTIVE)
        motor = Motor(id=motor_id, controller_id=ctrl_id, name="Main Pump", motor_code="PUMP1", motor_type=MotorType.SUBMERSIBLE_PUMP, status=MotorStatus.ON, rated_power=3.7)

        # Sensors
        s_level = Sensor(id=uuid.uuid4(), controller_id=ctrl_id, name="Overhead Tank", sensor_code="LVL_OH", sensor_type=SensorType.WATER_LEVEL, status=SensorStatus.ACTIVE)
        s_sump = Sensor(id=uuid.uuid4(), controller_id=ctrl_id, name="Sump Level", sensor_code="LVL_SUMP", sensor_type=SensorType.WATER_LEVEL, status=SensorStatus.ACTIVE)
        s_turb = Sensor(id=uuid.uuid4(), controller_id=ctrl_id, name="Turbidity", sensor_code="TURB_01", sensor_type=SensorType.TURBIDITY, status=SensorStatus.ACTIVE)
        s_flow = Sensor(id=uuid.uuid4(), controller_id=ctrl_id, name="Flow Rate", sensor_code="FLOW_01", sensor_type=SensorType.FLOW, status=SensorStatus.ACTIVE)
        s_curr = Sensor(id=uuid.uuid4(), controller_id=ctrl_id, name="Current", sensor_code="CURR_01", sensor_type=SensorType.CURRENT, status=SensorStatus.ACTIVE)
        s_volt = Sensor(id=uuid.uuid4(), controller_id=ctrl_id, name="Voltage", sensor_code="VOLT_01", sensor_type=SensorType.VOLTAGE, status=SensorStatus.ACTIVE)

        user_id = uuid.uuid4()
        user = User(id=user_id, email=f"user_{uuid.uuid4().hex[:6]}@test.com", password_hash=get_password_hash("pass"), name="Safe User", role=UserRole.ORGANIZATION_ADMIN, organization_id=org_id, is_active=True)

        session.add_all([org, site, station, settings, ctrl, motor, s_level, s_sump, s_turb, s_flow, s_curr, s_volt, user])
        session.commit()

    return {
        "org_id": org_id,
        "site_id": site_id,
        "station_id": station_id,
        "controller_id": ctrl_id,
        "device_uid": uid,
        "motor_id": motor_id,
        "user_id": user_id,
    }


@pytest.mark.asyncio
async def test_tank_full_auto_stop_integration():
    env = helper_create_test_environment()
    uid = env["device_uid"]
    motor_id = env["motor_id"]

    # Ingest 96% tank level
    payload = {
        "sensor_code": "LVL_OH",
        "value": 96.0,
        "unit": "%",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
    }
    saved = await process_telemetry_payload(uid, payload)
    assert saved == 1

    # Check motor transitioned to STOPPING / OFF
    async with AsyncSessionLocal() as session:
        res = await session.execute(select(Motor).where(Motor.id == motor_id))
        motor = res.scalar_one()
        assert motor.status in (MotorStatus.STOPPING, MotorStatus.OFF)

        # Check MotorEvent record
        res_ev = await session.execute(select(MotorEvent).where(MotorEvent.motor_id == motor_id))
        events = res_ev.scalars().all()
        assert any(e.event_type == MotorEventType.STOPPED for e in events)



@pytest.mark.asyncio
async def test_sump_depleted_dry_run_trip():
    env = helper_create_test_environment()
    uid = env["device_uid"]
    motor_id = env["motor_id"]

    # Ingest 5% sump level (<= 10% cutoff)
    payload = {
        "sensor_code": "LVL_SUMP",
        "value": 5.0,
        "unit": "%",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
    }
    saved = await process_telemetry_payload(uid, payload)
    assert saved == 1

    # Check motor transitioned to FAULT
    async with AsyncSessionLocal() as session:
        res = await session.execute(select(Motor).where(Motor.id == motor_id))
        motor = res.scalar_one()
        assert motor.status == MotorStatus.FAULT


@pytest.mark.asyncio
async def test_turbidity_safety_rejection_and_running_trip():
    env = helper_create_test_environment()
    uid = env["device_uid"]
    motor_id = env["motor_id"]
    user_id = env["user_id"]
    org_id = env["org_id"]

    # 1. Ingest severe contamination (>25 NTU)
    payload = {
        "sensor_code": "TURB_01",
        "value": 35.0,
        "unit": "NTU",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
    }
    await process_telemetry_payload(uid, payload)

    # 2. Running motor should have tripped to FAULT
    async with AsyncSessionLocal() as session:
        res = await session.execute(select(Motor).where(Motor.id == motor_id))
        motor = res.scalar_one()
        assert motor.status == MotorStatus.FAULT

        # Set motor to OFF to test pre-start rejection
        motor.status = MotorStatus.OFF
        session.add(motor)
        await session.commit()

        # 3. Attempt START command - should be rejected with exception
        with pytest.raises(MotorCommandValidationException) as exc_info:
            await dispatch_motor_command(
                session=session,
                motor_id=motor_id,
                command_type=CommandType.START,
                user_id=user_id,
                current_user_org_id=org_id,
            )
        assert "turbidity" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_flow_dry_run_trip():
    env = helper_create_test_environment()
    uid = env["device_uid"]
    motor_id = env["motor_id"]

    # Ingest 0.0 L/min flow on running pump
    payload = {
        "sensor_code": "FLOW_01",
        "value": 0.0,
        "unit": "L/min",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
    }
    saved = await process_telemetry_payload(uid, payload)
    assert saved == 1

    # Motor must trip to FAULT
    async with AsyncSessionLocal() as session:
        res = await session.execute(select(Motor).where(Motor.id == motor_id))
        motor = res.scalar_one()
        assert motor.status == MotorStatus.FAULT


@pytest.mark.asyncio
async def test_electrical_overcurrent_trip():
    env = helper_create_test_environment()
    uid = env["device_uid"]
    motor_id = env["motor_id"]

    # Ingest 15.0A current (>12.0A overload)
    payload = {
        "sensor_code": "CURR_01",
        "value": 15.0,
        "unit": "A",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
    }
    saved = await process_telemetry_payload(uid, payload)
    assert saved == 1

    # Motor must trip to FAULT
    async with AsyncSessionLocal() as session:
        res = await session.execute(select(Motor).where(Motor.id == motor_id))
        motor = res.scalar_one()
        assert motor.status == MotorStatus.FAULT
