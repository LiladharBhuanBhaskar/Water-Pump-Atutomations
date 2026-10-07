"""
HydraControl — Generic Sensor Framework & Domain Service
Provides type-aware validation, unit normalization, range evaluation,
stale timestamp protection, and historical telemetry querying across
all authoritative SensorType categories.
"""

import uuid
import logging
from typing import Dict, Any, Optional, Tuple, Sequence, Set
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import func, and_, desc

from app.models.sensor import Sensor, SensorStatus, SensorType
from app.models.controller import Controller
from app.models.station import Station
from app.models.site import Site
from app.models.telemetry import TelemetryReading
from app.schemas.sensor import SensorCreate, SensorUpdate

logger = logging.getLogger("hydracontrol.services.sensor")


# =============================================================================
# Domain Exceptions
# =============================================================================

class SensorNotFoundException(Exception):
    """Raised when a requested sensor does not exist or is not visible to tenant."""
    pass


class SensorValidationException(Exception):
    """Raised when a sensor payload, value, or unit is invalid."""
    pass


class SensorTenantAccessDeniedException(Exception):
    """Raised when an operation violates organization tenant boundaries."""
    pass


class SensorCodeAlreadyExistsException(Exception):
    """Raised when a sensor_code already exists within the target controller."""
    pass


class SensorHasDependentResourcesException(Exception):
    """Raised when attempting to delete a sensor with dependent telemetry."""
    pass


# =============================================================================
# Sensor Type Specifications (Standard units, canonical forms, valid ranges)
# =============================================================================

SENSOR_SPECS: Dict[SensorType, Dict[str, Any]] = {
    SensorType.WATER_LEVEL: {
        "default_unit": "%",
        "canonical_units": {
            "%": "%", "percent": "%", "pct": "%",
            "m": "m", "meter": "m", "meters": "m",
            "cm": "cm", "centimeter": "cm",
            "mm": "mm", "millimeter": "mm",
            "l": "L", "liters": "L", "liter": "L", "litres": "L",
            "gal": "gal", "gallons": "gal"
        },
        "range_by_unit": {
            "%": (0.0, 100.0),
            "m": (0.0, 100.0),
            "cm": (0.0, 10000.0),
            "mm": (0.0, 100000.0),
            "L": (0.0, 1000000.0),
            "gal": (0.0, 500000.0),
        }
    },
    SensorType.TURBIDITY: {
        "default_unit": "NTU",
        "canonical_units": {
            "ntu": "NTU", "fnu": "FNU", "mg/l": "mg/L", "ppm": "ppm"
        },
        "range_by_unit": {
            "NTU": (0.0, 4000.0),
            "FNU": (0.0, 4000.0),
            "mg/L": (0.0, 10000.0),
            "ppm": (0.0, 10000.0),
        }
    },
    SensorType.FLOW: {
        "default_unit": "L/min",
        "canonical_units": {
            "l/min": "L/min", "lpm": "L/min", "liters/min": "L/min",
            "m3/h": "m³/h", "m³/h": "m³/h", "m3/hr": "m³/h",
            "gpm": "GPM", "gallons/min": "GPM",
            "l/s": "L/s", "lps": "L/s"
        },
        "range_by_unit": {
            "L/min": (0.0, 20000.0),
            "m³/h": (0.0, 1200.0),
            "GPM": (0.0, 5000.0),
            "L/s": (0.0, 500.0),
        }
    },
    SensorType.PRESSURE: {
        "default_unit": "bar",
        "canonical_units": {
            "bar": "bar", "psi": "psi", "kpa": "kPa", "mpa": "MPa",
            "kg/cm2": "kg/cm²", "kg/cm²": "kg/cm²"
        },
        "range_by_unit": {
            "bar": (-1.0, 100.0),
            "psi": (-15.0, 1450.0),
            "kPa": (-100.0, 10000.0),
            "MPa": (-0.1, 10.0),
            "kg/cm²": (-1.0, 100.0),
        }
    },
    SensorType.TEMPERATURE: {
        "default_unit": "°C",
        "canonical_units": {
            "°c": "°C", "c": "°C", "degc": "°C", "celsius": "°C",
            "°f": "°F", "f": "°F", "degf": "°F", "fahrenheit": "°F",
            "k": "K", "kelvin": "K"
        },
        "range_by_unit": {
            "°C": (-50.0, 150.0),
            "°F": (-58.0, 302.0),
            "K": (223.15, 423.15),
        }
    },
    SensorType.HUMIDITY: {
        "default_unit": "%",
        "canonical_units": {
            "%": "%", "%rh": "%RH", "rh": "%RH", "percent": "%"
        },
        "range_by_unit": {
            "%": (0.0, 100.0),
            "%RH": (0.0, 100.0),
        }
    },
    SensorType.CURRENT: {
        "default_unit": "A",
        "canonical_units": {
            "a": "A", "amp": "A", "amps": "A", "amperes": "A",
            "ma": "mA", "milliamp": "mA", "ka": "kA"
        },
        "range_by_unit": {
            "A": (0.0, 1000.0),
            "mA": (0.0, 1000000.0),
            "kA": (0.0, 1.0),
        }
    },
    SensorType.VOLTAGE: {
        "default_unit": "V",
        "canonical_units": {
            "v": "V", "volt": "V", "volts": "V",
            "mv": "mV", "millivolt": "mV", "kv": "kV"
        },
        "range_by_unit": {
            "V": (0.0, 1000.0),
            "mV": (0.0, 1000000.0),
            "kV": (0.0, 1.0),
        }
    },
    SensorType.PH: {
        "default_unit": "pH",
        "canonical_units": {
            "ph": "pH"
        },
        "range_by_unit": {
            "pH": (0.0, 14.0),
        }
    },
    SensorType.OTHER: {
        "default_unit": "raw",
        "canonical_units": {},
        "range_by_unit": {}
    }
}


