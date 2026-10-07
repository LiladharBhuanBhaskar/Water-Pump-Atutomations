import uuid
import pytest
from datetime import datetime
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

try:
    from app.db.base import Base, BaseModel, utc_now
    from app.models.organization import Organization
    from app.models.site import Site, SiteType
    from app.models.station import Station, StationType
    from app.models.controller import Controller, ControllerType
    from app.models.sensor import Sensor, SensorType
    from app.models.motor import Motor
    from app.models.user import User, UserRole
    from app.models.automation_rule import (
        AutomationRule,
        AutomationRuleType,
        AutomationOperator,
        AutomationAction,
        AutomationRuleStatus
    )
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
    from backend.app.models.sensor import Sensor, SensorType
    from backend.app.models.motor import Motor
    from backend.app.models.user import User, UserRole
    from backend.app.models.automation_rule import (
        AutomationRule,
        AutomationRuleType,
        AutomationOperator,
        AutomationAction,
        AutomationRuleStatus
    )
    from backend.app.db.session import (
        sync_engine,
        get_async_session,
        get_sync_session
    )


@pytest.fixture(scope="module", autouse=True)
def setup_automation_tables():
    """Create all tables before running tests and drop after."""
    Base.metadata.create_all(bind=sync_engine)
    yield
    Base.metadata.drop_all(bind=sync_engine)


def test_automation_model_inheritance_and_metadata():
    """Verify AutomationRule model inherits from BaseModel and exists in Base.metadata."""
    assert issubclass(AutomationRule, BaseModel)
    assert "automation_rules" in Base.metadata.tables
    table = Base.metadata.tables["automation_rules"]
    assert "id" in table.columns
    assert "station_id" in table.columns
    assert "name" in table.columns
    assert "description" in table.columns
    assert "rule_type" in table.columns
    assert "status" in table.columns
    assert "sensor_id" in table.columns
    assert "operator" in table.columns
    assert "threshold_value" in table.columns
    assert "threshold_unit" in table.columns
    assert "duration_seconds" in table.columns
    assert "motor_id" in table.columns
    assert "action" in table.columns
    assert "cooldown_seconds" in table.columns
    assert "created_by" in table.columns


def _create_automation_hierarchy(session):
    unique_suffix = uuid.uuid4().hex[:6]
    user = User(
        email=f"auto_{unique_suffix}@example.com",
        name="Auto User",
        password_hash="hash",
        role=UserRole.ORGANIZATION_ADMIN
    )
    session.add(user)
    session.flush()

    org = Organization(name=f"Auto Org {unique_suffix}", organization_code=f"AUTO-ORG-{unique_suffix}")
    session.add(org)
    session.flush()

    site = Site(organization_id=org.id, name=f"Auto Site {unique_suffix}", site_code=f"AUTO-SITE-{unique_suffix}", site_type=SiteType.OTHER)
    session.add(site)
    session.flush()

    stn = Station(site_id=site.id, name=f"Auto Station {unique_suffix}", station_code=f"AUTO-STN-{unique_suffix}", station_type=StationType.OTHER)
    session.add(stn)
    session.flush()

    ctrl = Controller(
        station_id=stn.id,
        name=f"Auto Controller {unique_suffix}",
        controller_code=f"AUTO-CTRL-{unique_suffix}",
        device_uid=f"ESP32-AUTO-{unique_suffix}",
        controller_type=ControllerType.ESP32
    )
    session.add(ctrl)
    session.flush()

    sensor = Sensor(
        controller_id=ctrl.id,
        name=f"Auto Sensor {unique_suffix}",
        sensor_code=f"AUTO-S-{unique_suffix}",
        sensor_type=SensorType.WATER_LEVEL
    )
    session.add(sensor)
    
    motor = Motor(
        controller_id=ctrl.id,
        name=f"Auto Motor {unique_suffix}",
        motor_code=f"AUTO-M-{unique_suffix}"
    )
    session.add(motor)
    session.flush()

    return user, org, site, stn, ctrl, sensor, motor


def test_automation_creation_required_fields():
    """Verify creation with required fields."""
    with get_sync_session() as session:
        user, org, site, stn, ctrl, sensor, motor = _create_automation_hierarchy(session)

        rule = AutomationRule(
            station_id=stn.id,
            name="Test Required Fields Rule",
            rule_type=AutomationRuleType.TIMER,
            motor_id=motor.id,
            action=AutomationAction.START_MOTOR
        )
        session.add(rule)
        session.flush()

        assert rule.id is not None
        assert rule.station_id == stn.id
        assert rule.name == "Test Required Fields Rule"
        assert rule.rule_type == AutomationRuleType.TIMER
        assert rule.motor_id == motor.id
        assert rule.action == AutomationAction.START_MOTOR
        assert rule.status == AutomationRuleStatus.ACTIVE  # Default
        assert rule.description is None
        assert rule.sensor_id is None
        assert rule.operator is None
        assert rule.threshold_value is None
        assert rule.threshold_unit is None
        assert rule.duration_seconds is None
        assert rule.cooldown_seconds is None
        assert rule.created_by is None
        rule_id = rule.id

    with get_sync_session() as session:
        queried = session.get(AutomationRule, rule_id)
        assert queried is not None


