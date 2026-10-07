import uuid
import pytest
import asyncio
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

try:
    from app.db.base import Base, BaseModel
    from app.models.organization import Organization
    from app.models.site import Site, SiteType
    from app.models.station import Station, StationType
    from app.models.controller import Controller, ControllerType
    from app.models.sensor import Sensor, SensorStatus, SensorType
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
    from backend.app.models.sensor import Sensor, SensorStatus, SensorType
    from backend.app.db.session import (
        sync_engine,
        get_async_session,
        get_sync_session
    )


@pytest.fixture(scope="module", autouse=True)
def setup_sensor_tables():
    """Create all tables before running tests and drop after."""
    Base.metadata.create_all(bind=sync_engine)
    yield
    Base.metadata.drop_all(bind=sync_engine)


def test_sensor_model_inheritance_and_metadata():
    """Verify Sensor model inherits from BaseModel and exists in Base.metadata."""
    assert issubclass(Sensor, BaseModel)
    assert "sensors" in Base.metadata.tables
    table = Base.metadata.tables["sensors"]
    assert "id" in table.columns
    assert "controller_id" in table.columns
    assert "name" in table.columns
    assert "sensor_code" in table.columns
    assert "sensor_type" in table.columns
    assert "status" in table.columns
    assert "description" in table.columns
    assert "created_at" in table.columns
    assert "updated_at" in table.columns


def test_sensor_creation_and_defaults_sync():
    """Verify sensor creation with defaults."""
    with get_sync_session() as session:
        org = Organization(name="Sensor Org", organization_code="SENS-ORG")
        session.add(org)
        session.flush()

        site = Site(organization_id=org.id, name="Sensor Site", site_code="SENS-SITE", site_type=SiteType.OTHER)
        session.add(site)
        session.flush()

        stn = Station(site_id=site.id, name="Sensor Station", station_code="SENS-STN", station_type=StationType.OTHER)
        session.add(stn)
        session.flush()

        ctrl = Controller(
            station_id=stn.id,
            name="Sensor Controller",
            controller_code="SENS-CTRL-01",
            device_uid="ESP32-SENS-01",
            controller_type=ControllerType.ESP32
        )
        session.add(ctrl)
        session.flush()

        sensor = Sensor(
            controller_id=ctrl.id,
            name="Main Tank Level",
            sensor_code="SENS-01",
            description="Main overhead tank level sensor"
        )
        session.add(sensor)
        session.flush()

        assert sensor.id is not None
        assert isinstance(sensor.id, uuid.UUID)
        assert sensor.controller_id == ctrl.id
        assert sensor.name == "Main Tank Level"
        assert sensor.sensor_code == "SENS-01"
        assert sensor.sensor_type == SensorType.OTHER
        assert sensor.status == SensorStatus.ACTIVE
        assert sensor.description == "Main overhead tank level sensor"
        assert isinstance(sensor.created_at, datetime)
        assert isinstance(sensor.updated_at, datetime)
        sensor_id = sensor.id

    # Verify query
    with get_sync_session() as session:
        queried = session.get(Sensor, sensor_id)
        assert queried is not None
        assert queried.sensor_code == "SENS-01"
        assert "Main Tank Level" in str(queried)


def test_controller_scoped_sensor_code_uniqueness():
    """
    Verify multi-controller uniqueness:
    Controller A + S-01 = valid
    Controller B + S-01 = valid
    Controller A + S-01 again = raises IntegrityError
    """
    with get_sync_session() as session:
        org = Organization(name="Org For Sensor Scoped Codes", organization_code="ORG-S-SCOPED")
        session.add(org)
        session.flush()

        site = Site(organization_id=org.id, name="Site For Sensor Codes", site_code="SITE-S-CODES", site_type=SiteType.OTHER)
        session.add(site)
        session.flush()

        stn = Station(site_id=site.id, name="Station For Sensor Codes", station_code="STN-S-CODES", station_type=StationType.OTHER)
        session.add(stn)
        session.flush()

        c_a = Controller(
            station_id=stn.id,
            name="Controller Alpha S",
            controller_code="C-ALPHA-S",
            device_uid="DEV-S-ALPHA",
            controller_type=ControllerType.OTHER
        )
        c_b = Controller(
            station_id=stn.id,
            name="Controller Beta S",
            controller_code="C-BETA-S",
            device_uid="DEV-S-BETA",
            controller_type=ControllerType.OTHER
        )
        session.add_all([c_a, c_b])
        session.flush()

        s_a = Sensor(
            controller_id=c_a.id,
            name="Sensor A",
            sensor_code="S-100"
        )
        s_b = Sensor(
            controller_id=c_b.id,
            name="Sensor B",
            sensor_code="S-100"
        )
        session.add_all([s_a, s_b])
        session.flush()

        assert s_a.id is not None
        assert s_b.id is not None
        c_a_id = c_a.id

    # Inserting duplicate sensor_code in Controller A must fail
    with pytest.raises(IntegrityError):
        with get_sync_session() as session:
            dup_s = Sensor(
                controller_id=c_a_id,
                name="Duplicate Sensor",
                sensor_code="S-100"
            )
            session.add(dup_s)
            session.flush()