# =============================================================================
# Normalization & Validation Functions
# =============================================================================

def get_default_unit(sensor_type: SensorType) -> str:
    """Returns standard default unit for a given SensorType."""
    spec = SENSOR_SPECS.get(sensor_type, SENSOR_SPECS[SensorType.OTHER])
    return spec.get("default_unit", "raw")


def normalize_sensor_unit(sensor_type: SensorType, raw_unit: Optional[str]) -> str:
    """
    Normalizes raw user/hardware unit string into canonical notation.
    If unit is unspecified or unmapped, returns default unit or stripped original.
    """
    if not raw_unit or not str(raw_unit).strip():
        return get_default_unit(sensor_type)

    cleaned = str(raw_unit).strip()
    spec = SENSOR_SPECS.get(sensor_type, SENSOR_SPECS[SensorType.OTHER])
    canonical_map = spec.get("canonical_units", {})
    return canonical_map.get(cleaned.lower(), cleaned)


def is_value_in_range(sensor_type: SensorType, value: float, unit: str) -> bool:
    """
    Checks if a numeric value falls within the standard physical boundary for the sensor type and unit.
    Returns True for OTHER sensor type or unbounded units.
    """
    spec = SENSOR_SPECS.get(sensor_type, SENSOR_SPECS[SensorType.OTHER])
    range_map = spec.get("range_by_unit", {})
    if unit not in range_map:
        return True

    min_val, max_val = range_map[unit]
    return min_val <= value <= max_val


def ensure_utc_datetime(dt_input: Any) -> datetime:
    """
    Normalizes any datetime, timestamp, or string into timezone-aware UTC datetime.
    """
    if dt_input is None:
        return datetime.now(timezone.utc)

    if isinstance(dt_input, (int, float)):
        return datetime.fromtimestamp(dt_input, tz=timezone.utc)

    if isinstance(dt_input, str):
        try:
            cleaned = dt_input.replace("Z", "+00:00")
            parsed = datetime.fromisoformat(cleaned)
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except Exception:
            return datetime.now(timezone.utc)

    if isinstance(dt_input, datetime):
        if dt_input.tzinfo is None:
            return dt_input.replace(tzinfo=timezone.utc)
        return dt_input.astimezone(timezone.utc)

    return datetime.now(timezone.utc)


