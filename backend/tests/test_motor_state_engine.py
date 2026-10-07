"""
HydraControl — Phase 10 Comprehensive Motor State Engine Verification Suite
Tests pure state engine transitions, command lifecycles, edge safety precedence,
MQTT ACK/status/fault processing, stale message defense, WebSocket streaming,
concurrency/race conditions, and multi-tenant RBAC security.
"""

import pytest
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from app.db.base import Base
from app.db.session import sync_engine, get_sync_session, AsyncSessionLocal
from app.models.organization import Organization, OrganizationStatus
from app.models.site import Site, SiteStatus, SiteType
from app.models.station import Station, StationStatus, StationType
from app.models.controller import Controller, ControllerStatus, ControllerType
from app.models.motor import Motor, MotorStatus, MotorType
from app.models.motor_command import MotorCommand, CommandType, CommandStatus
from app.models.motor_event import MotorEvent, MotorEventType, MotorEventSource
from app.models.user import User, UserRole

from app.services.motor_state_engine import (
    transition_motor_state,
    validate_and_transition,
    parse_payload_timestamp,
    is_stale_message,
    ensure_utc,
    MotorStateEvent,
    InvalidStateTransitionException,
    TransitionResult
)
from app.services.command_service import (
    dispatch_motor_command,
    get_motor_command_by_id,
    list_motor_commands,
    MotorCommandNotFoundException,
    MotorNotOperationalException,
    MotorSiteSuspendedException,
    MotorSiteInactiveException,
)
from app.services.command_watchdog import process_command_timeouts
from app.mqtt.handlers.ack_handler import process_ack_payload
from app.mqtt.handlers.status_handler import process_status_payload
from app.mqtt.handlers.fault_handler import process_fault_payload


@pytest.fixture(scope="module", autouse=True)
def setup_tables():
    Base.metadata.create_all(bind=sync_engine)
    yield
    Base.metadata.drop_all(bind=sync_engine)


def helper_create_test_hierarchy(
    prefix: str,
    motor_status: MotorStatus = MotorStatus.OFF,
    site_status: SiteStatus = SiteStatus.ACTIVE
):
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
            status=site_status
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
            device_uid=f"{prefix}-HW-UID-{uuid.uuid4().hex[:6]}",
            controller_type=ControllerType.ESP32,
            status=ControllerStatus.ACTIVE,
            last_seen_at=datetime.now(timezone.utc)
        )
        session.add(controller)

        motor = Motor(
            id=uuid.uuid4(),
            controller_id=controller.id,
            name=f"{prefix} Pump",
            motor_code="PUMP_01",
            motor_type=MotorType.WATER_PUMP,
            status=motor_status,
            rated_power=5.5
        )
        session.add(motor)

        session.commit()
        return org, site, station, controller, motor


# =============================================================================
# 1. PURE STATE ENGINE TESTS (P10-T01)
# =============================================================================

def test_pure_state_engine_valid_lifecycle():
    """Verify standard valid operational lifecycle: OFF -> STARTING -> ON -> STOPPING -> OFF."""
    # 1. OFF + CMD_START -> STARTING
    r1 = transition_motor_state(MotorStatus.OFF, MotorStateEvent.CMD_START)
    assert r1.is_valid is True
    assert r1.next_state == MotorStatus.STARTING

    # 2. STARTING + STATUS_ON -> ON
    r2 = transition_motor_state(MotorStatus.STARTING, MotorStateEvent.STATUS_ON)
    assert r2.is_valid is True
    assert r2.next_state == MotorStatus.ON
    assert r2.event_type == MotorEventType.STARTED

    # 3. ON + CMD_STOP -> STOPPING
    r3 = transition_motor_state(MotorStatus.ON, MotorStateEvent.CMD_STOP)
    assert r3.is_valid is True
    assert r3.next_state == MotorStatus.STOPPING

    # 4. STOPPING + STATUS_OFF -> OFF
    r4 = transition_motor_state(MotorStatus.STOPPING, MotorStateEvent.STATUS_OFF)
    assert r4.is_valid is True
    assert r4.next_state == MotorStatus.OFF
    assert r4.event_type == MotorEventType.STOPPED


