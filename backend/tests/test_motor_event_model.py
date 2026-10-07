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
    from app.models.motor_event import MotorEvent, MotorEventType, MotorEventSource
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
    from backend.app.models.motor_event import MotorEvent, MotorEventType, MotorEventSource
    from backend.app.db.session import (
        sync_engine,
        get_async_session,
        get_sync_session
    )


@pytest.fixture(scope="module", autouse=True)
def setup_event_tables():
    """Create all tables before running tests and drop after."""
    Base.metadata.create_all(bind=sync_engine)
    yield
    Base.metadata.drop_all(bind=sync_engine)


def test_motor_event_model_inheritance_and_metadata():
    """Verify MotorEvent model inherits from BaseModel and exists in Base.metadata."""
    assert issubclass(MotorEvent, BaseModel)
    assert "motor_events" in Base.metadata.tables
    table = Base.metadata.tables["motor_events"]
    assert "id" in table.columns
    assert "motor_id" in table.columns
    assert "event_type" in table.columns
    assert "source" in table.columns
    assert "occurred_at" in table.columns
    assert "event_payload" in table.columns
    assert "description" in table.columns
    assert "created_at" in table.columns
    assert "updated_at" in table.columns


def _create_event_hierarchy(session):
    unique_suffix = uuid.uuid4().hex[:6]
    org = Organization(name=f"Evt Org {unique_suffix}", organization_code=f"EVT-ORG-{unique_suffix}")
    session.add(org)
    session.flush()

    site = Site(organization_id=org.id, name=f"Evt Site {unique_suffix}", site_code=f"EVT-SITE-{unique_suffix}", site_type=SiteType.OTHER)
    session.add(site)
    session.flush()

    stn = Station(site_id=site.id, name=f"Evt Station {unique_suffix}", station_code=f"EVT-STN-{unique_suffix}", station_type=StationType.OTHER)
    session.add(stn)
    session.flush()

    ctrl = Controller(
        station_id=stn.id,
        name=f"Evt Controller {unique_suffix}",
        controller_code=f"EVT-CTRL-{unique_suffix}",
        device_uid=f"ESP32-EVT-{unique_suffix}",
        controller_type=ControllerType.ESP32
    )
    session.add(ctrl)
    session.flush()

    motor = Motor(
        controller_id=ctrl.id,
        name=f"Evt Motor {unique_suffix}",
        motor_code=f"EVT-M-{unique_suffix}"
    )
    session.add(motor)
    session.flush()

    return org, site, stn, ctrl, motor


def test_motor_event_creation_required_fields():
    """Verify event creation with required fields."""
    with get_sync_session() as session:
        _, _, _, _, motor = _create_event_hierarchy(session)

        now = utc_now()
        evt = MotorEvent(
            motor_id=motor.id,
            event_type=MotorEventType.STARTED,
            source=MotorEventSource.USER,
            occurred_at=now
        )
        session.add(evt)
        session.flush()

        assert evt.id is not None
        assert isinstance(evt.id, uuid.UUID)
        assert evt.motor_id == motor.id
        assert evt.event_type == MotorEventType.STARTED
        assert evt.source == MotorEventSource.USER
        assert evt.occurred_at == now
        assert evt.event_payload is None
        assert evt.description is None
        assert isinstance(evt.created_at, datetime)
        assert isinstance(evt.updated_at, datetime)
        evt_id = evt.id

    with get_sync_session() as session:
        queried = session.get(MotorEvent, evt_id)
        assert queried is not None
        assert queried.event_type == MotorEventType.STARTED


def test_motor_event_with_payload_and_description():
    """Verify event creation with optional fields."""
    with get_sync_session() as session:
        _, _, _, _, motor = _create_event_hierarchy(session)

        now = utc_now()
        payload = {"reason": "tank_full"}
        evt = MotorEvent(
            motor_id=motor.id,
            event_type=MotorEventType.STOPPED,
            source=MotorEventSource.SENSOR,
            occurred_at=now,
            event_payload=payload,
            description="Tank has reached full capacity"
        )
        session.add(evt)
        session.flush()

        assert evt.event_payload == payload
        assert evt.description == "Tank has reached full capacity"


def test_event_types_and_sources_coverage():
    """Verify all defined MotorEventType and MotorEventSource enum values."""
    e_types = [
        MotorEventType.STARTED,
        MotorEventType.STOPPED,
        MotorEventType.FAULT,
        MotorEventType.RESET,
        MotorEventType.EMERGENCY_STOP,
        MotorEventType.OFFLINE,
        MotorEventType.ONLINE
    ]

    e_sources = [
        MotorEventSource.USER,
        MotorEventSource.CONTROLLER,
        MotorEventSource.SYSTEM,
        MotorEventSource.SENSOR,
        MotorEventSource.AUTOMATION
    ]

    with get_sync_session() as session:
        _, _, _, _, motor = _create_event_hierarchy(session)
        now = utc_now()

        for e_type in e_types:
            for source in e_sources:
                evt = MotorEvent(
                    motor_id=motor.id,
                    event_type=e_type,
                    source=source,
                    occurred_at=now
                )
                session.add(evt)
        session.flush()
        motor_id = motor.id

    with get_sync_session() as session:
        events = session.execute(
            select(MotorEvent).where(MotorEvent.motor_id == motor_id)
        ).scalars().all()
        assert len(events) == len(e_types) * len(e_sources)


