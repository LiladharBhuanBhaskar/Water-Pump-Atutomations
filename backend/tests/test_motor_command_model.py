import uuid
import pytest
import asyncio
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

try:
    from app.db.base import Base, BaseModel, utc_now
    from app.models.organization import Organization
    from app.models.site import Site, SiteType
    from app.models.station import Station, StationType
    from app.models.controller import Controller, ControllerType
    from app.models.motor import Motor
    from app.models.user import User, UserRole
    from app.models.motor_command import MotorCommand, CommandType, CommandStatus
    from app.db.session import (
        sync_engine,
        get_async_session,
        get_sync_session
    )
except ImportError:
    from backend.app.db.base import Base, BaseModel, utc_now
    from backend.app.models.organization import Organization
    from backend.app.models.site import Site, SiteType
    from backend.app.models.station import Station, StationType
    from backend.app.models.controller import Controller, ControllerType
    from backend.app.models.motor import Motor
    from backend.app.models.user import User, UserRole
    from backend.app.models.motor_command import MotorCommand, CommandType, CommandStatus
    from backend.app.db.session import (
        sync_engine,
        get_async_session,
        get_sync_session
    )


@pytest.fixture(scope="module", autouse=True)
def setup_command_tables():
    """Create all tables before running tests and drop after."""
    Base.metadata.create_all(bind=sync_engine)
    yield
    Base.metadata.drop_all(bind=sync_engine)


def test_motor_command_model_inheritance_and_metadata():
    """Verify MotorCommand model inherits from BaseModel and exists in Base.metadata."""
    assert issubclass(MotorCommand, BaseModel)
    assert "motor_commands" in Base.metadata.tables
    table = Base.metadata.tables["motor_commands"]
    assert "id" in table.columns
    assert "motor_id" in table.columns
    assert "command_type" in table.columns
    assert "status" in table.columns
    assert "requested_by" in table.columns
    assert "command_payload" in table.columns
    assert "requested_at" in table.columns
    assert "sent_at" in table.columns
    assert "acknowledged_at" in table.columns
    assert "executed_at" in table.columns
    assert "failed_at" in table.columns
    assert "error_message" in table.columns
    assert "created_at" in table.columns
    assert "updated_at" in table.columns


def _create_hierarchy(session):
    unique_suffix = uuid.uuid4().hex[:6]
    org = Organization(name=f"Cmd Org {unique_suffix}", organization_code=f"CMD-ORG-{unique_suffix}")
    session.add(org)
    session.flush()

    site = Site(organization_id=org.id, name=f"Cmd Site {unique_suffix}", site_code=f"CMD-SITE-{unique_suffix}", site_type=SiteType.OTHER)
    session.add(site)
    session.flush()

    stn = Station(site_id=site.id, name=f"Cmd Station {unique_suffix}", station_code=f"CMD-STN-{unique_suffix}", station_type=StationType.OTHER)
    session.add(stn)
    session.flush()

    ctrl = Controller(
        station_id=stn.id,
        name=f"Cmd Controller {unique_suffix}",
        controller_code=f"CMD-CTRL-{unique_suffix}",
        device_uid=f"ESP32-CMD-{unique_suffix}",
        controller_type=ControllerType.ESP32
    )
    session.add(ctrl)
    session.flush()

    motor = Motor(
        controller_id=ctrl.id,
        name=f"Cmd Motor {unique_suffix}",
        motor_code=f"CMD-M-{unique_suffix}"
    )
    session.add(motor)
    session.flush()

    user = User(
        email=f"cmduser_{uuid.uuid4().hex[:6]}@example.com",
        password_hash="hash",
        name="Cmd User",
        role=UserRole.STATION_OPERATOR,
        organization_id=org.id
    )
    session.add(user)
    session.flush()
    return org, site, stn, ctrl, motor, user