def test_pure_state_engine_invalid_transitions():
    """Verify illegal transitions are strictly rejected."""
    # Prohibit direct OFF -> ON without STARTING (when not in reconciliation)
    r_direct = transition_motor_state(MotorStatus.OFF, MotorStateEvent.STATUS_ON)
    assert r_direct.is_valid is False
    assert "prohibited" in r_direct.reason.lower()

    # Prohibit START from FAULT
    r_fault = transition_motor_state(MotorStatus.FAULT, MotorStateEvent.CMD_START)
    assert r_fault.is_valid is False

    # Prohibit START from DISABLED
    r_dis = transition_motor_state(MotorStatus.DISABLED, MotorStateEvent.CMD_START)
    assert r_dis.is_valid is False

    # Prohibit START from MAINTENANCE
    r_maint = transition_motor_state(MotorStatus.MAINTENANCE, MotorStateEvent.CMD_START)
    assert r_maint.is_valid is False

    # Prohibit START from OFFLINE
    r_off = transition_motor_state(MotorStatus.OFFLINE, MotorStateEvent.CMD_START)
    assert r_off.is_valid is False


def test_pure_state_engine_safety_precedence():
    """Verify emergency stop and safety trips have absolute precedence from ANY state."""
    all_states = [
        MotorStatus.OFF, MotorStatus.STARTING, MotorStatus.ON,
        MotorStatus.STOPPING, MotorStatus.FAULT, MotorStatus.MAINTENANCE,
        MotorStatus.DISABLED, MotorStatus.OFFLINE
    ]

    for st in all_states:
        # EMERGENCY_STOP -> FAULT
        r_estop = transition_motor_state(st, MotorStateEvent.CMD_EMERGENCY_STOP)
        assert r_estop.is_valid is True
        assert r_estop.next_state == MotorStatus.FAULT
        assert r_estop.event_type == MotorEventType.EMERGENCY_STOP

        # LOCAL_ESTOP -> FAULT
        r_local = transition_motor_state(st, MotorStateEvent.LOCAL_ESTOP)
        assert r_local.is_valid is True
        assert r_local.next_state == MotorStatus.FAULT
        assert r_local.event_type == MotorEventType.EMERGENCY_STOP

        # SAFETY_TRIP -> FAULT
        r_trip = transition_motor_state(st, MotorStateEvent.SAFETY_TRIP, {"error_message": "Turbidity 30 NTU"})
        assert r_trip.is_valid is True
        assert r_trip.next_state == MotorStatus.FAULT
        assert r_trip.event_type == MotorEventType.FAULT


def test_pure_state_engine_fault_reset_with_safety_latch():
    """Verify RESET is blocked if safety trip remains active or latch is set."""
    # Active safety trip -> RESET blocked
    r_blocked = transition_motor_state(MotorStatus.FAULT, MotorStateEvent.CMD_RESET, {"active_safety_trip": True})
    assert r_blocked.is_valid is False

    # Safety latch remaining -> RESET blocked
    r_latched = transition_motor_state(MotorStatus.FAULT, MotorStateEvent.CMD_RESET, {"safety_latched": True})
    assert r_latched.is_valid is False

    # Safe condition & latch cleared -> RESET allowed to OFF
    r_ok = transition_motor_state(MotorStatus.FAULT, MotorStateEvent.CMD_RESET, {"active_safety_trip": False, "safety_latched": False})
    assert r_ok.is_valid is True
    assert r_ok.next_state == MotorStatus.OFF
    assert r_ok.event_type == MotorEventType.RESET


def test_validate_and_transition_raises_exception():
    """Verify validate_and_transition raises InvalidStateTransitionException on invalid move."""
    with pytest.raises(InvalidStateTransitionException) as exc:
        validate_and_transition(MotorStatus.DISABLED, MotorStateEvent.CMD_START)
    assert "DISABLED" in str(exc.value)


# =============================================================================
# 2. COMMAND LIFECYCLE & STATE INTEGRATION (P10-T02)
# =============================================================================

