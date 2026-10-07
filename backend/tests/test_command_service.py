import pytest
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from app.db.base import Base
from app.db.session import sync_engine, get_sync_session, AsyncSessionLocal
from app.models.organization import Organization, OrganizationStatus
from app.models.site import Site, SiteStatus, SiteType
from app.models.station import Station, StationStatus, StationType
from app.models.controller import Controller, ControllerStatus, ControllerType
from app.models.motor import Motor, MotorStatus, MotorType
from app.models.motor_command import MotorCommand, CommandType, CommandStatus
from app.models.user import User, UserRole
from app.services.command_service import (
    dispatch_motor_command,
    get_motor_command_by_id,
    list_motor_commands,
    MotorCommandNotFoundException,
    MotorNotOperationalException,
    MotorSiteSuspendedException,
    MotorSiteInactiveException,
)


@pytest.fixture(scope="module", autouse=True)
def setup_tables():
    Base.metadata.create_all(bind=sync_engine)
    yield
    Base.metadata.drop_all(bind=sync_engine)


def helper_create_test_hierarchy(prefix: str, site_status: SiteStatus = SiteStatus.ACTIVE, motor_status: MotorStatus = MotorStatus.OFF):
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
            device_uid=f"{prefix}-HW-UID-99",
            controller_type=ControllerType.ESP32,
            status=ControllerStatus.ACTIVE
        )
        session.add(controller)

        motor = Motor(
            id=uuid.uuid4(),
            controller_id=controller.id,
            name=f"{prefix} Pump",
            motor_code="PUMP_MAIN",
            motor_type=MotorType.WATER_PUMP,
            status=motor_status,
            rated_power=7.5
        )
        session.add(motor)

        session.commit()
        return org, site, station, controller, motor


@pytest.mark.asyncio
async def test_dispatch_start_command_happy_path():
    org, site, station, controller, motor = helper_create_test_hierarchy("CMD_HAPPY", motor_status=MotorStatus.OFF)

    mock_mqtt = MagicMock()
    mock_mqtt.publish = AsyncMock(return_value=True)

    user_id = uuid.uuid4()
    payload = {"target_flow": 120.0, "auto_stop_minutes": 30}

    async with AsyncSessionLocal() as session:
        cmd = await dispatch_motor_command(
            session=session,
            motor_id=motor.id,
            command_type=CommandType.START,
            user_id=user_id,
            payload=payload,
            current_user_org_id=org.id,
            mqtt_client=mock_mqtt
        )

        assert cmd.id is not None
        assert cmd.status == CommandStatus.SENT
        assert cmd.sent_at is not None
        assert cmd.command_type == CommandType.START
        assert cmd.requested_by == user_id
        assert cmd.command_payload == payload

        # Verify MQTT publish was called with correct topic and payload
        mock_mqtt.publish.assert_called_once()
        call_args = mock_mqtt.publish.call_args[1]
        assert call_args["topic"] == f"hydracontrol/devices/{controller.device_uid}/commands"
        mqtt_p = call_args["payload"]
        assert mqtt_p["command_id"] == str(cmd.id)
        assert mqtt_p["command_type"] == "START"
        assert mqtt_p["motor_code"] == "PUMP_MAIN"
        assert mqtt_p["payload"] == payload


@pytest.mark.asyncio
async def test_dispatch_command_when_mqtt_offline():
    org, site, station, controller, motor = helper_create_test_hierarchy("CMD_OFFLINE_MQTT", motor_status=MotorStatus.OFF)

    mock_mqtt = MagicMock()
    mock_mqtt.publish = AsyncMock(return_value=False)

    async with AsyncSessionLocal() as session:
        cmd = await dispatch_motor_command(
            session=session,
            motor_id=motor.id,
            command_type=CommandType.STOP,
            current_user_org_id=org.id,
            mqtt_client=mock_mqtt
        )

        assert cmd.id is not None
        assert cmd.status == CommandStatus.PENDING
        assert cmd.sent_at is None