def test_sensor_types_coverage():
    """Verify all defined SensorType enum values are supported."""
    s_types = [
        SensorType.WATER_LEVEL,
        SensorType.TURBIDITY,
        SensorType.FLOW,
        SensorType.PRESSURE,
        SensorType.TEMPERATURE,
        SensorType.HUMIDITY,
        SensorType.CURRENT,
        SensorType.VOLTAGE,
        SensorType.PH,
        SensorType.OTHER,
    ]

    with get_sync_session() as session:
        org = Organization(name="S Types Org", organization_code="ORG-STYPES")
        session.add(org)
        session.flush()
        site = Site(organization_id=org.id, name="S Types Site", site_code="SITE-STYPES", site_type=SiteType.OTHER)
        session.add(site)
        session.flush()
        stn = Station(site_id=site.id, name="S Types Station", station_code="STN-STYPES", station_type=StationType.OTHER)
        session.add(stn)
        session.flush()
        c = Controller(
            station_id=stn.id,
            name="S Types Controller",
            controller_code="C-STYPES",
            device_uid="DEV-STYPES",
            controller_type=ControllerType.OTHER
        )
        session.add(c)
        session.flush()

        for idx, s_type in enumerate(s_types):
            s = Sensor(
                controller_id=c.id,
                name=f"Sensor {s_type.value}",
                sensor_code=f"STYPE-{idx:03d}",
                sensor_type=s_type
            )
            session.add(s)
        session.flush()
        c_id = c.id

    with get_sync_session() as session:
        sensors = session.execute(
            select(Sensor).where(Sensor.controller_id == c_id)
        ).scalars().all()
        assert len(sensors) == len(s_types)
        persisted_types = {s.sensor_type for s in sensors}
        assert persisted_types == set(s_types)


def test_sensor_status_states():
    """Verify all SensorStatus enum values."""
    statuses = [
        (SensorStatus.ACTIVE, "SS-001"),
        (SensorStatus.INACTIVE, "SS-002"),
        (SensorStatus.FAULT, "SS-003"),
        (SensorStatus.MAINTENANCE, "SS-004"),
        (SensorStatus.DISABLED, "SS-005"),
    ]

    with get_sync_session() as session:
        org = Organization(name="S Status Org", organization_code="ORG-SSTATUS")
        session.add(org)
        session.flush()
        site = Site(organization_id=org.id, name="S Status Site", site_code="SITE-SSTATUS", site_type=SiteType.OTHER)
        session.add(site)
        session.flush()
        stn = Station(site_id=site.id, name="S Status Station", station_code="STN-SSTATUS", station_type=StationType.OTHER)
        session.add(stn)
        session.flush()
        c = Controller(
            station_id=stn.id,
            name="S Status Controller",
            controller_code="C-SSTATUS",
            device_uid="DEV-SSTATUS",
            controller_type=ControllerType.OTHER
        )
        session.add(c)
        session.flush()

        for status, code in statuses:
            s = Sensor(
                controller_id=c.id,
                name=f"Sensor {status.value}",
                sensor_code=code,
                status=status
            )
            session.add(s)
        session.flush()

    with get_sync_session() as session:
        for status, code in statuses:
            s = session.execute(
                select(Sensor).where(Sensor.sensor_code == code)
            ).scalar_one()
            assert s.status == status


def test_controller_sensor_relationship_bidirectional():
    """Verify bidirectional relationship traversal: Controller.sensors and Sensor.controller."""
    with get_sync_session() as session:
        org = Organization(name="S Rel Org", organization_code="ORG-SREL")
        session.add(org)
        session.flush()
        site = Site(organization_id=org.id, name="S Rel Site", site_code="SITE-SREL", site_type=SiteType.OTHER)
        session.add(site)
        session.flush()
        stn = Station(site_id=site.id, name="S Rel Station", station_code="STN-SREL", station_type=StationType.OTHER)
        session.add(stn)
        session.flush()
        c = Controller(
            station_id=stn.id,
            name="S Rel Controller",
            controller_code="C-SREL",
            device_uid="DEV-SREL",
            controller_type=ControllerType.OTHER
        )
        session.add(c)
        session.flush()

        s1 = Sensor(
            controller=c,
            name="Sensor 1",
            sensor_code="SR-01",
        )
        s2 = Sensor(
            controller=c,
            name="Sensor 2",
            sensor_code="SR-02",
        )
        session.add_all([s1, s2])
        session.flush()

        c_id = c.id
        s1_id = s1.id

    # Verify Controller -> Sensors
    with get_sync_session() as session:
        fetched_c = session.get(Controller, c_id)
        assert fetched_c is not None
        assert len(fetched_c.sensors) == 2
        s_codes = [s.sensor_code for s in fetched_c.sensors]
        assert "SR-01" in s_codes
        assert "SR-02" in s_codes

    # Verify Sensor -> Controller
    with get_sync_session() as session:
        fetched_s = session.get(Sensor, s1_id)
        assert fetched_s is not None
        assert fetched_s.controller is not None
        assert fetched_s.controller.controller_code == "C-SREL"


