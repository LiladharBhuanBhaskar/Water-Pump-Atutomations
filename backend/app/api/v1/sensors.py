import uuid
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

logger = logging.getLogger(__name__)

from app.db.session import get_db
from app.api.deps import get_current_user, require_roles
from app.models.user import User, UserRole
from app.models.controller import Controller
from app.models.station import Station
from app.models.site import Site
from app.models.sensor import Sensor
from app.models.telemetry import TelemetryReading
from app.schemas.sensor import SensorCreate, SensorUpdate, SensorResponse
from app.services.sensor import (
    create_sensor,
    get_sensor_by_id,
    list_sensors_for_org_or_controller,
    update_sensor,
    delete_sensor,
    SensorCodeAlreadyExistsException,
    SensorHasDependentResourcesException
)
from app.services.site_auth import validate_site_access_policy
from app.services.tenant import get_org_scoped_resource

router = APIRouter(tags=["Sensors"])

@router.post("", response_model=SensorResponse, status_code=status.HTTP_201_CREATED)
async def create_sensor_endpoint(
    req: SensorCreate,
    current_user: User = Depends(require_roles([UserRole.SUPER_ADMIN, UserRole.ORGANIZATION_ADMIN, UserRole.SITE_MANAGER])),
    session: AsyncSession = Depends(get_db)
):
    """
    Create a new sensor under a controller.
    Restricted to SUPER_ADMIN, ORGANIZATION_ADMIN, SITE_MANAGER.
    Non-SUPER_ADMIN users can only create sensors under controllers belonging to their authenticated organization.
    """
    if current_user.role == UserRole.SUPER_ADMIN:
        controller = await get_controller_by_id_internal(session, req.controller_id)
    else:
        if current_user.organization_id is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Controller not found")
        controller = await get_org_scoped_resource(session, Controller, req.controller_id, current_user.organization_id)

    if controller is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Controller not found"
        )

    validate_site_access_policy(controller.station.site, current_user)

    try:
        sensor = await create_sensor(session, req, req.controller_id)
        return sensor
    except SensorCodeAlreadyExistsException as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )


async def get_controller_by_id_internal(session: AsyncSession, controller_id: uuid.UUID) -> Optional[Controller]:
    stmt = select(Controller).where(Controller.id == controller_id)
    res = await session.execute(stmt)
    return res.scalar_one_or_none()


@router.get("", response_model=List[SensorResponse])
async def list_sensors_endpoint(
    controller_id: Optional[uuid.UUID] = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    List sensors.
    SUPER_ADMIN can list all sensors or filter by controller_id.
    Non-SUPER_ADMIN users only receive sensors belonging to their authenticated organization.
    """
    if current_user.role == UserRole.SUPER_ADMIN:
        return await list_sensors_for_org_or_controller(session, organization_id=None, controller_id=controller_id)

    if current_user.organization_id is None:
        return []

    if controller_id is not None:
        controller = await get_org_scoped_resource(session, Controller, controller_id, current_user.organization_id)
        if controller is None:
            return []

    return await list_sensors_for_org_or_controller(session, organization_id=current_user.organization_id, controller_id=controller_id)


@router.get("/{sensor_id}", response_model=SensorResponse)
async def get_sensor_endpoint(
    sensor_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Retrieve a sensor by ID.
    Enforces Organization Tenant Isolation and Parent Site Operational Policy.
    """
    if current_user.role == UserRole.SUPER_ADMIN:
        sensor = await get_sensor_by_id(session, sensor_id)
    else:
        if current_user.organization_id is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sensor not found")
        sensor = await get_org_scoped_resource(session, Sensor, sensor_id, current_user.organization_id)

    if sensor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sensor not found"
        )

    validate_site_access_policy(sensor.controller.station.site, current_user)
    return sensor


@router.put("/{sensor_id}", response_model=SensorResponse)
@router.patch("/{sensor_id}", response_model=SensorResponse)
async def update_sensor_endpoint(
    sensor_id: uuid.UUID,
    req: SensorUpdate,
    current_user: User = Depends(require_roles([UserRole.SUPER_ADMIN, UserRole.ORGANIZATION_ADMIN, UserRole.SITE_MANAGER])),
    session: AsyncSession = Depends(get_db)
):
    """
    Update a sensor.
    Restricted to SUPER_ADMIN, ORGANIZATION_ADMIN, SITE_MANAGER.
    """
    if current_user.role == UserRole.SUPER_ADMIN:
        sensor = await get_sensor_by_id(session, sensor_id)
    else:
        if current_user.organization_id is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sensor not found")
        sensor = await get_org_scoped_resource(session, Sensor, sensor_id, current_user.organization_id)

    if sensor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sensor not found"
        )

    validate_site_access_policy(sensor.controller.station.site, current_user)

    try:
        updated_sensor = await update_sensor(session, sensor, req)
        return updated_sensor
    except SensorCodeAlreadyExistsException as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )


