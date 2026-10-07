import uuid
from typing import Sequence, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, and_

from app.models.sensor import Sensor, SensorStatus, SensorType
from app.models.controller import Controller
from app.models.station import Station
from app.models.site import Site
from app.models.telemetry import TelemetryReading
from app.schemas.sensor import SensorCreate, SensorUpdate

# Re-export from sensor_service for backward compatibility
from app.services.sensor_service import (
    SensorCodeAlreadyExistsException,
    SensorNotFoundException,
    SensorHasDependentResourcesException,
    SensorValidationException,
    SensorTenantAccessDeniedException,
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
    get_sensor_latest_telemetry
)


async def create_sensor(
    session: AsyncSession,
    req: SensorCreate,
    target_controller_id: uuid.UUID
) -> Sensor:
    code = req.sensor_code.strip().upper()
    name = req.name.strip()

    # Check composite uniqueness on (controller_id, sensor_code)
    stmt = select(Sensor).where(
        and_(
            Sensor.controller_id == target_controller_id,
            Sensor.sensor_code == code
        )
    )
    res = await session.execute(stmt)
    if res.scalar_one_or_none() is not None:
        raise SensorCodeAlreadyExistsException(f"Sensor code '{code}' already exists in this controller.")

    sensor = Sensor(
        id=uuid.uuid4(),
        controller_id=target_controller_id,
        name=name,
        sensor_code=code,
        sensor_type=req.sensor_type or SensorType.OTHER,
        status=req.status or SensorStatus.ACTIVE,
        description=req.description.strip() if req.description else None
    )
    session.add(sensor)
    await session.commit()
    await session.refresh(sensor)
    return sensor


async def get_sensor_by_id(session: AsyncSession, sensor_id: uuid.UUID) -> Optional[Sensor]:
    stmt = select(Sensor).where(Sensor.id == sensor_id)
    res = await session.execute(stmt)
    return res.scalar_one_or_none()


async def list_sensors_for_org_or_controller(
    session: AsyncSession,
    organization_id: Optional[uuid.UUID] = None,
    controller_id: Optional[uuid.UUID] = None
) -> Sequence[Sensor]:
    stmt = (
        select(Sensor)
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
    # Check if dependent telemetry readings exist
    stmt = select(func.count(TelemetryReading.id)).where(TelemetryReading.sensor_id == sensor.id)
    res = await session.execute(stmt)
    count = res.scalar() or 0

    if count > 0:
        raise SensorHasDependentResourcesException("Cannot delete sensor with active telemetry readings.")

    await session.delete(sensor)
    await session.commit()