@pytest.mark.asyncio
async def test_sensor_async_crud_and_updated_at():
    """Verify async session operations and updated_at changes."""
    async with get_async_session() as session:
        org = Organization(name="Async Org S", organization_code="ASYNC-ORG-S")
        session.add(org)
        await session.flush()
        site = Site(organization_id=org.id, name="Async Site S", site_code="ASYNC-SITE-S", site_type=SiteType.OTHER)
        session.add(site)
        await session.flush()
        stn = Station(site_id=site.id, name="Async Station S", station_code="ASYNC-STN-S", station_type=StationType.OTHER)
        session.add(stn)
        await session.flush()
        c = Controller(
            station_id=stn.id,
            name="Async Controller S",
            controller_code="ASYNC-C-S",
            device_uid="DEV-ASYNC-S",
            controller_type=ControllerType.OTHER
        )
        session.add(c)
        await session.flush()

        s = Sensor(
            controller_id=c.id,
            name="Async Sensor",
            sensor_code="ASYNC-S-01"
        )
        session.add(s)
        await session.flush()
        s_id = s.id
        initial_updated_at = s.updated_at

    await asyncio.sleep(0.05)

    async with get_async_session() as session:
        result = await session.execute(select(Sensor).where(Sensor.id == s_id))
        s_to_update = result.scalar_one()
        s_to_update.name = "Async Sensor Renamed"
        s_to_update.status = SensorStatus.MAINTENANCE
        await session.flush()

        assert s_to_update.name == "Async Sensor Renamed"
        assert s_to_update.status == SensorStatus.MAINTENANCE
        assert s_to_update.updated_at >= initial_updated_at


def test_sensor_missing_fields_fail():
    """Verify missing required fields raise IntegrityError."""
    with get_sync_session() as session:
        org = Organization(name="Fail Org S", organization_code="FAIL-ORG-S")
        session.add(org)
        session.flush()
        site = Site(organization_id=org.id, name="Fail Site S", site_code="FAIL-SITE-S", site_type=SiteType.OTHER)
        session.add(site)
        session.flush()
        stn = Station(site_id=site.id, name="Fail Station S", station_code="FAIL-STN-S", station_type=StationType.OTHER)
        session.add(stn)
        session.flush()
        c = Controller(
            station_id=stn.id,
            name="Fail Controller S",
            controller_code="FAIL-C-S",
            device_uid="FAIL-DEV-S",
            controller_type=ControllerType.OTHER
        )
        session.add(c)
        session.flush()
        c_id = c.id

    with pytest.raises(IntegrityError):
        with get_sync_session() as session:
            # Missing name
            s = Sensor(controller_id=c_id, sensor_code="S1")
            session.add(s)
            session.flush()
            
    with pytest.raises(IntegrityError):
        with get_sync_session() as session:
            # Missing sensor_code
            s = Sensor(controller_id=c_id, name="S1")
            session.add(s)
            session.flush()
            
    with pytest.raises(IntegrityError):
        with get_sync_session() as session:
            # Missing controller_id
            s = Sensor(name="S1", sensor_code="S1")
            session.add(s)
            session.flush()


def test_controller_deletion_restricted_with_sensors():
    """Verify that deleting a controller is restricted if it has sensors."""
    with get_sync_session() as session:
        org = Organization(name="Del Org S", organization_code="ORG-DEL-S")
        session.add(org)
        session.flush()
        site = Site(organization_id=org.id, name="Del Site S", site_code="SITE-DEL-S", site_type=SiteType.OTHER)
        session.add(site)
        session.flush()
        stn = Station(site_id=site.id, name="Del Station S", station_code="STN-DEL-S", station_type=StationType.OTHER)
        session.add(stn)
        session.flush()
        c = Controller(
            station_id=stn.id,
            name="Del Controller S",
            controller_code="C-DEL-S",
            device_uid="DEV-DEL-S",
            controller_type=ControllerType.OTHER
        )
        session.add(c)
        session.flush()
        
        s = Sensor(
            controller_id=c.id,
            name="Del Sensor",
            sensor_code="S-DEL"
        )
        session.add(s)
        session.flush()
        
        c_id = c.id
        
    with pytest.raises(IntegrityError):
        with get_sync_session() as session:
            controller_to_delete = session.get(Controller, c_id)
            session.delete(controller_to_delete)
            session.flush()