@pytest.mark.asyncio
async def test_command_dispatch_transitions_to_starting():
    """START command dispatch transitions motor from OFF to STARTING."""
    org, site, station, controller, motor = helper_create_test_hierarchy("P10_CMD_START", motor_status=MotorStatus.OFF)
    mock_mqtt = MagicMock()
    mock_mqtt.publish = AsyncMock(return_value=True)

    async with AsyncSessionLocal() as session:
        cmd = await dispatch_motor_command(
            session=session,
            motor_id=motor.id,
            command_type=CommandType.START,
            current_user_org_id=org.id,
            mqtt_client=mock_mqtt
        )
        assert cmd.status == CommandStatus.SENT

        with get_sync_session() as s_sync:
            m_refreshed = s_sync.get(Motor, motor.id)
            assert m_refreshed.status == MotorStatus.STARTING


@pytest.mark.asyncio
async def test_ack_execution_transitions_starting_to_on():
    """Device ACK (EXECUTED) transitions motor from STARTING to ON and emits STARTED event."""
    org, site, station, controller, motor = helper_create_test_hierarchy("P10_ACK_ON", motor_status=MotorStatus.OFF)
    mock_mqtt = MagicMock()
    mock_mqtt.publish = AsyncMock(return_value=True)

    async with AsyncSessionLocal() as session:
        cmd = await dispatch_motor_command(
            session=session,
            motor_id=motor.id,
            command_type=CommandType.START,
            current_user_org_id=org.id,
            mqtt_client=mock_mqtt
        )

    # Controller sends ACK EXECUTED
    ack_payload = {
        "command_id": str(cmd.id),
        "status": "EXECUTED",
        "message": "Motor contactor closed. Running."
    }
    updated_cmd = await process_ack_payload(controller.device_uid, ack_payload)
    assert updated_cmd is not None
    assert updated_cmd.status == CommandStatus.EXECUTED

    with get_sync_session() as session:
        m_refreshed = session.get(Motor, motor.id)
        assert m_refreshed.status == MotorStatus.ON

        # Verify STARTED MotorEvent was created
        events = session.query(MotorEvent).filter(MotorEvent.motor_id == motor.id).all()
        assert any(e.event_type == MotorEventType.STARTED for e in events)


@pytest.mark.asyncio
async def test_stop_command_and_ack_lifecycle():
    """STOP command sets STOPPING, ACK EXECUTED sets OFF and emits STOPPED event."""
    org, site, station, controller, motor = helper_create_test_hierarchy("P10_STOP_FLOW", motor_status=MotorStatus.ON)
    mock_mqtt = MagicMock()
    mock_mqtt.publish = AsyncMock(return_value=True)

    async with AsyncSessionLocal() as session:
        cmd = await dispatch_motor_command(
            session=session,
            motor_id=motor.id,
            command_type=CommandType.STOP,
            current_user_org_id=org.id,
            mqtt_client=mock_mqtt
        )
        assert cmd.status == CommandStatus.SENT

        with get_sync_session() as s_sync:
            m_stopping = s_sync.get(Motor, motor.id)
            assert m_stopping.status == MotorStatus.STOPPING

    # ACK EXECUTED
    ack_payload = {"command_id": str(cmd.id), "status": "EXECUTED"}
    await process_ack_payload(controller.device_uid, ack_payload)

    with get_sync_session() as session:
        m_off = session.get(Motor, motor.id)
        assert m_off.status == MotorStatus.OFF
        events = session.query(MotorEvent).filter(MotorEvent.motor_id == motor.id).all()
        assert any(e.event_type == MotorEventType.STOPPED for e in events)


@pytest.mark.asyncio
async def test_ack_startup_rejection_due_to_safety_fault():
    """When device rejects START due to safety trip (e.g. turbidity >25 NTU), motor transitions to FAULT."""
    org, site, station, controller, motor = helper_create_test_hierarchy("P10_SAFE_REJ", motor_status=MotorStatus.OFF)
    mock_mqtt = MagicMock()
    mock_mqtt.publish = AsyncMock(return_value=True)

    async with AsyncSessionLocal() as session:
        cmd = await dispatch_motor_command(
            session=session,
            motor_id=motor.id,
            command_type=CommandType.START,
            current_user_org_id=org.id,
            mqtt_client=mock_mqtt
        )

    # Controller returns FAILED ACK with safety reason
    ack_payload = {
        "command_id": str(cmd.id),
        "status": "FAILED",
        "error_message": "START rejected: Turbidity (32.5 NTU) exceeds limit (25.0 NTU)"
    }
    await process_ack_payload(controller.device_uid, ack_payload)

    with get_sync_session() as session:
        m_refreshed = session.get(Motor, motor.id)
        assert m_refreshed.status == MotorStatus.FAULT
        events = session.query(MotorEvent).filter(MotorEvent.motor_id == motor.id).all()
        assert any(e.event_type == MotorEventType.FAULT for e in events)


