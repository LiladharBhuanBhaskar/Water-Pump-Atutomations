"""
HydraControl — Site-Scoped Query Pattern Tests (LOOP 3 & LOOP 4)
Verifies site-level atomic query scoping across all domain models in the hierarchy:
Site -> Station -> Controller -> Motor & Sensor -> Telemetry, Commands, Events, Rules, Settings, Logs.
"""
import uuid
from decimal import Decimal
from datetime import datetime, timezone
import pytest

from app.db.base import Base
from app.db.session import sync_engine, get_async_session
from app.models.organization import Organization, OrganizationStatus
from app.models.site import Site, SiteType, SiteStatus
from app.models.station import Station, StationType, StationStatus
from app.models.settings import StationSettings
from app.models.controller import Controller, ControllerType, ControllerStatus
from app.models.motor import Motor, MotorType, MotorStatus
from app.models.sensor import Sensor, SensorType, SensorStatus
from app.models.telemetry import TelemetryReading
from app.models.motor_command import MotorCommand, CommandType, CommandStatus
from app.models.motor_event import MotorEvent, MotorEventType, MotorEventSource
from app.models.automation_rule import AutomationRule, AutomationRuleType, AutomationAction, AutomationRuleStatus
from app.models.audit_log import AuditLog, AuditAction, AuditActorType
from app.services.site_auth import get_site_scoped_resource, list_site_scoped_resources

@pytest.fixture(scope="module", autouse=True)
def setup_tables():
    Base.metadata.create_all(bind=sync_engine)
    yield
    Base.metadata.drop_all(bind=sync_engine)