def test_automation_full_water_level_rule():
    """Verify full WATER_LEVEL rule creation."""
    with get_sync_session() as session:
        user, org, site, stn, ctrl, sensor, motor = _create_automation_hierarchy(session)

        rule = AutomationRule(
            station_id=stn.id,
            name="High Water Stop",
            description="Stops motor when water level is high",
            rule_type=AutomationRuleType.WATER_LEVEL,
            status=AutomationRuleStatus.INACTIVE,
            sensor_id=sensor.id,
            operator=AutomationOperator.GREATER_THAN_OR_EQUAL,
            threshold_value=95.5,
            threshold_unit="percent",
            motor_id=motor.id,
            action=AutomationAction.STOP_MOTOR,
            cooldown_seconds=600,
            created_by=user.id
        )
        session.add(rule)
        session.flush()

        assert rule.sensor_id == sensor.id
        assert rule.threshold_value == Decimal("95.5")
        assert rule.cooldown_seconds == 600
        assert rule.created_by == user.id


def test_automation_enums_coverage():
    """Verify all defined Enums for AutomationRule."""
    a_types = [
        AutomationRuleType.WATER_LEVEL,
        AutomationRuleType.TURBIDITY,
        AutomationRuleType.TIMER
    ]

    a_ops = [
        AutomationOperator.GREATER_THAN,
        AutomationOperator.GREATER_THAN_OR_EQUAL,
        AutomationOperator.LESS_THAN,
        AutomationOperator.LESS_THAN_OR_EQUAL,
        AutomationOperator.EQUAL
    ]

    a_acts = [
        AutomationAction.START_MOTOR,
        AutomationAction.STOP_MOTOR,
        AutomationAction.RESET_MOTOR,
        AutomationAction.EMERGENCY_STOP_MOTOR
    ]

    a_stats = [
        AutomationRuleStatus.ACTIVE,
        AutomationRuleStatus.INACTIVE
    ]

    with get_sync_session() as session:
        user, org, site, stn, ctrl, sensor, motor = _create_automation_hierarchy(session)

        # Loop through a subset combining them
        for i, r_type in enumerate(a_types):
            op = a_ops[i % len(a_ops)]
            act = a_acts[i % len(a_acts)]
            stat = a_stats[i % len(a_stats)]

            rule = AutomationRule(
                station_id=stn.id,
                name=f"Rule {i}",
                rule_type=r_type,
                status=stat,
                sensor_id=sensor.id,
                operator=op,
                motor_id=motor.id,
                action=act
            )
            session.add(rule)
        session.flush()
        stn_id = stn.id

    with get_sync_session() as session:
        rules = session.execute(
            select(AutomationRule).where(AutomationRule.station_id == stn_id)
        ).scalars().all()
        assert len(rules) == len(a_types)


def test_automation_relationships():
    """Verify all relationships."""
    with get_sync_session() as session:
        user, org, site, stn, ctrl, sensor, motor = _create_automation_hierarchy(session)

        rule = AutomationRule(
            station=stn,
            name="Relationship Rule",
            rule_type=AutomationRuleType.TIMER,
            sensor=sensor,
            motor=motor,
            action=AutomationAction.START_MOTOR,
            creator=user
        )
        session.add(rule)
        session.flush()

        stn_id = stn.id
        sensor_id = sensor.id
        motor_id = motor.id
        user_id = user.id
        rule_id = rule.id

    # Verify relationships from the other side
    with get_sync_session() as session:
        fetched_stn = session.get(Station, stn_id)
        assert any(r.id == rule_id for r in fetched_stn.automation_rules)
        
        fetched_sensor = session.get(Sensor, sensor_id)
        assert any(r.id == rule_id for r in fetched_sensor.automation_rules)
        
        fetched_motor = session.get(Motor, motor_id)
        assert any(r.id == rule_id for r in fetched_motor.automation_rules)
        
        fetched_user = session.get(User, user_id)
        assert any(r.id == rule_id for r in fetched_user.created_automation_rules)
        
        fetched_rule = session.get(AutomationRule, rule_id)
        assert fetched_rule.station.id == stn_id
        assert fetched_rule.sensor.id == sensor_id
        assert fetched_rule.motor.id == motor_id
        assert fetched_rule.creator.id == user_id


