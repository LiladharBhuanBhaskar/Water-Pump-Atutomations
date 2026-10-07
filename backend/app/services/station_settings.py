"""Service layer for StationSettings management (Phase 12 - Wave 2A)."""

import uuid
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_

from app.models.settings import StationSettings
from app.models.station import Station
from app.models.site import Site
from app.models.user import User, UserRole
from app.schemas.settings import StationSettingsUpdate


class StationSettingsNotFoundException(Exception):
    pass


class StationAccessForbiddenException(Exception):
    pass


async def get_or_create_station_settings(
    session: AsyncSession,
    station_id: uuid.UUID,
    timezone: str = "Asia/Kolkata",
) -> StationSettings:
    """Gets existing StationSettings or creates default record if not yet initialized."""
    stmt = select(StationSettings).where(StationSettings.station_id == station_id)
    res = await session.execute(stmt)
    settings = res.scalar_one_or_none()

    if settings is None:
        settings = StationSettings(
            id=uuid.uuid4(),
            station_id=station_id,
            timezone=timezone,
            auto_stop_on_tank_full=False,
            offline_alert_enabled=True,
            offline_timeout_seconds=300,
        )
        session.add(settings)
        await session.commit()
        await session.refresh(settings)

    return settings


async def update_station_settings(
    session: AsyncSession,
    station_id: uuid.UUID,
    req: StationSettingsUpdate,
) -> StationSettings:
    """Updates station settings."""
    settings = await get_or_create_station_settings(session, station_id)

    if req.timezone is not None:
        settings.timezone = req.timezone
    if req.auto_stop_on_tank_full is not None:
        settings.auto_stop_on_tank_full = req.auto_stop_on_tank_full
    if req.water_level_threshold is not None:
        settings.water_level_threshold = req.water_level_threshold
    if req.turbidity_threshold is not None:
        settings.turbidity_threshold = req.turbidity_threshold
    if req.default_timer_seconds is not None:
        settings.default_timer_seconds = req.default_timer_seconds
    if req.offline_alert_enabled is not None:
        settings.offline_alert_enabled = req.offline_alert_enabled
    if req.offline_timeout_seconds is not None:
        settings.offline_timeout_seconds = req.offline_timeout_seconds

    await session.commit()
    await session.refresh(settings)
    return settings


async def verify_station_tenant_access(
    session: AsyncSession,
    station_id: uuid.UUID,
    current_user: User,
) -> Optional[Station]:
    """Verifies that the user has tenant access to the station."""
    stmt = (
        select(Station)
        .join(Site, Station.site_id == Site.id)
        .where(Station.id == station_id)
    )
    if current_user.role != UserRole.SUPER_ADMIN:
        if current_user.organization_id is None:
            return None
        stmt = stmt.where(Site.organization_id == current_user.organization_id)

    res = await session.execute(stmt)
    return res.scalar_one_or_none()
