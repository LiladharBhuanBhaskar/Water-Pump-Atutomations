"""
API endpoints for Motor and Station Event History (Phase 18 - Wave A).
"""

import uuid
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.motor_event import MotorEventType, MotorEventSource
from app.schemas.motor_event import MotorEventResponse
from app.services.event_history_service import (
    verify_motor_access,
    get_motor_events,
    get_station_events,
)
from app.services.station_settings import verify_station_tenant_access
from app.services.site_auth import validate_site_access_policy

router = APIRouter(tags=["Events"])


@router.get("/motors/{motor_id}/events", response_model=List[MotorEventResponse])
async def get_motor_events_endpoint(
    motor_id: uuid.UUID,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    event_type: Optional[MotorEventType] = None,
    source: Optional[MotorEventSource] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Retrieve paginated historical events for a specific motor.
    Enforces multi-tenant isolation and site access policy.
    """
    if start_time and end_time and start_time > end_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_time must be before end_time.",
        )

    motor = await verify_motor_access(session, motor_id, current_user)
    if motor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Motor not found",
        )

    if motor.controller and motor.controller.station and motor.controller.station.site:
        validate_site_access_policy(motor.controller.station.site, current_user)

    events = await get_motor_events(
        session=session,
        motor_id=motor_id,
        start_time=start_time,
        end_time=end_time,
        event_type=event_type,
        source=source,
        limit=limit,
        offset=offset,
    )
    return events


@router.get("/stations/{station_id}/events", response_model=List[MotorEventResponse])
async def get_station_events_endpoint(
    station_id: uuid.UUID,
    motor_id: Optional[uuid.UUID] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    event_type: Optional[MotorEventType] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Retrieve paginated historical events across all motors belonging to a station.
    Enforces multi-tenant isolation and site access policy.
    """
    if start_time and end_time and start_time > end_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_time must be before end_time.",
        )

    station = await verify_station_tenant_access(session, station_id, current_user)
    if station is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Station not found",
        )

    validate_site_access_policy(station.site, current_user)

    events = await get_station_events(
        session=session,
        station_id=station_id,
        motor_id=motor_id,
        start_time=start_time,
        end_time=end_time,
        event_type=event_type,
        limit=limit,
        offset=offset,
    )
    return events