def validate_sensor_reading(
    sensor_type: SensorType,
    raw_value: Any,
    raw_unit: Optional[str] = None
) -> Tuple[bool, Optional[str], float, str, Dict[str, Any]]:
    """
    Validates numeric type, normalizes unit, checks physical range,
    and returns (is_valid, error_reason, val_float, normalized_unit, quality_metadata).
    """
    quality: Dict[str, Any] = {"quality": "GOOD"}

    if raw_value is None:
        return False, "Missing telemetry value", 0.0, get_default_unit(sensor_type), {"quality": "BAD", "error": "MISSING_VALUE"}

    try:
        val_float = float(raw_value)
    except (ValueError, TypeError):
        return False, f"Invalid numeric value '{raw_value}'", 0.0, get_default_unit(sensor_type), {"quality": "BAD", "error": "INVALID_NUMERIC"}

    normalized_unit = normalize_sensor_unit(sensor_type, raw_unit)

    # Check physical validation bounds
    if not is_value_in_range(sensor_type, val_float, normalized_unit):
        quality = {"quality": "OUT_OF_RANGE", "warning": f"Value {val_float} outside typical range for {sensor_type.value} ({normalized_unit})"}

    return True, None, val_float, normalized_unit, quality


# =============================================================================
# Database CRUD & Query Services
# =============================================================================

async def create_sensor(
    session: AsyncSession,
    req: SensorCreate,
    target_controller_id: uuid.UUID
) -> Sensor:
    """Creates a new Sensor under a Controller with uniqueness checks."""
    code = req.sensor_code.strip().upper()
    name = req.name.strip()

    stmt = select(Sensor).where(
        and_(
            Sensor.controller_id == target_controller_id,
            Sensor.sensor_code == code
        )
    )
    res = await session.execute(stmt)
    if res.scalar_one_or_none() is not None:
        raise SensorCodeAlreadyExistsException(f"Sensor code '{code}' already exists in this controller.")

    s_type = req.sensor_type or SensorType.OTHER
    sensor = Sensor(
        id=uuid.uuid4(),
        controller_id=target_controller_id,
        name=name,
        sensor_code=code,
        sensor_type=s_type,
        status=req.status or SensorStatus.ACTIVE,
        description=req.description.strip() if req.description else None
    )
    session.add(sensor)
    await session.commit()
    await session.refresh(sensor)
    return sensor


async def get_sensor_by_id(
    session: AsyncSession,
    sensor_id: uuid.UUID,
    current_user_org_id: Optional[uuid.UUID] = None,
    is_super_admin: bool = False
) -> Optional[Sensor]:
    """Retrieves a sensor by ID with optional tenant boundary validation."""
    stmt = (
        select(Sensor)
        .options(
            selectinload(Sensor.controller).selectinload(Controller.station).selectinload(Station.site)
        )
        .where(Sensor.id == sensor_id)
    )
    res = await session.execute(stmt)
    sensor = res.scalar_one_or_none()
    if sensor is None:
        return None

    if not is_super_admin and current_user_org_id is not None:
        if sensor.controller and sensor.controller.station and sensor.controller.station.site:
            if sensor.controller.station.site.organization_id != current_user_org_id:
                return None

    return sensor


async def list_sensors_for_org_or_controller(
    session: AsyncSession,
    organization_id: Optional[uuid.UUID] = None,
    controller_id: Optional[uuid.UUID] = None
) -> Sequence[Sensor]:
    """Lists sensors filtered by tenant organization or controller."""
    stmt = (
        select(Sensor)
        .options(selectinload(Sensor.controller))
        .join(Controller, Sensor.controller_id == Controller.id)
        .join(Station, Controller.station_id == Station.id)
        .join(Site, Station.site_id == Site.id)
    )

    if organization_id is not None:
        stmt = stmt.where(Site.organization_id == organization_id)
    if controller_id is not None:
        stmt = stmt.where(Sensor.controller_id == controller_id)

    stmt = stmt.order_by(Sensor.created_at.desc())
    res = await session.execute(stmt)
    return res.scalars().all()