def test_motor_event_relationship_bidirectional():
    """Verify bidirectional relationship traversal: Motor.events and MotorEvent.motor."""
    with get_sync_session() as session:
        _, _, _, _, motor = _create_event_hierarchy(session)
        now = utc_now()

        evt1 = MotorEvent(
            motor=motor,
            event_type=MotorEventType.STARTED,
            source=MotorEventSource.SYSTEM,
            occurred_at=now
        )
        evt2 = MotorEvent(
            motor=motor,
            event_type=MotorEventType.STOPPED,
            source=MotorEventSource.SYSTEM,
            occurred_at=now
        )
        session.add_all([evt1, evt2])
        session.flush()

        motor_id = motor.id
        evt1_id = evt1.id

    # Verify Motor -> Events
    with get_sync_session() as session:
        fetched_motor = session.get(Motor, motor_id)
        assert fetched_motor is not None
        assert len(fetched_motor.events) >= 2
        
    # Verify Event -> Motor
    with get_sync_session() as session:
        fetched_evt = session.get(MotorEvent, evt1_id)
        assert fetched_evt is not None
        assert fetched_evt.motor is not None
        assert fetched_evt.motor.id == motor_id


@pytest.mark.asyncio
async def test_motor_event_async_crud():
    """Verify async session operations."""
    async with get_async_session() as session:
        unique_suffix = uuid.uuid4().hex[:6]
        org = Organization(name=f"Async Evt Org {unique_suffix}", organization_code=f"ASYNC-EVT-ORG-{unique_suffix}")
        session.add(org)
        await session.flush()
        site = Site(organization_id=org.id, name=f"Async Evt Site {unique_suffix}", site_code=f"ASYNC-EVT-SITE-{unique_suffix}", site_type=SiteType.OTHER)
        session.add(site)
        await session.flush()
        stn = Station(site_id=site.id, name=f"Async Evt Station {unique_suffix}", station_code=f"ASYNC-EVT-STN-{unique_suffix}", station_type=StationType.OTHER)
        session.add(stn)
        await session.flush()
        ctrl = Controller(
            station_id=stn.id,
            name=f"Async Evt Controller {unique_suffix}",
            controller_code=f"ASYNC-EVT-C-{unique_suffix}",
            device_uid=f"DEV-EVT-ASYNC-{unique_suffix}",
            controller_type=ControllerType.OTHER
        )
        session.add(ctrl)
        await session.flush()
        motor = Motor(
            controller_id=ctrl.id,
            name=f"Async Evt Motor {unique_suffix}",
            motor_code=f"ASYNC-EVT-M-{unique_suffix}"
        )
        session.add(motor)
        await session.flush()

        now = utc_now()
        evt = MotorEvent(
            motor_id=motor.id,
            event_type=MotorEventType.FAULT,
            source=MotorEventSource.CONTROLLER,
            occurred_at=now
        )
        session.add(evt)
        await session.flush()
        evt_id = evt.id

    async with get_async_session() as session:
        result = await session.execute(select(MotorEvent).where(MotorEvent.id == evt_id))
        evt_to_update = result.scalar_one()
        evt_to_update.description = "Async updated"
        await session.flush()

        assert evt_to_update.description == "Async updated"


def test_motor_event_missing_fields_fail():
    """Verify missing required fields raise IntegrityError."""
    with get_sync_session() as session:
        _, _, _, _, motor = _create_event_hierarchy(session)
        motor_id = motor.id

    with pytest.raises(IntegrityError):
        with get_sync_session() as session:
            # Missing event_type
            evt = MotorEvent(
                motor_id=motor_id,
                source=MotorEventSource.SYSTEM,
                occurred_at=utc_now()
            )
            session.add(evt)
            session.flush()
            
    with pytest.raises(IntegrityError):
        with get_sync_session() as session:
            # Missing source
            evt = MotorEvent(
                motor_id=motor_id,
                event_type=MotorEventType.STARTED,
                occurred_at=utc_now()
            )
            session.add(evt)
            session.flush()
            
    with pytest.raises(IntegrityError):
        with get_sync_session() as session:
            # Missing occurred_at
            evt = MotorEvent(
                motor_id=motor_id,
                event_type=MotorEventType.STARTED,
                source=MotorEventSource.SYSTEM
            )
            session.add(evt)
            session.flush()
            
    with pytest.raises(IntegrityError):
        with get_sync_session() as session:
            # Missing motor_id
            evt = MotorEvent(
                event_type=MotorEventType.STARTED,
                source=MotorEventSource.SYSTEM,
                occurred_at=utc_now()
            )
            session.add(evt)
            session.flush()


def test_motor_deletion_restricted_with_events():
    """Verify that deleting a motor is restricted if it has events."""
    with get_sync_session() as session:
        _, _, _, _, motor = _create_event_hierarchy(session)
        now = utc_now()
        
        evt = MotorEvent(
            motor_id=motor.id,
            event_type=MotorEventType.STARTED,
            source=MotorEventSource.SYSTEM,
            occurred_at=now
        )
        session.add(evt)
        session.flush()
        
        motor_id = motor.id
        
    with pytest.raises(IntegrityError):
        with get_sync_session() as session:
            motor_to_delete = session.get(Motor, motor_id)
            session.delete(motor_to_delete)
            session.flush()
