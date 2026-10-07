import uuid
import pytest
from datetime import datetime, timezone, timedelta
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
    from app.models.telemetry import TelemetryReading
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
    from backend.app.models.telemetry import TelemetryReading
    from backend.app.db.session import (
        sync_engine,
        get_async_session,
        get_sync_session
    )


@pytest.fixture(scope="module", autouse=True)
def setup_telemetry_tables():
    """Create all tables before running tests and drop after."""
    Base.metadata.create_all(bind=sync_engine)
    yield
    Base.metadata.drop_all(bind=sync_engine)


def test_telemetry_model_inheritance_and_metadata():
    """Verify TelemetryReading model inherits from BaseModel and exists in Base.metadata."""
    assert issubclass(TelemetryReading, BaseModel)
    assert "telemetry_readings" in Base.metadata.tables
    table = Base.metadata.tables["telemetry_readings"]
    assert "id" in table.columns
    assert "sensor_id" in table.columns
    assert "value" in table.columns
    assert "unit" in table.columns
    assert "occurred_at" in table.columns
    assert "metadata" in table.columns
    assert "created_at" in table.columns
    assert "updated_at" in table.columns


def _create_telemetry_hierarchy(session):
    unique_suffix = uuid.uuid4().hex[:6]
    org = Organization(name=f"Tel Org {unique_suffix}", organization_code=f"TEL-ORG-{unique_suffix}")
    session.add(org)
    session.flush()

    site = Site(organization_id=org.id, name=f"Tel Site {unique_suffix}", site_code=f"TEL-SITE-{unique_suffix}", site_type=SiteType.OTHER)
    session.add(site)
    session.flush()

    stn = Station(site_id=site.id, name=f"Tel Station {unique_suffix}", station_code=f"TEL-STN-{unique_suffix}", station_type=StationType.OTHER)
    session.add(stn)
    session.flush()

    ctrl = Controller(
        station_id=stn.id,
        name=f"Tel Controller {unique_suffix}",
        controller_code=f"TEL-CTRL-{unique_suffix}",
        device_uid=f"ESP32-TEL-{unique_suffix}",
        controller_type=ControllerType.ESP32
    )
    session.add(ctrl)
    session.flush()

    sensor = Sensor(
        controller_id=ctrl.id,
        name=f"Tel Sensor {unique_suffix}",
        sensor_code=f"TEL-S-{unique_suffix}",
        sensor_type=SensorType.WATER_LEVEL
    )
    session.add(sensor)
    session.flush()

    return org, site, stn, ctrl, sensor


def test_telemetry_creation_required_fields():
    """Verify creation with required fields."""
    with get_sync_session() as session:
        _, _, _, _, sensor = _create_telemetry_hierarchy(session)

        now = utc_now()
        read = TelemetryReading(
            sensor_id=sensor.id,
            value=95.5,
            unit="percent",
            occurred_at=now
        )
        session.add(read)
        session.flush()

        assert read.id is not None
        assert isinstance(read.id, uuid.UUID)
        assert read.sensor_id == sensor.id
        assert read.value == Decimal("95.5")
        assert read.unit == "percent"
        assert read.occurred_at == now
        assert read.metadata_ is None
        assert isinstance(read.created_at, datetime)
        assert isinstance(read.updated_at, datetime)
        read_id = read.id

    with get_sync_session() as session:
        queried = session.get(TelemetryReading, read_id)
        assert queried is not None
        assert queried.value == Decimal("95.5")


def test_telemetry_precision():
    """Verify numeric precision is preserved."""
    with get_sync_session() as session:
        _, _, _, _, sensor = _create_telemetry_hierarchy(session)
        
        now = utc_now()
        val = 123.456789
        read = TelemetryReading(
            sensor_id=sensor.id,
            value=val,
            unit="psi",
            occurred_at=now
        )
        session.add(read)
        session.flush()
        read_id = read.id
        
    with get_sync_session() as session:
        queried = session.get(TelemetryReading, read_id)
        assert queried.value == Decimal("123.456789")


def test_telemetry_with_metadata():
    """Verify creation with optional JSON metadata."""
    with get_sync_session() as session:
        _, _, _, _, sensor = _create_telemetry_hierarchy(session)

        now = utc_now()
        meta = {"raw_value": 812, "quality": "GOOD"}
        read = TelemetryReading(
            sensor_id=sensor.id,
            value=95.5,
            unit="percent",
            occurred_at=now,
            metadata_=meta
        )
        session.add(read)
        session.flush()

        assert read.metadata_ == meta


def test_telemetry_relationship_bidirectional():
    """Verify bidirectional relationship: Sensor.telemetry_readings and TelemetryReading.sensor."""
    with get_sync_session() as session:
        _, _, _, _, sensor = _create_telemetry_hierarchy(session)
        now = utc_now()

        read1 = TelemetryReading(
            sensor=sensor,
            value=10.0,
            unit="liters",
            occurred_at=now
        )
        read2 = TelemetryReading(
            sensor=sensor,
            value=20.0,
            unit="liters",
            occurred_at=now
        )
        session.add_all([read1, read2])
        session.flush()

        sensor_id = sensor.id
        read1_id = read1.id

    # Verify Sensor -> Readings
    with get_sync_session() as session:
        fetched_sensor = session.get(Sensor, sensor_id)
        assert fetched_sensor is not None
        assert len(fetched_sensor.telemetry_readings) >= 2
        
    # Verify Reading -> Sensor
    with get_sync_session() as session:
        fetched_read = session.get(TelemetryReading, read1_id)
        assert fetched_read is not None
        assert fetched_read.sensor is not None
        assert fetched_read.sensor.id == sensor_id