@pytest.mark.asyncio
async def test_automation_async_crud():
    """Verify async session operations."""
    async with get_async_session() as session:
        unique_suffix = uuid.uuid4().hex[:6]
        
        org = Organization(name=f"Async Auto Org {unique_suffix}", organization_code=f"ASYNC-AUTO-ORG-{unique_suffix}")
        session.add(org)
        await session.flush()
        
        site = Site(organization_id=org.id, name=f"Async Auto Site {unique_suffix}", site_code=f"ASYNC-AUTO-SITE-{unique_suffix}", site_type=SiteType.OTHER)
        session.add(site)
        await session.flush()
        
        stn = Station(site_id=site.id, name=f"Async Auto Station {unique_suffix}", station_code=f"ASYNC-AUTO-STN-{unique_suffix}", station_type=StationType.OTHER)
        session.add(stn)
        await session.flush()
        
        ctrl = Controller(
            station_id=stn.id,
            name=f"Async Auto Controller {unique_suffix}",
            controller_code=f"ASYNC-AUTO-C-{unique_suffix}",
            device_uid=f"DEV-AUTO-ASYNC-{unique_suffix}",
            controller_type=ControllerType.OTHER
        )
        session.add(ctrl)
        await session.flush()
        
        motor = Motor(
            controller_id=ctrl.id,
            name=f"Async Auto Motor {unique_suffix}",
            motor_code=f"ASYNC-AUTO-M-{unique_suffix}"
        )
        session.add(motor)
        await session.flush()

        rule = AutomationRule(
            station_id=stn.id,
            name="Async Rule",
            rule_type=AutomationRuleType.TIMER,
            motor_id=motor.id,
            action=AutomationAction.RESET_MOTOR
        )
        session.add(rule)
        await session.flush()
        rule_id = rule.id

    async with get_async_session() as session:
        result = await session.execute(select(AutomationRule).where(AutomationRule.id == rule_id))
        rule_to_update = result.scalar_one()
        rule_to_update.name = "Updated Async Rule"
        await session.flush()

        assert rule_to_update.name == "Updated Async Rule"


def test_automation_missing_fields_fail():
    """Verify missing required fields raise IntegrityError."""
    with get_sync_session() as session:
        user, org, site, stn, ctrl, sensor, motor = _create_automation_hierarchy(session)

    with pytest.raises(IntegrityError):
        with get_sync_session() as session:
            # Missing station_id
            rule = AutomationRule(
                name="Missing station",
                rule_type=AutomationRuleType.TIMER,
                motor_id=motor.id,
                action=AutomationAction.START_MOTOR
            )
            session.add(rule)
            session.flush()
            
    with pytest.raises(IntegrityError):
        with get_sync_session() as session:
            # Missing name
            rule = AutomationRule(
                station_id=stn.id,
                rule_type=AutomationRuleType.TIMER,
                motor_id=motor.id,
                action=AutomationAction.START_MOTOR
            )
            session.add(rule)
            session.flush()
            
    with pytest.raises(IntegrityError):
        with get_sync_session() as session:
            # Missing rule_type
            rule = AutomationRule(
                station_id=stn.id,
                name="Missing rule type",
                motor_id=motor.id,
                action=AutomationAction.START_MOTOR
            )
            session.add(rule)
            session.flush()
            
    with pytest.raises(IntegrityError):
        with get_sync_session() as session:
            # Missing motor_id
            rule = AutomationRule(
                station_id=stn.id,
                name="Missing motor id",
                rule_type=AutomationRuleType.TIMER,
                action=AutomationAction.START_MOTOR
            )
            session.add(rule)
            session.flush()
            
    with pytest.raises(IntegrityError):
        with get_sync_session() as session:
            # Missing action
            rule = AutomationRule(
                station_id=stn.id,
                name="Missing action",
                rule_type=AutomationRuleType.TIMER,
                motor_id=motor.id
            )
            session.add(rule)
            session.flush()


def test_automation_fk_deletion_behaviors():
    """Verify station/motor deletion is restricted, sensor/user set null."""
    with get_sync_session() as session:
        user, org, site, stn, ctrl, sensor, motor = _create_automation_hierarchy(session)
        
        rule = AutomationRule(
            station_id=stn.id,
            name="Delete Behavior Rule",
            rule_type=AutomationRuleType.WATER_LEVEL,
            sensor_id=sensor.id,
            motor_id=motor.id,
            action=AutomationAction.STOP_MOTOR,
            created_by=user.id
        )
        session.add(rule)
        session.flush()
        
        stn_id = stn.id
        motor_id = motor.id
        sensor_id = sensor.id
        user_id = user.id
        rule_id = rule.id
        
    # 1. User deletion -> SET NULL
    with get_sync_session() as session:
        user_to_delete = session.get(User, user_id)
        session.delete(user_to_delete)
        session.flush()
        
    with get_sync_session() as session:
        rule_check = session.get(AutomationRule, rule_id)
        assert rule_check.created_by is None
        
    # 2. Sensor deletion -> SET NULL
    with get_sync_session() as session:
        sensor_to_delete = session.get(Sensor, sensor_id)
        session.delete(sensor_to_delete)
        session.flush()
        
    with get_sync_session() as session:
        rule_check = session.get(AutomationRule, rule_id)
        assert rule_check.sensor_id is None
        
    # 3. Motor deletion -> RESTRICT
    with pytest.raises(IntegrityError):
        with get_sync_session() as session:
            motor_to_delete = session.get(Motor, motor_id)
            session.delete(motor_to_delete)
            session.flush()
            
    # 4. Station deletion -> RESTRICT
    with pytest.raises(IntegrityError):
        with get_sync_session() as session:
            stn_to_delete = session.get(Station, stn_id)
            session.delete(stn_to_delete)
            session.flush()