@router.delete("/{sensor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sensor_endpoint(
    sensor_id: uuid.UUID,
    current_user: User = Depends(require_roles([UserRole.SUPER_ADMIN, UserRole.ORGANIZATION_ADMIN])),
    session: AsyncSession = Depends(get_db)
):
    """
    Delete a sensor.
    Restricted to SUPER_ADMIN or ORGANIZATION_ADMIN.
    Fails if dependent telemetry readings exist (HTTP 400).
    """
    if current_user.role == UserRole.SUPER_ADMIN:
        sensor = await get_sensor_by_id(session, sensor_id)
    else:
        if current_user.organization_id is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sensor not found")
        sensor = await get_org_scoped_resource(session, Sensor, sensor_id, current_user.organization_id)

    if sensor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sensor not found"
        )

    try:
        await delete_sensor(session, sensor)
    except SensorHasDependentResourcesException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# =============================================================================
# Telemetry Endpoints (Phase 11 Generic Sensor Framework)
# =============================================================================

from datetime import datetime, timezone
from app.schemas.telemetry import TelemetryReadingResponse, TelemetryIngestItem, TelemetryBatchIngestRequest
from app.services.sensor_service import (
    get_sensor_telemetry_history,
    get_sensor_latest_telemetry,
    validate_sensor_reading,
    ensure_utc_datetime
)
from app.websocket.streamer import stream_telemetry


@router.get("/{sensor_id}/telemetry", response_model=List[TelemetryReadingResponse])
async def get_sensor_telemetry_history_endpoint(
    sensor_id: uuid.UUID,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    limit: int = 100,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Retrieve chronological historical telemetry readings for a sensor.
    Enforces multi-tenant isolation and site authorization.
    """
    is_super_admin = (current_user.role == UserRole.SUPER_ADMIN)
    org_id = current_user.organization_id

    try:
        readings = await get_sensor_telemetry_history(
            session=session,
            sensor_id=sensor_id,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
            offset=offset,
            current_user_org_id=org_id,
            is_super_admin=is_super_admin
        )
        return readings
    except SensorNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sensor '{sensor_id}' not found."
        )


@router.get("/{sensor_id}/latest", response_model=Optional[TelemetryReadingResponse])
async def get_sensor_latest_telemetry_endpoint(
    sensor_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Retrieve the most recent telemetry reading for a sensor.
    """
    is_super_admin = (current_user.role == UserRole.SUPER_ADMIN)
    org_id = current_user.organization_id

    try:
        latest = await get_sensor_latest_telemetry(
            session=session,
            sensor_id=sensor_id,
            current_user_org_id=org_id,
            is_super_admin=is_super_admin
        )
        if latest is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No telemetry readings found for sensor '{sensor_id}'."
            )
        return latest
    except SensorNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sensor '{sensor_id}' not found."
        )


@router.post("/{sensor_id}/telemetry", response_model=TelemetryReadingResponse, status_code=status.HTTP_201_CREATED)
async def ingest_sensor_telemetry_endpoint(
    sensor_id: uuid.UUID,
    req: TelemetryIngestItem,
    current_user: User = Depends(require_roles([UserRole.SUPER_ADMIN, UserRole.ORGANIZATION_ADMIN, UserRole.SITE_MANAGER, UserRole.STATION_OPERATOR, UserRole.TECHNICIAN])),
    session: AsyncSession = Depends(get_db)
):
    """
    Direct REST API ingestion endpoint for sensor telemetry (gateways/testing).
    Validates tenant ownership, normalizes units, records reading, and broadcasts over WebSockets.
    """
    stmt = (
        select(Sensor, Controller, Station, Site)
        .join(Controller, Sensor.controller_id == Controller.id)
        .join(Station, Controller.station_id == Station.id)
        .join(Site, Station.site_id == Site.id)
        .where(Sensor.id == sensor_id)
    )
    if current_user.role != UserRole.SUPER_ADMIN:
        if current_user.organization_id is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sensor not found")
        stmt = stmt.where(Site.organization_id == current_user.organization_id)

    res = await session.execute(stmt)
    row = res.first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sensor '{sensor_id}' not found."
        )
    sensor, ctrl, station, site = row
    validate_site_access_policy(site, current_user)

    is_valid, error_reason, val_float, normalized_unit, quality_meta = validate_sensor_reading(
        sensor_type=sensor.sensor_type,
        raw_value=req.value,
        raw_unit=req.unit
    )

    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid telemetry value: {error_reason}"
        )

    now = datetime.now(timezone.utc)
    occurred_at = ensure_utc_datetime(req.occurred_at) if req.occurred_at is not None else now

    meta = dict(req.metadata) if req.metadata else {}
    meta.update(quality_meta)

    reading = TelemetryReading(
        id=uuid.uuid4(),
        sensor_id=sensor.id,
        value=val_float,
        unit=normalized_unit,
        occurred_at=occurred_at,
        metadata_=meta
    )
    session.add(reading)
    await session.commit()
    await session.refresh(reading)

    # Broadcast via WebSocket
    try:
        await stream_telemetry(
            device_uid=ctrl.device_uid if ctrl else "MANUAL",
            sensor_id=sensor.id,
            sensor_code=sensor.sensor_code,
            value=val_float,
            unit=normalized_unit,
            occurred_at=occurred_at,
            organization_id=site.organization_id if site else None,
            site_id=site.id if site else None,
            station_id=station.id if station else None,
            metadata=meta
        )
    except Exception as e:
        logger.error(f"Error streaming direct telemetry for '{sensor.sensor_code}': {e}")

    return reading
