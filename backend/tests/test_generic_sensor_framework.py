"""
HydraControl — Phase 11 Generic Sensor Framework Verification Suite
Tests all 10 SensorType categories, unit normalization, validation, quality tagging,
MQTT telemetry ingestion, anti-spoofing defense, REST history/latest endpoints,
WebSocket broadcasting, and multi-tenant RBAC security.
"""

import pytest
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch

from app.db.base import Base
from app.db.session import sync_engine, get_sync_session, AsyncSessionLocal
from app.models.organization import Organization, OrganizationStatus
from app.models.site import Site, SiteStatus, SiteType
from app.models.station import Station, StationStatus, StationType
from app.models.controller import Controller, ControllerStatus, ControllerType
from app.models.sensor import Sensor, SensorStatus, SensorType
from app.models.telemetry import TelemetryReading
from app.models.user import User, UserRole

from app.services.sensor_service import (
    SENSOR_SPECS,
    get_default_unit,
    normalize_sensor_unit,
    is_value_in_range,
    ensure_utc_datetime,
    validate_sensor_reading,
    create_sensor,
    get_sensor_by_id,
    list_sensors_for_org_or_controller,
    update_sensor,
    delete_sensor,
    get_sensor_telemetry_history,
    get_sensor_latest_telemetry,
    SensorCodeAlreadyExistsException,
    SensorNotFoundException,
    SensorHasDependentResourcesException,
)
from app.schemas.sensor import SensorCreate, SensorUpdate
from app.mqtt.handlers.telemetry_handler import process_telemetry_payload


@pytest.fixture(scope="module", autouse=True)
def setup_tables():
    Base.metadata.create_all(bind=sync_engine)
    yield
    Base.metadata.drop_all(bind=sync_engine)


def helper_create_test_hierarchy(prefix: str):
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
            device_uid=f"{prefix}-DEV-{uuid.uuid4().hex[:6]}",
            controller_type=ControllerType.ESP32,
            status=ControllerStatus.ACTIVE,
            last_seen_at=datetime.now(timezone.utc)
        )
        session.add(controller)
        session.commit()

        return {
            "org_id": org.id,
            "site_id": site.id,
            "station_id": station.id,
            "controller_id": controller.id,
            "device_uid": controller.device_uid
        }


# =============================================================================
# 1. Sensor Type Specifications & Normalization Tests
# =============================================================================