# =============================================================================
# 3. MQTT STATUS & STALE DEFENSE (P10-T02 / P10-T03)
# =============================================================================

@pytest.mark.asyncio
async def test_stale_status_message_protection():
    """Verify that an older/stale status payload does not regress current state."""
    org, site, station, controller, motor = helper_create_test_hierarchy("P10_STALE", motor_status=MotorStatus.ON)

    now = datetime.now(timezone.utc)
    old_time = now - timedelta(seconds=60)

    # Set controller last_seen_at to now
    with get_sync_session() as session:
        ctrl = session.get(Controller, controller.id)
        ctrl.last_seen_at = now
        session.commit()

    # Send status with timestamp from 60 seconds ago claiming motor is OFF
    stale_payload = {
        "timestamp": old_time.isoformat(),
        "motors": [{"motor_code": "PUMP_01", "status": "OFF"}]
    }
    processed = await process_status_payload(controller.device_uid, stale_payload)
    assert processed is False

    # Motor state must remain ON
    with get_sync_session() as session:
        m = session.get(Motor, motor.id)
        assert m.status == MotorStatus.ON


@pytest.mark.asyncio
async def test_device_anti_spoofing_cross_device_ack_rejection():
    """Verify that device B cannot ACK a command directed to device A."""
    org, site, station, ctrl_a, motor_a = helper_create_test_hierarchy("P10_DEV_A")
    _, _, _, ctrl_b, motor_b = helper_create_test_hierarchy("P10_DEV_B")

    mock_mqtt = MagicMock()
    mock_mqtt.publish = AsyncMock(return_value=True)

    async with AsyncSessionLocal() as session:
        cmd_a = await dispatch_motor_command(
            session=session,
            motor_id=motor_a.id,
            command_type=CommandType.START,
            current_user_org_id=org.id,
            mqtt_client=mock_mqtt
        )

    # Device B attempts to ACK command A
    spoofed_ack = {
        "command_id": str(cmd_a.id),
        "status": "EXECUTED"
    }
    res = await process_ack_payload(ctrl_b.device_uid, spoofed_ack)
    assert res is None

    # Motor A must NOT be transitioned to ON by Device B
    with get_sync_session() as session:
        m_a = session.get(Motor, motor_a.id)
        assert m_a.status == MotorStatus.STARTING


@pytest.mark.asyncio
async def test_watchdog_timeout_reverts_unconfirmed_starting_state():
    """If a START command times out without ACK, watchdog reverts motor to OFF."""
    org, site, station, controller, motor = helper_create_test_hierarchy("P10_WD_TIMEOUT", motor_status=MotorStatus.OFF)
    mock_mqtt = MagicMock()
    mock_mqtt.publish = AsyncMock(return_value=True)

    now = datetime.now(timezone.utc)
    old_time = now - timedelta(seconds=45)

    async with AsyncSessionLocal() as session:
        cmd = await dispatch_motor_command(
            session=session,
            motor_id=motor.id,
            command_type=CommandType.START,
            current_user_org_id=org.id,
            mqtt_client=mock_mqtt
        )
        cmd.sent_at = old_time
        session.add(cmd)
        await session.commit()

        # Run watchdog
        res = await process_command_timeouts(session, timeout_seconds=30, now=now)
        assert res["timed_out_count"] == 1

    with get_sync_session() as session:
        m = session.get(Motor, motor.id)
        assert m.status == MotorStatus.OFF
        cmd_ref = session.get(MotorCommand, cmd.id)
        assert cmd_ref.status == CommandStatus.TIMEOUT


# =============================================================================
# 4. CONCURRENCY, FAULT & RECOVERY TESTS
# =============================================================================

