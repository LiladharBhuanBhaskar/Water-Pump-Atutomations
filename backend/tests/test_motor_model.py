import uuid
import pytest
import asyncio
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from decimal import Decimal

try:
    from app.db.base import Base, BaseModel
    from app.models.organization import Organization
    from app.models.site import Site, SiteType
    from app.models.station import Station, StationType
    from app.models.controller import Controller, ControllerType
    from app.models.motor import Motor, MotorStatus, MotorType
    from app.db.session import (
        sync_engine,
        get_async_session,
        get_sync_session
    )
except ImportError:
    from backend.app.db.base import Base, BaseModel
    from backend.app.models.organization import Organization
    from backend.app.models.site import Site, SiteType
    from backend.app.models.station import Station, StationType
    from backend.app.models.controller import Controller, ControllerType
    from backend.app.models.motor import Motor, MotorStatus, MotorType
    from backend.app.db.session import (
        sync_engine,
        get_async_session,
        get_sync_session
    )


@pytest.fixture(scope="module", autouse=True)
def setup_motor_tables():
    """Create all tables before running tests and drop after."""
    Base.metadata.create_all(bind=sync_engine)
    yield
    Base.metadata.drop_all(bind=sync_engine)


def test_motor_model_inheritance_and_metadata():
    """Verify Motor model inherits from BaseModel and exists in Base.metadata."""
    assert issubclass(Motor, BaseModel)
    assert "motors" in Base.metadata.tables
    table = Base.metadata.tables["motors"]
    assert "id" in table.columns
    assert "controller_id" in table.columns
    assert "name" in table.columns
    assert "motor_code" in table.columns
    assert "motor_type" in table.columns
    assert "status" in table.columns
    assert "rated_power" in table.columns
    assert "description" in table.columns
    assert "created_at" in table.columns
    assert "updated_at" in table.columns


def test_motor_creation_and_defaults_sync():
    """Verify motor creation with defaults."""
    with get_sync_session() as session:
        org = Organization(name="Motor Org", organization_code="MOT-ORG")
        session.add(org)
        session.flush()

        site = Site(organization_id=org.id, name="Motor Site", site_code="MOT-SITE", site_type=SiteType.OTHER)
        session.add(site)
        session.flush()

        stn = Station(site_id=site.id, name="Motor Station", station_code="MOT-STN", station_type=StationType.OTHER)
        session.add(stn)
        session.flush()

        ctrl = Controller(
            station_id=stn.id,
            name="Motor Controller",
            controller_code="MOT-CTRL-01",
            device_uid="ESP32-MOT-01",
            controller_type=ControllerType.ESP32
        )
        session.add(ctrl)
        session.flush()

        motor = Motor(
            controller_id=ctrl.id,
            name="Main Pump",
            motor_code="PUMP-01",
            rated_power=Decimal("5.50"),
            description="Main irrigation pump"
        )
        session.add(motor)
        session.flush()

        assert motor.id is not None
        assert isinstance(motor.id, uuid.UUID)
        assert motor.controller_id == ctrl.id
        assert motor.name == "Main Pump"
        assert motor.motor_code == "PUMP-01"
        assert motor.motor_type == MotorType.WATER_PUMP
        assert motor.status == MotorStatus.OFFLINE
        assert motor.rated_power == Decimal("5.50")
        assert motor.description == "Main irrigation pump"
        assert isinstance(motor.created_at, datetime)
        assert isinstance(motor.updated_at, datetime)
        motor_id = motor.id

    # Verify query
    with get_sync_session() as session:
        queried = session.get(Motor, motor_id)
        assert queried is not None
        assert queried.motor_code == "PUMP-01"
        assert "Main Pump" in str(queried)


def test_controller_scoped_motor_code_uniqueness():
    """
    Verify multi-controller uniqueness:
    Controller A + M-01 = valid
    Controller B + M-01 = valid
    Controller A + M-01 again = raises IntegrityError
    """
    with get_sync_session() as session:
        org = Organization(name="Org For Motor Scoped Codes", organization_code="ORG-M-SCOPED")
        session.add(org)
        session.flush()

        site = Site(organization_id=org.id, name="Site For Motor Codes", site_code="SITE-M-CODES", site_type=SiteType.OTHER)
        session.add(site)
        session.flush()

        stn = Station(site_id=site.id, name="Station For Motor Codes", station_code="STN-M-CODES", station_type=StationType.OTHER)
        session.add(stn)
        session.flush()

        c_a = Controller(
            station_id=stn.id,
            name="Controller Alpha",
            controller_code="C-ALPHA",
            device_uid="DEV-M-ALPHA",
            controller_type=ControllerType.OTHER
        )
        c_b = Controller(
            station_id=stn.id,
            name="Controller Beta",
            controller_code="C-BETA",
            device_uid="DEV-M-BETA",
            controller_type=ControllerType.OTHER
        )
        session.add_all([c_a, c_b])
        session.flush()

        m_a = Motor(
            controller_id=c_a.id,
            name="Motor A",
            motor_code="M-100"
        )
        m_b = Motor(
            controller_id=c_b.id,
            name="Motor B",
            motor_code="M-100"
        )
        session.add_all([m_a, m_b])
        session.flush()

        assert m_a.id is not None
        assert m_b.id is not None
        c_a_id = c_a.id

    # Inserting duplicate motor_code in Controller A must fail
    with pytest.raises(IntegrityError):
        with get_sync_session() as session:
            dup_m = Motor(
                controller_id=c_a_id,
                name="Duplicate Motor",
                motor_code="M-100"
            )
            session.add(dup_m)
            session.flush()