@pytest.mark.asyncio
async def test_dispatch_start_command_rejected_for_invalid_motor_states():
    # OFFLINE
    org1, _, _, _, m_offline = helper_create_test_hierarchy("M_OFF", motor_status=MotorStatus.OFFLINE)
    async with AsyncSessionLocal() as session:
        with pytest.raises(MotorNotOperationalException) as exc:
            await dispatch_motor_command(session, m_offline.id, CommandType.START, current_user_org_id=org1.id)
        assert "in status 'OFFLINE'" in str(exc.value)

    # MAINTENANCE
    org2, _, _, _, m_maint = helper_create_test_hierarchy("M_MAINT", motor_status=MotorStatus.MAINTENANCE)
    async with AsyncSessionLocal() as session:
        with pytest.raises(MotorNotOperationalException) as exc:
            await dispatch_motor_command(session, m_maint.id, CommandType.START, current_user_org_id=org2.id)
        assert "in status 'MAINTENANCE'" in str(exc.value)

    # DISABLED
    org3, _, _, _, m_dis = helper_create_test_hierarchy("M_DIS", motor_status=MotorStatus.DISABLED)
    async with AsyncSessionLocal() as session:
        with pytest.raises(MotorNotOperationalException) as exc:
            await dispatch_motor_command(session, m_dis.id, CommandType.START, current_user_org_id=org3.id)
        assert "in status 'DISABLED'" in str(exc.value)


@pytest.mark.asyncio
async def test_dispatch_stop_and_emergency_stop_allowed_in_fault_state():
    org, _, _, _, m_fault = helper_create_test_hierarchy("M_FAULT", motor_status=MotorStatus.FAULT)
    mock_mqtt = MagicMock()
    mock_mqtt.publish = AsyncMock(return_value=True)

    async with AsyncSessionLocal() as session:
        cmd_stop = await dispatch_motor_command(
            session, m_fault.id, CommandType.STOP, current_user_org_id=org.id, mqtt_client=mock_mqtt
        )
        assert cmd_stop.status == CommandStatus.SENT

        cmd_estop = await dispatch_motor_command(
            session, m_fault.id, CommandType.EMERGENCY_STOP, current_user_org_id=org.id, mqtt_client=mock_mqtt
        )
        assert cmd_estop.status == CommandStatus.SENT


@pytest.mark.asyncio
async def test_dispatch_command_site_operational_policies():
    # Suspended Site
    org_s, _, _, _, m_susp = helper_create_test_hierarchy("S_SUSP", site_status=SiteStatus.SUSPENDED)
    async with AsyncSessionLocal() as session:
        with pytest.raises(MotorSiteSuspendedException):
            await dispatch_motor_command(session, m_susp.id, CommandType.START, current_user_org_id=org_s.id)

    # Inactive Site
    org_i, _, _, _, m_inact = helper_create_test_hierarchy("S_INACT", site_status=SiteStatus.INACTIVE)
    async with AsyncSessionLocal() as session:
        with pytest.raises(MotorSiteInactiveException):
            await dispatch_motor_command(session, m_inact.id, CommandType.START, current_user_org_id=org_i.id)


@pytest.mark.asyncio
async def test_dispatch_command_organization_isolation():
    org_a, _, _, _, m_a = helper_create_test_hierarchy("ORG_A")
    org_b, _, _, _, m_b = helper_create_test_hierarchy("ORG_B")

    mock_mqtt = MagicMock()
    mock_mqtt.publish = AsyncMock(return_value=True)

    async with AsyncSessionLocal() as session:
        # Org A user attempts to command Org B's motor -> 404 masked exception
        with pytest.raises(MotorCommandNotFoundException):
            await dispatch_motor_command(
                session, m_b.id, CommandType.START, current_user_org_id=org_a.id, mqtt_client=mock_mqtt
            )

        # Super Admin without specific org can dispatch
        cmd_super = await dispatch_motor_command(
            session, m_b.id, CommandType.START, is_super_admin=True, mqtt_client=mock_mqtt
        )
        assert cmd_super.status == CommandStatus.SENT


@pytest.mark.asyncio
async def test_get_and_list_motor_commands():
    org, _, _, _, motor = helper_create_test_hierarchy("CMD_LIST")
    mock_mqtt = MagicMock()
    mock_mqtt.publish = AsyncMock(return_value=True)

    async with AsyncSessionLocal() as session:
        cmd1 = await dispatch_motor_command(session, motor.id, CommandType.START, mqtt_client=mock_mqtt)
        cmd2 = await dispatch_motor_command(session, motor.id, CommandType.STOP, mqtt_client=mock_mqtt)

        fetched = await get_motor_command_by_id(session, cmd1.id)
        assert fetched is not None
        assert fetched.id == cmd1.id

        all_cmds = await list_motor_commands(session, motor_id=motor.id)
        assert len(all_cmds) >= 2
        cmd_ids = [c.id for c in all_cmds]
        assert cmd1.id in cmd_ids
        assert cmd2.id in cmd_ids
