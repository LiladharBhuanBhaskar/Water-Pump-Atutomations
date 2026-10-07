"""
HydraControl — Event History Service (Phase 18 - Wave A)
Provides query and filtering services for historical MotorEvent records with multi-tenant scoping.
"""

import uuid
from datetime import datetime
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.models.motor_event import MotorEvent, MotorEventType, MotorEventSource
from app.models.motor import Motor
from app.models.controller import Controller
from app.models.station import Station
from app.models.site import Site
from app.models.user import User, UserRole
from app.services.tenant import get_org_scoped_resource


async def verify_motor_access(
    session: AsyncSession,
    motor_id: uuid.UUID,
    user: User,
) -> Optional[Motor]:
    """Verify user has tenant access to the motor."""
    stmt = (
        select(Motor)
        .where(Motor.id == motor_id)
        .options(
            selectinload(Motor.controller).selectinload(Controller.station).selectinload(Station.site)
        )
    )
    res = await session.execute(stmt)
    motor = res.scalar_one_or_none()
    if motor is None:
        return None

    if user.role == UserRole.SUPER_ADMIN:
        return motor

    if (
        user.organization_id is not None
        and motor.controller
        and motor.controller.station
        and motor.controller.station.site
        and motor.controller.station.site.organization_id == user.organization_id
    ):
        return motor

    return None


async def get_motor_events(
    session: AsyncSession,
    motor_id: uuid.UUID,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    event_type: Optional[MotorEventType] = None,
    source: Optional[MotorEventSource] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[MotorEvent]:
    """Retrieve filtered, paginated events for a specific motor."""
    stmt = select(MotorEvent).where(MotorEvent.motor_id == motor_id)

    if start_time is not None:
        stmt = stmt.where(MotorEvent.occurred_at >= start_time)
    if end_time is not None:
        stmt = stmt.where(MotorEvent.occurred_at <= end_time)
    if event_type is not None:
        stmt = stmt.where(MotorEvent.event_type == event_type)
    if source is not None:
        stmt = stmt.where(MotorEvent.source == source)

    stmt = stmt.order_by(MotorEvent.occurred_at.desc(), MotorEvent.id.desc())
    stmt = stmt.limit(limit).offset(offset)

    res = await session.execute(stmt)
    return res.scalars().all()


async def get_station_events(
    session: AsyncSession,
    station_id: uuid.UUID,
    motor_id: Optional[uuid.UUID] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    event_type: Optional[MotorEventType] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[MotorEvent]:
    """Retrieve filtered, paginated events across all motors belonging to a station."""
    stmt = (
        select(MotorEvent)
        .join(Motor, MotorEvent.motor_id == Motor.id)
        .join(Controller, Motor.controller_id == Controller.id)
        .where(Controller.station_id == station_id)
    )

    if motor_id is not None:
        stmt = stmt.where(MotorEvent.motor_id == motor_id)
    if start_time is not None:
        stmt = stmt.where(MotorEvent.occurred_at >= start_time)
    if end_time is not None:
        stmt = stmt.where(MotorEvent.occurred_at <= end_time)
    if event_type is not None:
        stmt = stmt.where(MotorEvent.event_type == event_type)

    stmt = stmt.order_by(MotorEvent.occurred_at.desc(), MotorEvent.id.desc())
    stmt = stmt.limit(limit).offset(offset)

    res = await session.execute(stmt)
    return res.scalars().all()