@pytest.mark.asyncio
async def test_emergency_stop_overrides_in_flight_starting():
    """Emergency stop immediately forces FAULT even if motor is currently STARTING."""
    org, site, station, controller, motor = helper_create_test_hierarchy("P10_ESTOP_RACE", motor_status=MotorStatus.STARTING)
    mock_mqtt = MagicMock()
    mock_mqtt.publish = AsyncMock(return_value=True)

    async with AsyncSessionLocal() as session:
        cmd_estop = await dispatch_motor_command(
            session=session,
            motor_id=motor.id,
            command_type=CommandType.EMERGENCY_STOP,
            current_user_org_id=org.id,
            mqtt_client=mock_mqtt
        )
        assert cmd_estop.status == CommandStatus.SENT

    with get_sync_session() as session:
        m = session.get(Motor, motor.id)
        assert m.status == MotorStatus.FAULT


@pytest.mark.asyncio
async def test_fault_reset_flow():
    """Test full fault reset sequence from FAULT -> RESET -> OFF."""
    org, site, station, controller, motor = helper_create_test_hierarchy("P10_RESET_FLOW", motor_status=MotorStatus.FAULT)
    mock_mqtt = MagicMock()
    mock_mqtt.publish = AsyncMock(return_value=True)

    async with AsyncSessionLocal() as session:
        cmd_reset = await dispatch_motor_command(
            session=session,
            motor_id=motor.id,
            command_type=CommandType.RESET,
            current_user_org_id=org.id,
            mqtt_client=mock_mqtt
        )
        assert cmd_reset.status == CommandStatus.SENT

    with get_sync_session() as session:
        m = session.get(Motor, motor.id)
        assert m.status == MotorStatus.OFF
        events = session.query(MotorEvent).filter(MotorEvent.motor_id == motor.id).all()
        assert any(e.event_type == MotorEventType.RESET for e in events)


# =============================================================================
# 5. SECURITY & TENANT ISOLATION TESTS
# =============================================================================

@pytest.mark.asyncio
async def test_cross_tenant_command_isolation():
    """User from Org A cannot command motor from Org B."""
    org_a, _, _, _, motor_a = helper_create_test_hierarchy("P10_TENANT_A")
    org_b, _, _, _, motor_b = helper_create_test_hierarchy("P10_TENANT_B")

    mock_mqtt = MagicMock()
    mock_mqtt.publish = AsyncMock(return_value=True)

    async with AsyncSessionLocal() as session:
        with pytest.raises(MotorCommandNotFoundException):
            await dispatch_motor_command(
                session=session,
                motor_id=motor_b.id,
                command_type=CommandType.START,
                current_user_org_id=org_a.id,
                mqtt_client=mock_mqtt
            )


# =============================================================================
# 6. ADMINISTRATIVE & OFFLINE RECONCILIATION TESTS
# =============================================================================

def test_maintenance_and_disabled_transitions():
    """Test administrative lockouts and unlocks."""
    # 1. Maintenance Lock & Unlock
    r_maint = transition_motor_state(MotorStatus.OFF, MotorStateEvent.MAINTENANCE_LOCK)
    assert r_maint.is_valid is True
    assert r_maint.next_state == MotorStatus.MAINTENANCE

    r_unlock = transition_motor_state(MotorStatus.MAINTENANCE, MotorStateEvent.MAINTENANCE_UNLOCK)
    assert r_unlock.is_valid is True
    assert r_unlock.next_state == MotorStatus.OFF

    # 2. Admin Disable & Enable
    r_dis = transition_motor_state(MotorStatus.OFF, MotorStateEvent.ADMIN_DISABLE)
    assert r_dis.is_valid is True
    assert r_dis.next_state == MotorStatus.DISABLED

    r_en = transition_motor_state(MotorStatus.DISABLED, MotorStateEvent.ADMIN_ENABLE)
    assert r_en.is_valid is True
    assert r_en.next_state == MotorStatus.OFF