def test_motor_types_coverage():
    """Verify all defined MotorType enum values are supported."""
    m_types = [
        MotorType.WATER_PUMP,
        MotorType.SUBMERSIBLE_PUMP,
        MotorType.BOREWELL_PUMP,
        MotorType.BOOSTER_PUMP,
        MotorType.IRRIGATION_PUMP,
        MotorType.CENTRIFUGAL_PUMP,
        MotorType.INDUSTRIAL_PUMP,
        MotorType.OTHER,
    ]

    with get_sync_session() as session:
        org = Organization(name="M Types Org", organization_code="ORG-MTYPES")
        session.add(org)
        session.flush()
        site = Site(organization_id=org.id, name="M Types Site", site_code="SITE-MTYPES", site_type=SiteType.OTHER)
        session.add(site)
        session.flush()
        stn = Station(site_id=site.id, name="M Types Station", station_code="STN-MTYPES", station_type=StationType.OTHER)
        session.add(stn)
        session.flush()
        c = Controller(
            station_id=stn.id,
            name="M Types Controller",
            controller_code="C-MTYPES",
            device_uid="DEV-MTYPES",
            controller_type=ControllerType.OTHER
        )
        session.add(c)
        session.flush()

        for idx, m_type in enumerate(m_types):
            m = Motor(
                controller_id=c.id,
                name=f"Motor {m_type.value}",
                motor_code=f"MTYPE-{idx:03d}",
                motor_type=m_type
            )
            session.add(m)
        session.flush()
        c_id = c.id

    with get_sync_session() as session:
        motors = session.execute(
            select(Motor).where(Motor.controller_id == c_id)
        ).scalars().all()
        assert len(motors) == len(m_types)
        persisted_types = {m.motor_type for m in motors}
        assert persisted_types == set(m_types)


def test_motor_status_states():
    """Verify all MotorStatus enum values."""
    statuses = [
        (MotorStatus.OFFLINE, "MS-001"),
        (MotorStatus.OFF, "MS-002"),
        (MotorStatus.ON, "MS-003"),
        (MotorStatus.STARTING, "MS-004"),
        (MotorStatus.STOPPING, "MS-005"),
        (MotorStatus.FAULT, "MS-006"),
        (MotorStatus.MAINTENANCE, "MS-007"),
        (MotorStatus.DISABLED, "MS-008"),
    ]

    with get_sync_session() as session:
        org = Organization(name="M Status Org", organization_code="ORG-MSTATUS")
        session.add(org)
        session.flush()
        site = Site(organization_id=org.id, name="M Status Site", site_code="SITE-MSTATUS", site_type=SiteType.OTHER)
        session.add(site)
        session.flush()
        stn = Station(site_id=site.id, name="M Status Station", station_code="STN-MSTATUS", station_type=StationType.OTHER)
        session.add(stn)
        session.flush()
        c = Controller(
            station_id=stn.id,
            name="M Status Controller",
            controller_code="C-MSTATUS",
            device_uid="DEV-MSTATUS",
            controller_type=ControllerType.OTHER
        )
        session.add(c)
        session.flush()

        for status, code in statuses:
            m = Motor(
                controller_id=c.id,
                name=f"Motor {status.value}",
                motor_code=code,
                status=status
            )
            session.add(m)
        session.flush()

    with get_sync_session() as session:
        for status, code in statuses:
            m = session.execute(
                select(Motor).where(Motor.motor_code == code)
            ).scalar_one()
            assert m.status == status


def test_controller_motor_relationship_bidirectional():
    """Verify bidirectional relationship traversal: Controller.motors and Motor.controller."""
    with get_sync_session() as session:
        org = Organization(name="M Rel Org", organization_code="ORG-MREL")
        session.add(org)
        session.flush()
        site = Site(organization_id=org.id, name="M Rel Site", site_code="SITE-MREL", site_type=SiteType.OTHER)
        session.add(site)
        session.flush()
        stn = Station(site_id=site.id, name="M Rel Station", station_code="STN-MREL", station_type=StationType.OTHER)
        session.add(stn)
        session.flush()
        c = Controller(
            station_id=stn.id,
            name="M Rel Controller",
            controller_code="C-MREL",
            device_uid="DEV-MREL",
            controller_type=ControllerType.OTHER
        )
        session.add(c)
        session.flush()

        m1 = Motor(
            controller=c,
            name="Motor 1",
            motor_code="MR-01",
        )
        m2 = Motor(
            controller=c,
            name="Motor 2",
            motor_code="MR-02",
        )
        session.add_all([m1, m2])
        session.flush()

        c_id = c.id
        m1_id = m1.id

    # Verify Controller -> Motors
    with get_sync_session() as session:
        fetched_c = session.get(Controller, c_id)
        assert fetched_c is not None
        assert len(fetched_c.motors) == 2
        m_codes = [m.motor_code for m in fetched_c.motors]
        assert "MR-01" in m_codes
        assert "MR-02" in m_codes

    # Verify Motor -> Controller
    with get_sync_session() as session:
        fetched_m = session.get(Motor, m1_id)
        assert fetched_m is not None
        assert fetched_m.controller is not None
        assert fetched_m.controller.controller_code == "C-MREL"