def test_motor_command_creation_defaults_and_system_command():
    """Verify command creation with requested_by=NULL and default values."""
    with get_sync_session() as session:
        _, _, _, _, motor, _ = _create_hierarchy(session)

        now = utc_now()
        cmd = MotorCommand(
            motor_id=motor.id,
            command_type=CommandType.START,
            requested_at=now
        )
        session.add(cmd)
        session.flush()

        assert cmd.id is not None
        assert isinstance(cmd.id, uuid.UUID)
        assert cmd.motor_id == motor.id
        assert cmd.command_type == CommandType.START
        assert cmd.status == CommandStatus.PENDING
        assert cmd.requested_by is None
        assert cmd.command_payload is None
        assert cmd.requested_at == now
        assert cmd.sent_at is None
        assert cmd.acknowledged_at is None
        assert cmd.executed_at is None
        assert cmd.failed_at is None
        assert cmd.error_message is None
        assert isinstance(cmd.created_at, datetime)
        assert isinstance(cmd.updated_at, datetime)
        cmd_id = cmd.id

    with get_sync_session() as session:
        queried = session.get(MotorCommand, cmd_id)
        assert queried is not None
        assert queried.command_type == CommandType.START


def test_motor_command_with_user_and_payload():
    """Verify user relationship and JSON payload."""
    with get_sync_session() as session:
        _, _, _, _, motor, user = _create_hierarchy(session)

        now = utc_now()
        payload = {"reason": "manual_override"}
        cmd = MotorCommand(
            motor_id=motor.id,
            command_type=CommandType.STOP,
            requested_by=user.id,
            command_payload=payload,
            requested_at=now
        )
        session.add(cmd)
        session.flush()

        assert cmd.requested_by == user.id
        assert cmd.command_payload == payload
        
        # Verify bidirectional relationship
        assert cmd.requester.id == user.id
        assert cmd in user.motor_commands


def test_command_types_and_statuses_coverage():
    """Verify all defined CommandType and CommandStatus enum values."""
    c_types = [
        CommandType.START,
        CommandType.STOP,
        CommandType.RESET,
        CommandType.EMERGENCY_STOP
    ]

    c_statuses = [
        CommandStatus.PENDING,
        CommandStatus.SENT,
        CommandStatus.ACKNOWLEDGED,
        CommandStatus.EXECUTED,
        CommandStatus.FAILED,
        CommandStatus.TIMEOUT
    ]

    with get_sync_session() as session:
        _, _, _, _, motor, _ = _create_hierarchy(session)
        now = utc_now()

        for c_type in c_types:
            for status in c_statuses:
                cmd = MotorCommand(
                    motor_id=motor.id,
                    command_type=c_type,
                    status=status,
                    requested_at=now
                )
                session.add(cmd)
        session.flush()
        motor_id = motor.id

    with get_sync_session() as session:
        cmds = session.execute(
            select(MotorCommand).where(MotorCommand.motor_id == motor_id)
        ).scalars().all()
        assert len(cmds) == len(c_types) * len(c_statuses)


def test_motor_command_relationship_bidirectional():
    """Verify bidirectional relationship traversal: Motor.commands and MotorCommand.motor."""
    with get_sync_session() as session:
        _, _, _, _, motor, _ = _create_hierarchy(session)
        now = utc_now()

        cmd1 = MotorCommand(
            motor=motor,
            command_type=CommandType.START,
            requested_at=now
        )
        cmd2 = MotorCommand(
            motor=motor,
            command_type=CommandType.STOP,
            requested_at=now
        )
        session.add_all([cmd1, cmd2])
        session.flush()

        motor_id = motor.id
        cmd1_id = cmd1.id

    # Verify Motor -> Commands
    with get_sync_session() as session:
        fetched_motor = session.get(Motor, motor_id)
        assert fetched_motor is not None
        assert len(fetched_motor.commands) >= 2
        
    # Verify Command -> Motor
    with get_sync_session() as session:
        fetched_cmd = session.get(MotorCommand, cmd1_id)
        assert fetched_cmd is not None
        assert fetched_cmd.motor is not None
        assert fetched_cmd.motor.id == motor_id


