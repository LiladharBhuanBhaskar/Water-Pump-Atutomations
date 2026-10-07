"""
HydraControl — Organization-Scoped Query Pattern Tests (LOOP 2 & LOOP 3)
Verifies safe atomic query-level tenant scoping across the full domain hierarchy:
Organization -> Site -> Station -> Controller -> Motor & Sensor -> Telemetry, Commands, Events, Rules, Settings, Logs.
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
from app.models.user import User, UserRole
from app.services.tenant import get_org_scoped_resource, list_org_scoped_resources

@pytest.fixture(scope="module", autouse=True)
def setup_tables():
    Base.metadata.create_all(bind=sync_engine)
    yield
    Base.metadata.drop_all(bind=sync_engine)


@pytest.mark.asyncio
async def test_org_scoped_queries_full_hierarchy():
    async with get_async_session() as session:
        # 1. Create Organization A and Organization B
        org_a = Organization(
            id=uuid.uuid4(),
            name="Tenant A",
            organization_code="TENANT-A",
            status=OrganizationStatus.ACTIVE
        )
        org_b = Organization(
            id=uuid.uuid4(),
            name="Tenant B",
            organization_code="TENANT-B",
            status=OrganizationStatus.ACTIVE
        )
        session.add_all([org_a, org_b])
        await session.commit()

        # 2. Create Site for A and Site for B
        site_a = Site(
            id=uuid.uuid4(),
            organization_id=org_a.id,
            name="Site Alpha",
            site_code="SITE-A1",
            site_type=SiteType.WATER_PLANT,
            status=SiteStatus.ACTIVE
        )
        site_b = Site(
            id=uuid.uuid4(),
            organization_id=org_b.id,
            name="Site Beta",
            site_code="SITE-B1",
            site_type=SiteType.FACTORY,
            status=SiteStatus.ACTIVE
        )
        session.add_all([site_a, site_b])
        await session.commit()

        # 3. Create Station for A and Station for B
        station_a = Station(
            id=uuid.uuid4(),
            site_id=site_a.id,
            name="Station A1",
            station_code="STN-A1",
            station_type=StationType.WATER_SUPPLY,
            status=StationStatus.ACTIVE
        )
        station_b = Station(
            id=uuid.uuid4(),
            site_id=site_b.id,
            name="Station B1",
            station_code="STN-B1",
            station_type=StationType.INDUSTRIAL,
            status=StationStatus.ACTIVE
        )
        session.add_all([station_a, station_b])
        await session.commit()

        # 4. Settings for Station A and B
        settings_a = StationSettings(
            id=uuid.uuid4(),
            station_id=station_a.id,
            auto_stop_on_tank_full=True,
            water_level_threshold=Decimal("95.0")
        )
        settings_b = StationSettings(
            id=uuid.uuid4(),
            station_id=station_b.id,
            auto_stop_on_tank_full=False,
            water_level_threshold=Decimal("80.0")
        )
        session.add_all([settings_a, settings_b])
        await session.commit()

        # 5. Controller for Station A and B
        ctrl_a = Controller(
            id=uuid.uuid4(),
            station_id=station_a.id,
            name="Controller A1",
            controller_code="CTRL-A1",
            device_uid="ESP32-TENANT-A-001",
            controller_type=ControllerType.ESP32,
            status=ControllerStatus.ACTIVE
        )
        ctrl_b = Controller(
            id=uuid.uuid4(),
            station_id=station_b.id,
            name="Controller B1",
            controller_code="CTRL-B1",
            device_uid="ESP32-TENANT-B-001",
            controller_type=ControllerType.ESP32,
            status=ControllerStatus.ACTIVE
        )
        session.add_all([ctrl_a, ctrl_b])
        await session.commit()

        # 6. Motor for Controller A and B
        motor_a = Motor(
            id=uuid.uuid4(),
            controller_id=ctrl_a.id,
            name="Main Pump A",
            motor_code="PUMP-A1",
            motor_type=MotorType.WATER_PUMP,
            status=MotorStatus.OFF,
            rated_power=Decimal("7.5")
        )
        motor_b = Motor(
            id=uuid.uuid4(),
            controller_id=ctrl_b.id,
            name="Main Pump B",
            motor_code="PUMP-B1",
            motor_type=MotorType.INDUSTRIAL_PUMP,
            status=MotorStatus.OFF,
            rated_power=Decimal("15.0")
        )
        session.add_all([motor_a, motor_b])
        await session.commit()

        # 7. Sensor for Controller A and B
        sensor_a = Sensor(
            id=uuid.uuid4(),
            controller_id=ctrl_a.id,
            name="Level Sensor A",
            sensor_code="SENS-A1",
            sensor_type=SensorType.WATER_LEVEL,
            status=SensorStatus.ACTIVE
        )
        sensor_b = Sensor(
            id=uuid.uuid4(),
            controller_id=ctrl_b.id,
            name="Level Sensor B",
            sensor_code="SENS-B1",
            sensor_type=SensorType.WATER_LEVEL,
            status=SensorStatus.ACTIVE
        )
        session.add_all([sensor_a, sensor_b])
        await session.commit()

        # 8. Telemetry for Sensor A and B
        now = datetime.now(timezone.utc)
        telem_a = TelemetryReading(
            id=uuid.uuid4(),
            sensor_id=sensor_a.id,
            value=Decimal("45.5"),
            unit="PERCENT",
            occurred_at=now
        )
        telem_b = TelemetryReading(
            id=uuid.uuid4(),
            sensor_id=sensor_b.id,
            value=Decimal("60.0"),
            unit="PERCENT",
            occurred_at=now
        )
        session.add_all([telem_a, telem_b])
        await session.commit()

        # 9. MotorCommand for Motor A and B
        cmd_a = MotorCommand(
            id=uuid.uuid4(),
            motor_id=motor_a.id,
            command_type=CommandType.START,
            status=CommandStatus.EXECUTED,
            requested_at=now
        )
        cmd_b = MotorCommand(
            id=uuid.uuid4(),
            motor_id=motor_b.id,
            command_type=CommandType.STOP,
            status=CommandStatus.EXECUTED,
            requested_at=now
        )
        session.add_all([cmd_a, cmd_b])
        await session.commit()

        # 10. MotorEvent for Motor A and B
        event_a = MotorEvent(
            id=uuid.uuid4(),
            motor_id=motor_a.id,
            event_type=MotorEventType.STARTED,
            source=MotorEventSource.USER,
            occurred_at=now
        )
        event_b = MotorEvent(
            id=uuid.uuid4(),
            motor_id=motor_b.id,
            event_type=MotorEventType.STOPPED,
            source=MotorEventSource.SYSTEM,
            occurred_at=now
        )
        session.add_all([event_a, event_b])
        await session.commit()

        # 11. AutomationRule for Station A and B
        rule_a = AutomationRule(
            id=uuid.uuid4(),
            station_id=station_a.id,
            name="High Water Cutoff A",
            rule_type=AutomationRuleType.WATER_LEVEL,
            motor_id=motor_a.id,
            action=AutomationAction.STOP_MOTOR,
            status=AutomationRuleStatus.ACTIVE
        )
        rule_b = AutomationRule(
            id=uuid.uuid4(),
            station_id=station_b.id,
            name="High Water Cutoff B",
            rule_type=AutomationRuleType.WATER_LEVEL,
            motor_id=motor_b.id,
            action=AutomationAction.STOP_MOTOR,
            status=AutomationRuleStatus.ACTIVE
        )
        session.add_all([rule_a, rule_b])
        await session.commit()

        # 12. AuditLog for Org A and B
        audit_a = AuditLog(
            id=uuid.uuid4(),
            organization_id=org_a.id,
            site_id=site_a.id,
            station_id=station_a.id,
            actor_type=AuditActorType.SYSTEM,
            action=AuditAction.START,
            resource_type="Motor",
            resource_id=motor_a.id,
            action_description="Motor A started"
        )
        audit_b = AuditLog(
            id=uuid.uuid4(),
            organization_id=org_b.id,
            site_id=site_b.id,
            station_id=station_b.id,
            actor_type=AuditActorType.SYSTEM,
            action=AuditAction.STOP,
            resource_type="Motor",
            resource_id=motor_b.id,
            action_description="Motor B stopped"
        )
        session.add_all([audit_a, audit_b])
        await session.commit()

        # 13. User for Org A and B
        user_a = User(
            id=uuid.uuid4(),
            name="Operator A",
            email="op_a@example.com",
            password_hash="hash",
            role=UserRole.STATION_OPERATOR,
            is_active=True,
            organization_id=org_a.id
        )
        user_b = User(
            id=uuid.uuid4(),
            name="Operator B",
            email="op_b@example.com",
            password_hash="hash",
            role=UserRole.STATION_OPERATOR,
            is_active=True,
            organization_id=org_b.id
        )
        session.add_all([user_a, user_b])
        await session.commit()

        # VERIFICATION: Test all models under Org A context
        test_matrix = [
            (Organization, org_a.id, org_b.id),
            (Site, site_a.id, site_b.id),
            (Station, station_a.id, station_b.id),
            (StationSettings, settings_a.id, settings_b.id),
            (Controller, ctrl_a.id, ctrl_b.id),
            (Motor, motor_a.id, motor_b.id),
            (Sensor, sensor_a.id, sensor_b.id),
            (TelemetryReading, telem_a.id, telem_b.id),
            (MotorCommand, cmd_a.id, cmd_b.id),
            (MotorEvent, event_a.id, event_b.id),
            (AutomationRule, rule_a.id, rule_b.id),
            (AuditLog, audit_a.id, audit_b.id),
            (User, user_a.id, user_b.id),
        ]

        for model, res_a_id, res_b_id in test_matrix:
            # Org A accessing Org A resource -> Allowed
            res_a = await get_org_scoped_resource(session, model, res_a_id, org_a.id)
            assert res_a is not None, f"Expected {model.__name__} A to be accessible in Org A"
            assert res_a.id == res_a_id

            # Org A accessing Org B resource -> Denied (Returns None)
            res_b_from_a = await get_org_scoped_resource(session, model, res_b_id, org_a.id)
            assert res_b_from_a is None, f"Security Violation: {model.__name__} B leaked to Org A"

            # Org B accessing Org B resource -> Allowed
            res_b = await get_org_scoped_resource(session, model, res_b_id, org_b.id)
            assert res_b is not None, f"Expected {model.__name__} B to be accessible in Org B"
            assert res_b.id == res_b_id

            # Org B accessing Org A resource -> Denied (Returns None)
            res_a_from_b = await get_org_scoped_resource(session, model, res_a_id, org_b.id)
            assert res_a_from_b is None, f"Security Violation: {model.__name__} A leaked to Org B"

        # Test list scoping
        motors_a = await list_org_scoped_resources(session, Motor, org_a.id)
        assert len(motors_a) == 1
        assert motors_a[0].id == motor_a.id

        motors_b = await list_org_scoped_resources(session, Motor, org_b.id)
        assert len(motors_b) == 1
        assert motors_b[0].id == motor_b.id