def test_occurred_at_vs_created_at():
    """Verify occurred_at and created_at remain distinct."""
    with get_sync_session() as session:
        _, _, _, _, sensor = _create_telemetry_hierarchy(session)
        
        past_time = utc_now() - timedelta(hours=1)
        
        read = TelemetryReading(
            sensor_id=sensor.id,
            value=50.0,
            unit="percent",
            occurred_at=past_time
        )
        session.add(read)
        session.flush()
        
        assert read.occurred_at == past_time
        assert read.created_at > past_time
        assert read.created_at != read.occurred_at


@pytest.mark.asyncio
async def test_telemetry_async_crud():
    """Verify async session operations."""
    async with get_async_session() as session:
        unique_suffix = uuid.uuid4().hex[:6]
        org = Organization(name=f"Async Tel Org {unique_suffix}", organization_code=f"ASYNC-TEL-ORG-{unique_suffix}")
        session.add(org)
        await session.flush()
        site = Site(organization_id=org.id, name=f"Async Tel Site {unique_suffix}", site_code=f"ASYNC-TEL-SITE-{unique_suffix}", site_type=SiteType.OTHER)
        session.add(site)
        await session.flush()
        stn = Station(site_id=site.id, name=f"Async Tel Station {unique_suffix}", station_code=f"ASYNC-TEL-STN-{unique_suffix}", station_type=StationType.OTHER)
        session.add(stn)
        await session.flush()
        ctrl = Controller(
            station_id=stn.id,
            name=f"Async Tel Controller {unique_suffix}",
            controller_code=f"ASYNC-TEL-C-{unique_suffix}",
            device_uid=f"DEV-TEL-ASYNC-{unique_suffix}",
            controller_type=ControllerType.OTHER
        )
        session.add(ctrl)
        await session.flush()
        sensor = Sensor(
            controller_id=ctrl.id,
            name=f"Async Tel Sensor {unique_suffix}",
            sensor_code=f"ASYNC-TEL-S-{unique_suffix}",
            sensor_type=SensorType.WATER_LEVEL
        )
        session.add(sensor)
        await session.flush()

        now = utc_now()
        read = TelemetryReading(
            sensor_id=sensor.id,
            value=75.0,
            unit="percent",
            occurred_at=now
        )
        session.add(read)
        await session.flush()
        read_id = read.id

    async with get_async_session() as session:
        result = await session.execute(select(TelemetryReading).where(TelemetryReading.id == read_id))
        read_to_update = result.scalar_one()
        read_to_update.unit = "C"
        await session.flush()

        assert read_to_update.unit == "C"


def test_telemetry_missing_fields_fail():
    """Verify missing required fields raise IntegrityError."""
    with get_sync_session() as session:
        _, _, _, _, sensor = _create_telemetry_hierarchy(session)
        sensor_id = sensor.id

    with pytest.raises(IntegrityError):
        with get_sync_session() as session:
            # Missing value
            read = TelemetryReading(
                sensor_id=sensor_id,
                unit="percent",
                occurred_at=utc_now()
            )
            session.add(read)
            session.flush()
            
    with pytest.raises(IntegrityError):
        with get_sync_session() as session:
            # Missing unit
            read = TelemetryReading(
                sensor_id=sensor_id,
                value=50.0,
                occurred_at=utc_now()
            )
            session.add(read)
            session.flush()
            
    with pytest.raises(IntegrityError):
        with get_sync_session() as session:
            # Missing occurred_at
            read = TelemetryReading(
                sensor_id=sensor_id,
                value=50.0,
                unit="percent"
            )
            session.add(read)
            session.flush()
            
    with pytest.raises(IntegrityError):
        with get_sync_session() as session:
            # Missing sensor_id
            read = TelemetryReading(
                value=50.0,
                unit="percent",
                occurred_at=utc_now()
            )
            session.add(read)
            session.flush()


def test_sensor_deletion_restricted_with_telemetry():
    """Verify that deleting a sensor is restricted if it has telemetry."""
    with get_sync_session() as session:
        _, _, _, _, sensor = _create_telemetry_hierarchy(session)
        now = utc_now()
        
        read = TelemetryReading(
            sensor_id=sensor.id,
            value=50.0,
            unit="percent",
            occurred_at=now
        )
        session.add(read)
        session.flush()
        
        sensor_id = sensor.id
        
    with pytest.raises(IntegrityError):
        with get_sync_session() as session:
            sensor_to_delete = session.get(Sensor, sensor_id)
            session.delete(sensor_to_delete)
            session.flush()