@pytest.mark.asyncio
async def test_motor_command_async_crud():
    """Verify async session operations."""
    async with get_async_session() as session:
        unique_suffix = uuid.uuid4().hex[:6]
        org = Organization(name=f"Async Org {unique_suffix}", organization_code=f"ASYNC-ORG-{unique_suffix}")
        session.add(org)
        await session.flush()
        site = Site(organization_id=org.id, name=f"Async Site {unique_suffix}", site_code=f"ASYNC-SITE-{unique_suffix}", site_type=SiteType.OTHER)
        session.add(site)
        await session.flush()
        stn = Station(site_id=site.id, name=f"Async Station {unique_suffix}", station_code=f"ASYNC-STN-{unique_suffix}", station_type=StationType.OTHER)
        session.add(stn)
        await session.flush()
        ctrl = Controller(
            station_id=stn.id,
            name=f"Async Controller {unique_suffix}",
            controller_code=f"ASYNC-C-{unique_suffix}",
            device_uid=f"DEV-ASYNC-{unique_suffix}",
            controller_type=ControllerType.OTHER
        )
        session.add(ctrl)
        await session.flush()
        motor = Motor(
            controller_id=ctrl.id,
            name=f"Async Motor {unique_suffix}",
            motor_code=f"ASYNC-M-{unique_suffix}"
        )
        session.add(motor)
        await session.flush()

        now = utc_now()
        cmd = MotorCommand(
            motor_id=motor.id,
            command_type=CommandType.START,
            requested_at=now
        )
        session.add(cmd)
        await session.flush()
        cmd_id = cmd.id

    async with get_async_session() as session:
        result = await session.execute(select(MotorCommand).where(MotorCommand.id == cmd_id))
        cmd_to_update = result.scalar_one()
        cmd_to_update.status = CommandStatus.EXECUTED
        await session.flush()

        assert cmd_to_update.status == CommandStatus.EXECUTED


def test_motor_command_missing_fields_fail():
    """Verify missing required fields raise IntegrityError."""
    with get_sync_session() as session:
        _, _, _, _, motor, _ = _create_hierarchy(session)
        motor_id = motor.id

    with pytest.raises(IntegrityError):
        with get_sync_session() as session:
            # Missing command_type
            cmd = MotorCommand(motor_id=motor_id, requested_at=utc_now())
            session.add(cmd)
            session.flush()
            
    with pytest.raises(IntegrityError):
        with get_sync_session() as session:
            # Missing requested_at
            cmd = MotorCommand(motor_id=motor_id, command_type=CommandType.START)
            session.add(cmd)
            session.flush()
            
    with pytest.raises(IntegrityError):
        with get_sync_session() as session:
            # Missing motor_id
            cmd = MotorCommand(command_type=CommandType.START, requested_at=utc_now())
            session.add(cmd)
            session.flush()


def test_motor_deletion_restricted_with_commands():
    """Verify that deleting a motor is restricted if it has commands."""
    with get_sync_session() as session:
        _, _, _, _, motor, _ = _create_hierarchy(session)
        now = utc_now()
        
        cmd = MotorCommand(
            motor_id=motor.id,
            command_type=CommandType.START,
            requested_at=now
        )
        session.add(cmd)
        session.flush()
        
        motor_id = motor.id
        
    with pytest.raises(IntegrityError):
        with get_sync_session() as session:
            motor_to_delete = session.get(Motor, motor_id)
            session.delete(motor_to_delete)
            session.flush()


def test_user_deletion_sets_requested_by_null():
    """Verify that deleting a user sets requested_by to NULL on commands."""
    with get_sync_session() as session:
        _, _, _, _, motor, user = _create_hierarchy(session)
        now = utc_now()
        
        cmd = MotorCommand(
            motor_id=motor.id,
            command_type=CommandType.START,
            requested_by=user.id,
            requested_at=now
        )
        session.add(cmd)
        session.flush()
        
        cmd_id = cmd.id
        user_id = user.id
        
    with get_sync_session() as session:
        user_to_delete = session.get(User, user_id)
        session.delete(user_to_delete)
        session.flush()
        
    with get_sync_session() as session:
        cmd_fetched = session.get(MotorCommand, cmd_id)
        assert cmd_fetched.requested_by is None
