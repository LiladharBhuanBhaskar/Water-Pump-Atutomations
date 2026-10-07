"""
HydraControl — P6-T04 Command Timeout Watchdog Tests
Verifies automatic detection and transition of expired PENDING/SENT commands,
terminal state preservation, idempotency, failure metadata population, and non-republishing.
"""

import pytest
import uuid
from datetime import datetime, timezone, timedelta
from app.db.base import Base
from app.db.session import sync_engine, get_sync_session, AsyncSessionLocal
from app.models.organization import Organization, OrganizationStatus
from app.models.site import Site, SiteStatus, SiteType
from app.models.station import Station, StationStatus, StationType
from app.models.controller import Controller, ControllerStatus, ControllerType
from app.models.motor import Motor, MotorStatus, MotorType
from app.models.motor_command import MotorCommand, CommandType, CommandStatus
from app.services.command_watchdog import process_command_timeouts


@pytest.fixture(scope="module", autouse=True)
def setup_tables():
    Base.metadata.create_all(bind=sync_engine)
    yield
    Base.metadata.drop_all(bind=sync_engine)


@pytest.fixture(autouse=True)
def clean_commands():
    with get_sync_session() as session:
        session.query(MotorCommand).delete()
        session.commit()
    yield


def helper_create_watchdog_setup(prefix: str):
    """Sets up a test motor for watchdog testing."""
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
            name=f"{prefix} Pump",
            motor_code="PUMP_WD",
            motor_type=MotorType.WATER_PUMP,
            status=MotorStatus.OFF
        )
        session.add(motor)
        session.commit()

        return {
            "motor": motor,
            "controller": controller,
        }


@pytest.mark.asyncio
async def test_pending_command_within_timeout_remains_pending():
    """A PENDING command requested recently (within timeout window) is not timed out."""
    setup = helper_create_watchdog_setup("WD_PEND_OK")
    motor = setup["motor"]

    now = datetime(2026, 10, 5, 12, 0, 0, tzinfo=timezone.utc)
    cmd_id = uuid.uuid4()

    with get_sync_session() as session:
        cmd = MotorCommand(
            id=cmd_id,
            motor_id=motor.id,
            command_type=CommandType.START,
            status=CommandStatus.PENDING,
            requested_at=now - timedelta(seconds=10)  # 10s old, limit is 30s
        )
        session.add(cmd)
        session.commit()

    async with AsyncSessionLocal() as async_session:
        res = await process_command_timeouts(async_session, timeout_seconds=30, now=now)
        assert res["timed_out_count"] == 0

    with get_sync_session() as session:
        refreshed = session.get(MotorCommand, cmd_id)
        assert refreshed.status == CommandStatus.PENDING
        assert refreshed.failed_at is None


@pytest.mark.asyncio
async def test_pending_command_past_timeout_transitions_to_timeout():
    """A PENDING command older than the timeout window transitions to TIMEOUT."""
    setup = helper_create_watchdog_setup("WD_PEND_EXP")
    motor = setup["motor"]

    now = datetime(2026, 10, 5, 12, 0, 0, tzinfo=timezone.utc)
    cmd_id = uuid.uuid4()

    with get_sync_session() as session:
        cmd = MotorCommand(
            id=cmd_id,
            motor_id=motor.id,
            command_type=CommandType.START,
            status=CommandStatus.PENDING,
            requested_at=now - timedelta(seconds=45)  # 45s old, limit is 30s
        )
        session.add(cmd)
        session.commit()

    async with AsyncSessionLocal() as async_session:
        res = await process_command_timeouts(async_session, timeout_seconds=30, now=now)
        assert res["timed_out_count"] == 1

    with get_sync_session() as session:
        refreshed = session.get(MotorCommand, cmd_id)
        assert refreshed.status == CommandStatus.TIMEOUT
        assert refreshed.failed_at is not None
        assert "timed out" in refreshed.error_message.lower()


@pytest.mark.asyncio
async def test_sent_command_within_timeout_remains_sent():
    """A SENT command within timeout duration remains SENT."""
    setup = helper_create_watchdog_setup("WD_SENT_OK")
    motor = setup["motor"]

    now = datetime(2026, 10, 5, 12, 0, 0, tzinfo=timezone.utc)
    cmd_id = uuid.uuid4()

    with get_sync_session() as session:
        cmd = MotorCommand(
            id=cmd_id,
            motor_id=motor.id,
            command_type=CommandType.STOP,
            status=CommandStatus.SENT,
            requested_at=now - timedelta(seconds=20),
            sent_at=now - timedelta(seconds=15)  # 15s elapsed since sent, limit 30s
        )
        session.add(cmd)
        session.commit()

    async with AsyncSessionLocal() as async_session:
        res = await process_command_timeouts(async_session, timeout_seconds=30, now=now)
        assert res["timed_out_count"] == 0

    with get_sync_session() as session:
        refreshed = session.get(MotorCommand, cmd_id)
        assert refreshed.status == CommandStatus.SENT