@pytest.mark.asyncio
async def test_motor_async_crud_and_updated_at():
    """Verify async session operations and updated_at changes."""
    async with get_async_session() as session:
        org = Organization(name="Async Org M", organization_code="ASYNC-ORG-M")
        session.add(org)
        await session.flush()
        site = Site(organization_id=org.id, name="Async Site M", site_code="ASYNC-SITE-M", site_type=SiteType.OTHER)
        session.add(site)
        await session.flush()
        stn = Station(site_id=site.id, name="Async Station M", station_code="ASYNC-STN-M", station_type=StationType.OTHER)
        session.add(stn)
        await session.flush()
        c = Controller(
            station_id=stn.id,
            name="Async Controller M",
            controller_code="ASYNC-C-M",
            device_uid="DEV-ASYNC-M",
            controller_type=ControllerType.OTHER
        )
        session.add(c)
        await session.flush()

        m = Motor(
            controller_id=c.id,
            name="Async Motor",
            motor_code="ASYNC-M-01"
        )
        session.add(m)
        await session.flush()
        m_id = m.id
        initial_updated_at = m.updated_at

    await asyncio.sleep(0.05)

    async with get_async_session() as session:
        result = await session.execute(select(Motor).where(Motor.id == m_id))
        m_to_update = result.scalar_one()
        m_to_update.name = "Async Motor Renamed"
        m_to_update.status = MotorStatus.MAINTENANCE
        await session.flush()

        assert m_to_update.name == "Async Motor Renamed"
        assert m_to_update.status == MotorStatus.MAINTENANCE
        assert m_to_update.updated_at >= initial_updated_at


def test_motor_missing_fields_fail():
    """Verify missing required fields raise IntegrityError."""
    with get_sync_session() as session:
        org = Organization(name="Fail Org M", organization_code="FAIL-ORG-M")
        session.add(org)
        session.flush()
        site = Site(organization_id=org.id, name="Fail Site M", site_code="FAIL-SITE-M", site_type=SiteType.OTHER)
        session.add(site)
        session.flush()
        stn = Station(site_id=site.id, name="Fail Station M", station_code="FAIL-STN-M", station_type=StationType.OTHER)
        session.add(stn)
        session.flush()
        c = Controller(
            station_id=stn.id,
            name="Fail Controller M",
            controller_code="FAIL-C-M",
            device_uid="FAIL-DEV-M",
            controller_type=ControllerType.OTHER
        )
        session.add(c)
        session.flush()
        c_id = c.id

    with pytest.raises(IntegrityError):
        with get_sync_session() as session:
            # Missing name
            m = Motor(controller_id=c_id, motor_code="M1")
            session.add(m)
            session.flush()
            
    with pytest.raises(IntegrityError):
        with get_sync_session() as session:
            # Missing motor_code
            m = Motor(controller_id=c_id, name="M1")
            session.add(m)
            session.flush()
            
    with pytest.raises(IntegrityError):
        with get_sync_session() as session:
            # Missing controller_id
            m = Motor(name="M1", motor_code="M1")
            session.add(m)
            session.flush()


def test_controller_deletion_restricted_with_motors():
    """Verify that deleting a controller is restricted if it has motors."""
    with get_sync_session() as session:
        org = Organization(name="Del Org", organization_code="ORG-DEL")
        session.add(org)
        session.flush()
        site = Site(organization_id=org.id, name="Del Site", site_code="SITE-DEL", site_type=SiteType.OTHER)
        session.add(site)
        session.flush()
        stn = Station(site_id=site.id, name="Del Station", station_code="STN-DEL", station_type=StationType.OTHER)
        session.add(stn)
        session.flush()
        c = Controller(
            station_id=stn.id,
            name="Del Controller",
            controller_code="C-DEL",
            device_uid="DEV-DEL",
            controller_type=ControllerType.OTHER
        )
        session.add(c)
        session.flush()
        
        m = Motor(
            controller_id=c.id,
            name="Del Motor",
            motor_code="M-DEL"
        )
        session.add(m)
        session.flush()
        
        c_id = c.id
        
    with pytest.raises(IntegrityError):
        with get_sync_session() as session:
            controller_to_delete = session.get(Controller, c_id)
            session.delete(controller_to_delete)
            session.flush()