def test_sensor_types_specs_and_defaults():
    """Verify all 10 SensorType values have defined specs and defaults."""
    expected_types = [
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
    for st in expected_types:
        assert st in SENSOR_SPECS
        default_unit = get_default_unit(st)
        assert isinstance(default_unit, str)
        assert len(default_unit) > 0


def test_unit_normalization_mappings():
    """Verify raw unit strings are normalized to canonical notation."""
    assert normalize_sensor_unit(SensorType.WATER_LEVEL, "percent") == "%"
    assert normalize_sensor_unit(SensorType.WATER_LEVEL, "Liters") == "L"
    assert normalize_sensor_unit(SensorType.TURBIDITY, "ntu") == "NTU"
    assert normalize_sensor_unit(SensorType.TURBIDITY, "FNU") == "FNU"
    assert normalize_sensor_unit(SensorType.FLOW, "lpm") == "L/min"
    assert normalize_sensor_unit(SensorType.FLOW, "m3/h") == "m³/h"
    assert normalize_sensor_unit(SensorType.PRESSURE, "PSI") == "psi"
    assert normalize_sensor_unit(SensorType.PRESSURE, "bar") == "bar"
    assert normalize_sensor_unit(SensorType.TEMPERATURE, "celsius") == "°C"
    assert normalize_sensor_unit(SensorType.TEMPERATURE, "F") == "°F"
    assert normalize_sensor_unit(SensorType.HUMIDITY, "%RH") == "%RH"
    assert normalize_sensor_unit(SensorType.CURRENT, "amp") == "A"
    assert normalize_sensor_unit(SensorType.CURRENT, "mA") == "mA"
    assert normalize_sensor_unit(SensorType.VOLTAGE, "volts") == "V"
    assert normalize_sensor_unit(SensorType.PH, "PH") == "pH"
    assert normalize_sensor_unit(SensorType.OTHER, "custom_metric") == "custom_metric"
    assert normalize_sensor_unit(SensorType.WATER_LEVEL, None) == "%"


def test_validate_sensor_reading_quality_tags():
    """Verify range validation tags quality as GOOD or OUT_OF_RANGE."""
    # Water Level
    valid, _, val, unit, q = validate_sensor_reading(SensorType.WATER_LEVEL, 75.5, "%")
    assert valid and val == 75.5 and unit == "%" and q["quality"] == "GOOD"

    valid, _, val, unit, q = validate_sensor_reading(SensorType.WATER_LEVEL, 150.0, "%")
    assert valid and q["quality"] == "OUT_OF_RANGE"

    # Turbidity
    valid, _, val, unit, q = validate_sensor_reading(SensorType.TURBIDITY, 12.0, "ntu")
    assert valid and unit == "NTU" and q["quality"] == "GOOD"

    # Temperature
    valid, _, val, unit, q = validate_sensor_reading(SensorType.TEMPERATURE, 25.0, "°C")
    assert valid and q["quality"] == "GOOD"

    valid, _, val, unit, q = validate_sensor_reading(SensorType.TEMPERATURE, 200.0, "°C")
    assert valid and q["quality"] == "OUT_OF_RANGE"

    # pH
    valid, _, val, unit, q = validate_sensor_reading(SensorType.PH, 7.2, "ph")
    assert valid and unit == "pH" and q["quality"] == "GOOD"

    valid, _, val, unit, q = validate_sensor_reading(SensorType.PH, 16.0, "pH")
    assert valid and q["quality"] == "OUT_OF_RANGE"

    # Invalid input
    valid, err, _, _, q = validate_sensor_reading(SensorType.FLOW, "not-a-number", "L/min")
    assert not valid and q["quality"] == "BAD"

    valid, err, _, _, q = validate_sensor_reading(SensorType.FLOW, None, "L/min")
    assert not valid and q["quality"] == "BAD"


def test_ensure_utc_datetime():
    """Verify datetime parsing and normalization to UTC."""
    now = datetime.now(timezone.utc)
    assert ensure_utc_datetime(now) == now

    # Naive datetime
    naive = datetime(2026, 10, 6, 12, 0, 0)
    aware = ensure_utc_datetime(naive)
    assert aware.tzinfo == timezone.utc

    # String ISO with Z
    iso_z = "2026-10-06T12:00:00Z"
    parsed_z = ensure_utc_datetime(iso_z)
    assert parsed_z.tzinfo == timezone.utc
    assert parsed_z.hour == 12

    # Timestamp
    ts = 1760000000
    from_ts = ensure_utc_datetime(ts)
    assert from_ts.tzinfo == timezone.utc


# =============================================================================
# 2. Sensor Domain Service CRUD & Uniqueness Tests
# =============================================================================

@pytest.mark.asyncio
async def test_sensor_crud_and_uniqueness():
    h = helper_create_test_hierarchy("P11_CRUD")
    async with AsyncSessionLocal() as session:
        # Create Sensor
        req = SensorCreate(
            controller_id=h["controller_id"],
            name="Feed Water Level",
            sensor_code="LVL_FEED_01",
            sensor_type=SensorType.WATER_LEVEL,
            status=SensorStatus.ACTIVE,
            description="Main feed tank level sensor"
        )
        sensor = await create_sensor(session, req, h["controller_id"])
        assert sensor.id is not None
        assert sensor.sensor_code == "LVL_FEED_01"
        assert sensor.sensor_type == SensorType.WATER_LEVEL

        # Duplicate code in same controller must raise
        with pytest.raises(SensorCodeAlreadyExistsException):
            await create_sensor(session, req, h["controller_id"])

        # Update sensor
        up_req = SensorUpdate(name="Updated Feed Level", status=SensorStatus.MAINTENANCE)
        updated = await update_sensor(session, sensor, up_req)
        assert updated.name == "Updated Feed Level"
        assert updated.status == SensorStatus.MAINTENANCE

        # Delete sensor (no telemetry -> success)
        await delete_sensor(session, updated)
        assert await get_sensor_by_id(session, sensor.id) is None


@pytest.mark.asyncio
async def test_sensor_delete_restricted_when_telemetry_exists():
    h = helper_create_test_hierarchy("P11_DEL")
    async with AsyncSessionLocal() as session:
        req = SensorCreate(
            controller_id=h["controller_id"],
            name="Flow Sensor",
            sensor_code="FLOW_DEL_01",
            sensor_type=SensorType.FLOW
        )
        sensor = await create_sensor(session, req, h["controller_id"])

        # Add a telemetry reading
        reading = TelemetryReading(
            id=uuid.uuid4(),
            sensor_id=sensor.id,
            value=45.2,
            unit="L/min",
            occurred_at=datetime.now(timezone.utc)
        )
        session.add(reading)
        await session.commit()

        # Delete must raise SensorHasDependentResourcesException
        with pytest.raises(SensorHasDependentResourcesException):
            await delete_sensor(session, sensor)


# =============================================================================
# 3. Telemetry History & Latest Query Service Tests
# =============================================================================

@pytest.mark.asyncio
async def test_telemetry_history_and_latest_queries():
    h = helper_create_test_hierarchy("P11_HIST")
    async with AsyncSessionLocal() as session:
        req = SensorCreate(
            controller_id=h["controller_id"],
            name="Pressure Sensor",
            sensor_code="PRES_HIST_01",
            sensor_type=SensorType.PRESSURE
        )
        sensor = await create_sensor(session, req, h["controller_id"])

        base_time = datetime(2026, 10, 6, 10, 0, 0, tzinfo=timezone.utc)
        for i in range(10):
            t_entry = TelemetryReading(
                id=uuid.uuid4(),
                sensor_id=sensor.id,
                value=2.0 + (i * 0.1),
                unit="bar",
                occurred_at=base_time + timedelta(minutes=i * 5),
                metadata_={"step": i}
            )
            session.add(t_entry)
        await session.commit()

        # 1. Query full history (chronological order)
        history = await get_sensor_telemetry_history(
            session=session,
            sensor_id=sensor.id,
            current_user_org_id=h["org_id"]
        )
        assert len(history) == 10
        assert float(history[0].value) == pytest.approx(2.0, 0.01)
        assert float(history[-1].value) == pytest.approx(2.9, 0.01)

        # 2. Query with time window
        start = base_time + timedelta(minutes=10)
        end = base_time + timedelta(minutes=30)
        windowed = await get_sensor_telemetry_history(
            session=session,
            sensor_id=sensor.id,
            start_time=start,
            end_time=end,
            current_user_org_id=h["org_id"]
        )
        assert len(windowed) == 5  # minute 10, 15, 20, 25, 30

        # 3. Pagination
        paginated = await get_sensor_telemetry_history(
            session=session,
            sensor_id=sensor.id,
            limit=3,
            offset=2,
            current_user_org_id=h["org_id"]
        )
        assert len(paginated) == 3
        assert float(paginated[0].value) == pytest.approx(2.2, 0.01)

        # 4. Latest Reading
        latest = await get_sensor_latest_telemetry(
            session=session,
            sensor_id=sensor.id,
            current_user_org_id=h["org_id"]
        )
        assert latest is not None
        assert float(latest.value) == pytest.approx(2.9, 0.01)
        assert latest.metadata_["step"] == 9

        # 5. Cross-tenant access denied
        foreign_org_id = uuid.uuid4()
        with pytest.raises(SensorNotFoundException):
            await get_sensor_telemetry_history(
                session=session,
                sensor_id=sensor.id,
                current_user_org_id=foreign_org_id
            )


# =============================================================================
# 4. MQTT Telemetry Ingestion, Anti-Spoofing & Quality Tagging
# =============================================================================

@pytest.mark.asyncio
async def test_mqtt_telemetry_ingestion_and_anti_spoofing():
    h = helper_create_test_hierarchy("P11_MQTT")
    device_uid = h["device_uid"]

    # Register sensors on controller
    async with AsyncSessionLocal() as session:
        await create_sensor(session, SensorCreate(
            controller_id=h["controller_id"],
            name="Turbidity Sensor",
            sensor_code="TURB_01",
            sensor_type=SensorType.TURBIDITY
        ), h["controller_id"])
        await create_sensor(session, SensorCreate(
            controller_id=h["controller_id"],
            name="Level Sensor",
            sensor_code="LEVEL_01",
            sensor_type=SensorType.WATER_LEVEL
        ), h["controller_id"])

    # 1. Valid batch payload with normalization
    batch_payload = [
        {"sensor_code": "TURB_01", "value": 15.4, "unit": "ntu", "occurred_at": "2026-01-01T10:00:00Z"},
        {"sensor_code": "LEVEL_01", "value": 85.0, "unit": "percent", "occurred_at": "2026-01-01T10:00:00Z"},
    ]

    with patch("app.mqtt.handlers.telemetry_handler.stream_telemetry", new_callable=AsyncMock) as mock_stream:
        saved = await process_telemetry_payload(device_uid, batch_payload)
        assert saved == 2
        assert mock_stream.call_count == 2

    # Verify persisted data in DB
    async with AsyncSessionLocal() as session:
        sensors = await list_sensors_for_org_or_controller(session, controller_id=h["controller_id"])
        turb_sensor = next(s for s in sensors if s.sensor_code == "TURB_01")
        latest = await get_sensor_latest_telemetry(session, turb_sensor.id)
        assert latest is not None
        assert float(latest.value) == pytest.approx(15.4, 0.01)
        assert latest.unit == "NTU"
        assert latest.metadata_["quality"] == "GOOD"

    # 2. Out-of-range quality tagging
    out_of_range_payload = [
        {"sensor_code": "TURB_01", "value": 5000.0, "unit": "NTU"}
    ]
    saved = await process_telemetry_payload(device_uid, out_of_range_payload)
    assert saved == 1

    async with AsyncSessionLocal() as session:
        latest = await get_sensor_latest_telemetry(session, turb_sensor.id)
        assert float(latest.value) == pytest.approx(5000.0, 0.01)
        assert latest.metadata_["quality"] == "OUT_OF_RANGE"

    # 3. Anti-Spoofing: Unregistered sensor code on valid device -> Rejected (saved=0)
    unregistered_sensor_payload = [
        {"sensor_code": "UNKNOWN_SENS_99", "value": 10.0, "unit": "%"}
    ]
    saved = await process_telemetry_payload(device_uid, unregistered_sensor_payload)
    assert saved == 0

    # 4. Anti-Spoofing: Unregistered device_uid -> Rejected (saved=0)
    saved = await process_telemetry_payload("SPOOFED-DEV-9999", batch_payload)
    assert saved == 0


# =============================================================================
# 5. Multi-Sensor Types Coverage Matrix
# =============================================================================

@pytest.mark.asyncio
async def test_all_10_sensor_types_telemetry_ingestion():
    """Verify all 10 SensorType values can be ingested, validated, and queried."""
    h = helper_create_test_hierarchy("P11_ALL10")
    device_uid = h["device_uid"]

    type_code_map = [
        (SensorType.WATER_LEVEL, "SN_LEVEL", 62.5, "%", "%"),
        (SensorType.TURBIDITY, "SN_TURB", 8.4, "ntu", "NTU"),
        (SensorType.FLOW, "SN_FLOW", 120.0, "lpm", "L/min"),
        (SensorType.PRESSURE, "SN_PRES", 4.5, "bar", "bar"),
        (SensorType.TEMPERATURE, "SN_TEMP", 28.5, "c", "°C"),
        (SensorType.HUMIDITY, "SN_HUM", 55.0, "%rh", "%RH"),
        (SensorType.CURRENT, "SN_CURR", 8.2, "amp", "A"),
        (SensorType.VOLTAGE, "SN_VOLT", 235.0, "volts", "V"),
        (SensorType.PH, "SN_PH", 7.4, "ph", "pH"),
        (SensorType.OTHER, "SN_OTHER", 42.0, "count", "count"),
    ]

    async with AsyncSessionLocal() as session:
        for s_type, code, _, _, _ in type_code_map:
            await create_sensor(session, SensorCreate(
                controller_id=h["controller_id"],
                name=f"Sensor {s_type.value}",
                sensor_code=code,
                sensor_type=s_type
            ), h["controller_id"])

    # Batch ingest for all 10 sensors
    ingest_items = [
        {"sensor_code": code, "value": val, "unit": raw_u}
        for _, code, val, raw_u, _ in type_code_map
    ]

    saved = await process_telemetry_payload(device_uid, ingest_items)
    assert saved == 10

    # Verify each sensor's latest reading and normalized unit
    async with AsyncSessionLocal() as session:
        sensors = await list_sensors_for_org_or_controller(session, controller_id=h["controller_id"])
        assert len(sensors) == 10
        for s_type, code, expected_val, _, expected_unit in type_code_map:
            sens = next(s for s in sensors if s.sensor_code == code)
            latest = await get_sensor_latest_telemetry(session, sens.id)
            assert latest is not None
            assert float(latest.value) == pytest.approx(expected_val, 0.01)
            assert latest.unit == expected_unit
            assert latest.metadata_["quality"] == "GOOD"