@pytest.mark.asyncio
async def test_sent_command_past_timeout_transitions_to_timeout():
    """A SENT command past timeout duration transitions to TIMEOUT."""
    setup = helper_create_watchdog_setup("WD_SENT_EXP")
    motor = setup["motor"]

    now = datetime(2026, 10, 5, 12, 0, 0, tzinfo=timezone.utc)
    cmd_id = uuid.uuid4()

    with get_sync_session() as session:
        cmd = MotorCommand(
            id=cmd_id,
            motor_id=motor.id,
            command_type=CommandType.STOP,
            status=CommandStatus.SENT,
            requested_at=now - timedelta(seconds=60),
            sent_at=now - timedelta(seconds=55)  # 55s elapsed since sent, limit 30s
        )
        session.add(cmd)
        session.commit()

    async with AsyncSessionLocal() as async_session:
        res = await process_command_timeouts(async_session, timeout_seconds=30, now=now)
        assert res["timed_out_count"] == 1

    with get_sync_session() as session:
        refreshed = session.get(MotorCommand, cmd_id)
        assert refreshed.status == CommandStatus.TIMEOUT
        assert refreshed.failed_at is not None
        assert "timed out" in refreshed.error_message.lower()


@pytest.mark.asyncio
async def test_terminal_states_are_never_mutated_by_watchdog():
    """Commands in EXECUTED, FAILED, or TIMEOUT states are completely untouched by watchdog."""
    setup = helper_create_watchdog_setup("WD_TERMINAL")
    motor = setup["motor"]

    now = datetime(2026, 10, 5, 12, 0, 0, tzinfo=timezone.utc)
    old_time = now - timedelta(hours=2)

    cmd_exec_id = uuid.uuid4()
    cmd_fail_id = uuid.uuid4()
    cmd_tout_id = uuid.uuid4()

    with get_sync_session() as session:
        cmd_exec = MotorCommand(
            id=cmd_exec_id,
            motor_id=motor.id,
            command_type=CommandType.START,
            status=CommandStatus.EXECUTED,
            requested_at=old_time,
            sent_at=old_time,
            executed_at=old_time
        )
        cmd_fail = MotorCommand(
            id=cmd_fail_id,
            motor_id=motor.id,
            command_type=CommandType.STOP,
            status=CommandStatus.FAILED,
            requested_at=old_time,
            failed_at=old_time,
            error_message="Contactor stuck"
        )
        cmd_tout = MotorCommand(
            id=cmd_tout_id,
            motor_id=motor.id,
            command_type=CommandType.START,
            status=CommandStatus.TIMEOUT,
            requested_at=old_time,
            failed_at=old_time,
            error_message="Previous timeout"
        )
        session.add_all([cmd_exec, cmd_fail, cmd_tout])
        session.commit()

    async with AsyncSessionLocal() as async_session:
        res = await process_command_timeouts(async_session, timeout_seconds=30, now=now)
        assert res["timed_out_count"] == 0

    with get_sync_session() as session:
        r_exec = session.get(MotorCommand, cmd_exec_id)
        r_fail = session.get(MotorCommand, cmd_fail_id)
        r_tout = session.get(MotorCommand, cmd_tout_id)

        assert r_exec.status == CommandStatus.EXECUTED
        assert r_fail.status == CommandStatus.FAILED
        assert r_fail.error_message == "Contactor stuck"
        assert r_tout.status == CommandStatus.TIMEOUT
        assert r_tout.error_message == "Previous timeout"


@pytest.mark.asyncio
async def test_watchdog_idempotency_on_multiple_runs():
    """Running watchdog multiple times sequentially does not repeatedly mutate commands."""
    setup = helper_create_watchdog_setup("WD_IDEM")
    motor = setup["motor"]

    now = datetime(2026, 10, 5, 12, 0, 0, tzinfo=timezone.utc)
    cmd_id = uuid.uuid4()

    with get_sync_session() as session:
        cmd = MotorCommand(
            id=cmd_id,
            motor_id=motor.id,
            command_type=CommandType.START,
            status=CommandStatus.PENDING,
            requested_at=now - timedelta(seconds=50)
        )
        session.add(cmd)
        session.commit()

    # Run 1: transitions command
    async with AsyncSessionLocal() as async_session:
        res1 = await process_command_timeouts(async_session, timeout_seconds=30, now=now)
        assert res1["timed_out_count"] == 1

    # Run 2: command is now TIMEOUT (terminal), so 0 timed out
    async with AsyncSessionLocal() as async_session:
        res2 = await process_command_timeouts(async_session, timeout_seconds=30, now=now)
        assert res2["timed_out_count"] == 0


@pytest.mark.asyncio
async def test_watchdog_batch_processing():
    """Watchdog properly handles a mix of expired and non-expired commands."""
    setup = helper_create_watchdog_setup("WD_BATCH")
    motor = setup["motor"]

    now = datetime(2026, 10, 5, 12, 0, 0, tzinfo=timezone.utc)

    # 3 expired, 2 fresh
    with get_sync_session() as session:
        for i in range(3):
            session.add(MotorCommand(
                motor_id=motor.id,
                command_type=CommandType.START,
                status=CommandStatus.SENT,
                requested_at=now - timedelta(seconds=60 + i),
                sent_at=now - timedelta(seconds=50 + i)
            ))
        for j in range(2):
            session.add(MotorCommand(
                motor_id=motor.id,
                command_type=CommandType.STOP,
                status=CommandStatus.SENT,
                requested_at=now - timedelta(seconds=10 + j),
                sent_at=now - timedelta(seconds=5 + j)
            ))
        session.commit()

    async with AsyncSessionLocal() as async_session:
        res = await process_command_timeouts(async_session, timeout_seconds=30, now=now)
        assert res["timed_out_count"] == 3
        assert res["unaffected_count"] == 2