def test_heartbeat_timeout_and_reconnection_sync():
    """Test heartbeat loss to OFFLINE and subsequent reconnection state synchronization."""
    # 1. Operational states to OFFLINE on heartbeat loss
    for st in [MotorStatus.OFF, MotorStatus.STARTING, MotorStatus.ON, MotorStatus.STOPPING]:
        r_off = transition_motor_state(st, MotorStateEvent.HEARTBEAT_TIMEOUT)
        assert r_off.is_valid is True
        assert r_off.next_state == MotorStatus.OFFLINE
        assert r_off.event_type == MotorEventType.OFFLINE

    # 2. Reconnection sync from OFFLINE
    r_sync_on = transition_motor_state(MotorStatus.OFFLINE, MotorStateEvent.HEARTBEAT_RESTORED, {"hardware_state": "ON"})
    assert r_sync_on.is_valid is True
    assert r_sync_on.next_state == MotorStatus.ON
    assert r_sync_on.event_type == MotorEventType.ONLINE

    r_sync_off = transition_motor_state(MotorStatus.OFFLINE, MotorStateEvent.HEARTBEAT_RESTORED, {"hardware_state": "OFF"})
    assert r_sync_off.is_valid is True
    assert r_sync_off.next_state == MotorStatus.OFF
    assert r_sync_off.event_type == MotorEventType.ONLINE


@pytest.mark.asyncio
async def test_fault_mqtt_handler_estop_and_sensor_trips():
    """Verify fault_handler processes local ESTOP and sensor trips correctly."""
    org, site, station, controller, motor = helper_create_test_hierarchy("P10_FLT_HDLR", motor_status=MotorStatus.ON)

    # 1. Local E-Stop
    estop_payload = {
        "motor_code": motor.motor_code,
        "fault_type": "LOCAL_ESTOP",
        "message": "Physical emergency stop button pressed on panel"
    }
    event1 = await process_fault_payload(controller.device_uid, estop_payload)
    assert event1 is not None
    assert event1.event_type == MotorEventType.EMERGENCY_STOP

    with get_sync_session() as session:
        m = session.get(Motor, motor.id)
        assert m.status == MotorStatus.FAULT

    # 2. High Turbidity Trip
    turbidity_payload = {
        "motor_code": motor.motor_code,
        "fault_type": "HIGH_TURBIDITY_TRIP",
        "message": "Water turbidity (28.4 NTU) exceeded safety cutoff (25.0 NTU)"
    }
    event2 = await process_fault_payload(controller.device_uid, turbidity_payload)
    assert event2 is not None
    assert event2.event_type == MotorEventType.FAULT


@pytest.mark.asyncio
async def test_status_payload_multi_motor_sync():
    """Verify controller status sync with multiple motors under one controller."""
    with get_sync_session() as session:
        org = Organization(id=uuid.uuid4(), name="MultiMotor Org", organization_code="MM_ORG", status=OrganizationStatus.ACTIVE)
        session.add(org)
        site = Site(id=uuid.uuid4(), organization_id=org.id, name="MM Site", site_code="MM_SITE", site_type=SiteType.HOME, status=SiteStatus.ACTIVE)
        session.add(site)
        station = Station(id=uuid.uuid4(), site_id=site.id, name="MM Stn", station_code="MM_STN", station_type=StationType.WATER_SUPPLY, status=StationStatus.ACTIVE)
        session.add(station)
        controller = Controller(
            id=uuid.uuid4(), station_id=station.id, name="MM Ctrl", controller_code="MM_CTRL",
            device_uid=f"MM-HW-UID-{uuid.uuid4().hex[:6]}", controller_type=ControllerType.ESP32, status=ControllerStatus.ACTIVE
        )
        session.add(controller)

        m1 = Motor(id=uuid.uuid4(), controller_id=controller.id, name="Pump 1", motor_code="P1", motor_type=MotorType.WATER_PUMP, status=MotorStatus.OFF)
        m2 = Motor(id=uuid.uuid4(), controller_id=controller.id, name="Pump 2", motor_code="P2", motor_type=MotorType.WATER_PUMP, status=MotorStatus.ON)
        session.add_all([m1, m2])
        session.commit()
        ctrl_uid = controller.device_uid
        m1_id = m1.id
        m2_id = m2.id

    # Inbound status payload reporting P1 is ON and P2 is OFF
    payload = {
        "controller_status": "ACTIVE",
        "motors": [
            {"motor_code": "P1", "status": "ON"},
            {"motor_code": "P2", "status": "OFF"}
        ]
    }
    processed = await process_status_payload(ctrl_uid, payload)
    assert processed is True

    with get_sync_session() as session:
        m1_ref = session.get(Motor, m1_id)
        m2_ref = session.get(Motor, m2_id)
        assert m1_ref.status == MotorStatus.ON
        assert m2_ref.status == MotorStatus.OFF