@pytest.mark.asyncio
async def test_site_scoped_queries_full_hierarchy():
    async with get_async_session() as session:
        # Organization
        org = Organization(
            id=uuid.uuid4(),
            name="Apex Water Org",
            organization_code="APEX-001",
            status=OrganizationStatus.ACTIVE
        )
        session.add(org)
        await session.commit()

        # Site 1 and Site 2 under the same Organization
        site_1 = Site(
            id=uuid.uuid4(),
            organization_id=org.id,
            name="Plant North",
            site_code="PLANT-N",
            site_type=SiteType.WATER_PLANT,
            status=SiteStatus.ACTIVE
        )
        site_2 = Site(
            id=uuid.uuid4(),
            organization_id=org.id,
            name="Plant South",
            site_code="PLANT-S",
            site_type=SiteType.WATER_PLANT,
            status=SiteStatus.ACTIVE
        )
        session.add_all([site_1, site_2])
        await session.commit()

        # Station 1 (under Site 1) and Station 2 (under Site 2)
        stn_1 = Station(
            id=uuid.uuid4(),
            site_id=site_1.id,
            name="Station North 1",
            station_code="STN-N1",
            station_type=StationType.WATER_SUPPLY,
            status=StationStatus.ACTIVE
        )
        stn_2 = Station(
            id=uuid.uuid4(),
            site_id=site_2.id,
            name="Station South 1",
            station_code="STN-S1",
            station_type=StationType.WATER_SUPPLY,
            status=StationStatus.ACTIVE
        )
        session.add_all([stn_1, stn_2])
        await session.commit()

        # Settings for Station 1 and 2
        set_1 = StationSettings(
            id=uuid.uuid4(),
            station_id=stn_1.id,
            auto_stop_on_tank_full=True
        )
        set_2 = StationSettings(
            id=uuid.uuid4(),
            station_id=stn_2.id,
            auto_stop_on_tank_full=False
        )
        session.add_all([set_1, set_2])
        await session.commit()

        # Controller 1 and 2
        ctrl_1 = Controller(
            id=uuid.uuid4(),
            station_id=stn_1.id,
            name="Ctrl N1",
            controller_code="CN-01",
            device_uid="DEV-N1-001",
            controller_type=ControllerType.ESP32,
            status=ControllerStatus.ACTIVE
        )
        ctrl_2 = Controller(
            id=uuid.uuid4(),
            station_id=stn_2.id,
            name="Ctrl S1",
            controller_code="CS-01",
            device_uid="DEV-S1-001",
            controller_type=ControllerType.ESP32,
            status=ControllerStatus.ACTIVE
        )
        session.add_all([ctrl_1, ctrl_2])
        await session.commit()

        # Motor 1 and 2
        motor_1 = Motor(
            id=uuid.uuid4(),
            controller_id=ctrl_1.id,
            name="Pump N1",
            motor_code="PN-01",
            motor_type=MotorType.WATER_PUMP,
            status=MotorStatus.OFF
        )
        motor_2 = Motor(
            id=uuid.uuid4(),
            controller_id=ctrl_2.id,
            name="Pump S1",
            motor_code="PS-01",
            motor_type=MotorType.WATER_PUMP,
            status=MotorStatus.OFF
        )
        session.add_all([motor_1, motor_2])
        await session.commit()

        # Sensor 1 and 2
        sens_1 = Sensor(
            id=uuid.uuid4(),
            controller_id=ctrl_1.id,
            name="Level N1",
            sensor_code="SN-01",
            sensor_type=SensorType.WATER_LEVEL,
            status=SensorStatus.ACTIVE
        )
        sens_2 = Sensor(
            id=uuid.uuid4(),
            controller_id=ctrl_2.id,
            name="Level S1",
            sensor_code="SS-01",
            sensor_type=SensorType.WATER_LEVEL,
            status=SensorStatus.ACTIVE
        )
        session.add_all([sens_1, sens_2])
        await session.commit()

        # Telemetry 1 and 2
        now = datetime.now(timezone.utc)
        telem_1 = TelemetryReading(
            id=uuid.uuid4(),
            sensor_id=sens_1.id,
            value=Decimal("50.0"),
            unit="PERCENT",
            occurred_at=now
        )
        telem_2 = TelemetryReading(
            id=uuid.uuid4(),
            sensor_id=sens_2.id,
            value=Decimal("75.0"),
            unit="PERCENT",
            occurred_at=now
        )
        session.add_all([telem_1, telem_2])
        await session.commit()

        # Command 1 and 2
        cmd_1 = MotorCommand(
            id=uuid.uuid4(),
            motor_id=motor_1.id,
            command_type=CommandType.START,
            status=CommandStatus.EXECUTED,
            requested_at=now
        )
        cmd_2 = MotorCommand(
            id=uuid.uuid4(),
            motor_id=motor_2.id,
            command_type=CommandType.STOP,
            status=CommandStatus.EXECUTED,
            requested_at=now
        )
        session.add_all([cmd_1, cmd_2])
        await session.commit()

        # Event 1 and 2
        evt_1 = MotorEvent(
            id=uuid.uuid4(),
            motor_id=motor_1.id,
            event_type=MotorEventType.STARTED,
            source=MotorEventSource.USER,
            occurred_at=now
        )
        evt_2 = MotorEvent(
            id=uuid.uuid4(),
            motor_id=motor_2.id,
            event_type=MotorEventType.STOPPED,
            source=MotorEventSource.SYSTEM,
            occurred_at=now
        )
        session.add_all([evt_1, evt_2])
        await session.commit()

        # AutomationRule 1 and 2
        rule_1 = AutomationRule(
            id=uuid.uuid4(),
            station_id=stn_1.id,
            name="Cutoff N1",
            rule_type=AutomationRuleType.WATER_LEVEL,
            motor_id=motor_1.id,
            action=AutomationAction.STOP_MOTOR,
            status=AutomationRuleStatus.ACTIVE
        )
        rule_2 = AutomationRule(
            id=uuid.uuid4(),
            station_id=stn_2.id,
            name="Cutoff S1",
            rule_type=AutomationRuleType.WATER_LEVEL,
            motor_id=motor_2.id,
            action=AutomationAction.STOP_MOTOR,
            status=AutomationRuleStatus.ACTIVE
        )
        session.add_all([rule_1, rule_2])
        await session.commit()

        # AuditLog 1 and 2
        audit_1 = AuditLog(
            id=uuid.uuid4(),
            organization_id=org.id,
            site_id=site_1.id,
            actor_type=AuditActorType.USER,
            action=AuditAction.START,
            resource_type="Motor",
            resource_id=motor_1.id,
            action_description="Started Motor 1"
        )
        audit_2 = AuditLog(
            id=uuid.uuid4(),
            organization_id=org.id,
            site_id=site_2.id,
            actor_type=AuditActorType.USER,
            action=AuditAction.STOP,
            resource_type="Motor",
            resource_id=motor_2.id,
            action_description="Stopped Motor 2"
        )
        session.add_all([audit_1, audit_2])
        await session.commit()

        # VERIFICATION: Test all models under Site 1 context
        test_matrix = [
            (Site, site_1.id, site_2.id),
            (Station, stn_1.id, stn_2.id),
            (StationSettings, set_1.id, set_2.id),
            (AutomationRule, rule_1.id, rule_2.id),
            (Controller, ctrl_1.id, ctrl_2.id),
            (Motor, motor_1.id, motor_2.id),
            (Sensor, sens_1.id, sens_2.id),
            (TelemetryReading, telem_1.id, telem_2.id),
            (MotorCommand, cmd_1.id, cmd_2.id),
            (MotorEvent, evt_1.id, evt_2.id),
            (AuditLog, audit_1.id, audit_2.id),
        ]

        for model, res_1_id, res_2_id in test_matrix:
            # Query with Site 1 scope -> Resource 1 is allowed
            r1 = await get_site_scoped_resource(session, model, res_1_id, site_1.id, org.id)
            assert r1 is not None, f"{model.__name__} 1 should be accessible in Site 1 scope"
            assert r1.id == res_1_id

            # Query with Site 1 scope -> Resource 2 (from Site 2) is DENIED (returns None)
            r2_from_s1 = await get_site_scoped_resource(session, model, res_2_id, site_1.id, org.id)
            assert r2_from_s1 is None, f"{model.__name__} 2 from Site 2 leaked into Site 1 scope!"

            # Query with Site 2 scope -> Resource 2 is allowed
            r2 = await get_site_scoped_resource(session, model, res_2_id, site_2.id, org.id)
            assert r2 is not None, f"{model.__name__} 2 should be accessible in Site 2 scope"
            assert r2.id == res_2_id

            # Query with Site 2 scope -> Resource 1 (from Site 1) is DENIED (returns None)
            r1_from_s2 = await get_site_scoped_resource(session, model, res_1_id, site_2.id, org.id)
            assert r1_from_s2 is None, f"{model.__name__} 1 from Site 1 leaked into Site 2 scope!"

        # Test list scoping per site
        motors_s1 = await list_site_scoped_resources(session, Motor, site_1.id, org.id)
        assert len(motors_s1) == 1
        assert motors_s1[0].id == motor_1.id

        motors_s2 = await list_site_scoped_resources(session, Motor, site_2.id, org.id)
        assert len(motors_s2) == 1
        assert motors_s2[0].id == motor_2.id