async def update_sensor(
    session: AsyncSession,
    sensor: Sensor,
    req: SensorUpdate
) -> Sensor:
    """Updates an existing Sensor."""
    if req.sensor_code is not None:
        new_code = req.sensor_code.strip().upper()
        if new_code != sensor.sensor_code:
            stmt = select(Sensor).where(
                and_(
                    Sensor.controller_id == sensor.controller_id,
                    Sensor.sensor_code == new_code
                )
            )
            res = await session.execute(stmt)
            if res.scalar_one_or_none() is not None:
                raise SensorCodeAlreadyExistsException(f"Sensor code '{new_code}' already exists in this controller.")
            sensor.sensor_code = new_code

    if req.name is not None:
        sensor.name = req.name.strip()

    if req.sensor_type is not None:
        sensor.sensor_type = req.sensor_type

    if req.status is not None:
        sensor.status = req.status

    if req.description is not None:
        sensor.description = req.description.strip() if req.description else None

    session.add(sensor)
    await session.commit()
    await session.refresh(sensor)
    return sensor


async def delete_sensor(session: AsyncSession, sensor: Sensor) -> None:
    """Deletes a Sensor if no dependent telemetry readings exist."""
    stmt = select(func.count(TelemetryReading.id)).where(TelemetryReading.sensor_id == sensor.id)
    res = await session.execute(stmt)
    count = res.scalar() or 0

    if count > 0:
        raise SensorHasDependentResourcesException("Cannot delete sensor with active telemetry readings.")

    await session.delete(sensor)
    await session.commit()


# =============================================================================
# Historical & Latest Telemetry Queries
# =============================================================================

async def get_sensor_telemetry_history(
    session: AsyncSession,
    sensor_id: uuid.UUID,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    limit: int = 100,
    offset: int = 0,
    current_user_org_id: Optional[uuid.UUID] = None,
    is_super_admin: bool = False
) -> Sequence[TelemetryReading]:
    """
    Retrieves chronological historical telemetry readings for a specific sensor,
    scoped by tenant boundaries and optional UTC time ranges.
    """
    # 1. Tenant & Existence Check
    sensor = await get_sensor_by_id(session, sensor_id, current_user_org_id, is_super_admin)
    if sensor is None:
        raise SensorNotFoundException(f"Sensor '{sensor_id}' not found.")

    # 2. Build Query
    stmt = select(TelemetryReading).where(TelemetryReading.sensor_id == sensor_id)

    if start_time is not None:
        utc_start = ensure_utc_datetime(start_time)
        stmt = stmt.where(TelemetryReading.occurred_at >= utc_start)

    if end_time is not None:
        utc_end = ensure_utc_datetime(end_time)
        stmt = stmt.where(TelemetryReading.occurred_at <= utc_end)

    # Order by occurred_at ascending (chronological time series)
    stmt = stmt.order_by(TelemetryReading.occurred_at.asc())

    # Pagination bounds
    safe_limit = max(1, min(limit, 1000))
    safe_offset = max(0, offset)
    stmt = stmt.limit(safe_limit).offset(safe_offset)

    res = await session.execute(stmt)
    return res.scalars().all()


async def get_sensor_latest_telemetry(
    session: AsyncSession,
    sensor_id: uuid.UUID,
    current_user_org_id: Optional[uuid.UUID] = None,
    is_super_admin: bool = False
) -> Optional[TelemetryReading]:
    """
    Retrieves the most recent telemetry reading for a sensor.
    """
    sensor = await get_sensor_by_id(session, sensor_id, current_user_org_id, is_super_admin)
    if sensor is None:
        raise SensorNotFoundException(f"Sensor '{sensor_id}' not found.")

    stmt = (
        select(TelemetryReading)
        .where(TelemetryReading.sensor_id == sensor_id)
        .order_by(desc(TelemetryReading.occurred_at))
        .limit(1)
    )
    res = await session.execute(stmt)
    return res.scalar_one_or_none()
