"""
API endpoints for Station Schedules (Phase 16 - Wave A).
"""

import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.api.deps import get_current_user, require_roles
from app.models.user import User, UserRole
from app.schemas.schedule import ScheduleCreate, ScheduleUpdate, ScheduleResponse
from app.services.schedule_service import (
    list_schedules_for_station,
    get_schedule_by_id,
    create_schedule,
    update_schedule,
    delete_schedule,
)
from app.services.station_settings import verify_station_tenant_access
from app.services.site_auth import validate_site_access_policy

router = APIRouter(tags=["Schedules"])


@router.get("/stations/{station_id}/schedules", response_model=List[ScheduleResponse])
async def list_station_schedules_endpoint(
    station_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    List all schedules for a station.
    Enforces multi-tenant isolation and site policy.
    """
    station = await verify_station_tenant_access(session, station_id, current_user)
    if station is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Station not found",
        )

    validate_site_access_policy(station.site, current_user)
    schedules = await list_schedules_for_station(session, station_id)
    return schedules


@router.post("/stations/{station_id}/schedules", response_model=ScheduleResponse, status_code=status.HTTP_201_CREATED)
async def create_station_schedule_endpoint(
    station_id: uuid.UUID,
    req: ScheduleCreate,
    current_user: User = Depends(require_roles([UserRole.SUPER_ADMIN, UserRole.ORGANIZATION_ADMIN, UserRole.SITE_MANAGER])),
    session: AsyncSession = Depends(get_db),
):
    """
    Create a new schedule for a station.
    Restricted to SUPER_ADMIN, ORGANIZATION_ADMIN, SITE_MANAGER.
    """
    if req.station_id != station_id:
        req.station_id = station_id

    station = await verify_station_tenant_access(session, station_id, current_user)
    if station is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Station not found",
        )

    validate_site_access_policy(station.site, current_user)
    try:
        schedule = await create_schedule(session, req, creator_id=current_user.id)
        return schedule
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/stations/{station_id}/schedules/{schedule_id}", response_model=ScheduleResponse)
async def update_station_schedule_endpoint(
    station_id: uuid.UUID,
    schedule_id: uuid.UUID,
    req: ScheduleUpdate,
    current_user: User = Depends(require_roles([UserRole.SUPER_ADMIN, UserRole.ORGANIZATION_ADMIN, UserRole.SITE_MANAGER])),
    session: AsyncSession = Depends(get_db),
):
    """
    Update a schedule rule for a station.
    Restricted to SUPER_ADMIN, ORGANIZATION_ADMIN, SITE_MANAGER.
    """
    station = await verify_station_tenant_access(session, station_id, current_user)
    if station is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Station not found",
        )

    validate_site_access_policy(station.site, current_user)
    schedule = await get_schedule_by_id(session, schedule_id)
    if schedule is None or schedule.station_id != station_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schedule not found",
        )

    updated = await update_schedule(session, schedule, req)
    return updated


@router.delete("/stations/{station_id}/schedules/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_station_schedule_endpoint(
    station_id: uuid.UUID,
    schedule_id: uuid.UUID,
    current_user: User = Depends(require_roles([UserRole.SUPER_ADMIN, UserRole.ORGANIZATION_ADMIN, UserRole.SITE_MANAGER])),
    session: AsyncSession = Depends(get_db),
):
    """
    Delete a schedule rule for a station.
    Restricted to SUPER_ADMIN, ORGANIZATION_ADMIN, SITE_MANAGER.
    """
    station = await verify_station_tenant_access(session, station_id, current_user)
    if station is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Station not found",
        )

    validate_site_access_policy(station.site, current_user)
    schedule = await get_schedule_by_id(session, schedule_id)
    if schedule is None or schedule.station_id != station_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schedule not found",
        )

    await delete_schedule(session, schedule)
