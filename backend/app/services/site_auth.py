"""
HydraControl — Site-Level Authorization & Query Scoping Services
Provides secure site-level authorization and single-query hierarchical scoping within tenant boundaries.
"""
import uuid
from typing import Type, TypeVar, Optional, Sequence
from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi import HTTPException, status

from app.models.organization import Organization
from app.models.site import Site, SiteStatus
from app.models.station import Station
from app.models.settings import StationSettings
from app.models.controller import Controller
from app.models.motor import Motor
from app.models.sensor import Sensor
from app.models.telemetry import TelemetryReading
from app.models.motor_command import MotorCommand
from app.models.motor_event import MotorEvent
from app.models.automation_rule import AutomationRule
from app.models.audit_log import AuditLog
from app.models.user import User, UserRole
from app.services.tenant import get_org_scoped_resource

T = TypeVar("T")

# Roles permitted to access sites in MAINTENANCE mode
MAINTENANCE_ALLOWED_ROLES = {
    UserRole.SUPER_ADMIN,
    UserRole.ORGANIZATION_ADMIN,
    UserRole.SITE_MANAGER,
    UserRole.TECHNICIAN,
    UserRole.OWNER,
}


def validate_site_access_policy(site: Site, user: User) -> None:
    """
    Validates site operational status and user role permissions according to site authorization policy.
    Raises HTTPException 403 if access is restricted.
    """
    if site.status == SiteStatus.INACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Site is inactive"
        )
        
    if site.status == SiteStatus.SUSPENDED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Site is suspended"
        )
        
    if site.status == SiteStatus.MAINTENANCE:
        if user.role not in MAINTENANCE_ALLOWED_ROLES:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Site is under maintenance"
            )


def build_site_scoped_query(
    model: Type[T],
    site_id: uuid.UUID,
    organization_id: uuid.UUID
) -> Select:
    """
    Builds a secure SQLAlchemy SELECT statement that filters records by both site_id and organization_id
    using direct foreign keys or explicit relational join paths through the domain hierarchy.
    """
    if model is Site:
        return (
            select(Site)
            .where(Site.id == site_id, Site.organization_id == organization_id)
        )
        
    if model is Station:
        return (
            select(Station)
            .join(Site, Station.site_id == Site.id)
            .where(Station.site_id == site_id, Site.organization_id == organization_id)
        )
        
    if model is StationSettings:
        return (
            select(StationSettings)
            .join(Station, StationSettings.station_id == Station.id)
            .join(Site, Station.site_id == Site.id)
            .where(Station.site_id == site_id, Site.organization_id == organization_id)
        )
        
    if model is AutomationRule:
        return (
            select(AutomationRule)
            .join(Station, AutomationRule.station_id == Station.id)
            .join(Site, Station.site_id == Site.id)
            .where(Station.site_id == site_id, Site.organization_id == organization_id)
        )
        
    if model is Controller:
        return (
            select(Controller)
            .join(Station, Controller.station_id == Station.id)
            .join(Site, Station.site_id == Site.id)
            .where(Station.site_id == site_id, Site.organization_id == organization_id)
        )
        
    if model is Motor:
        return (
            select(Motor)
            .join(Controller, Motor.controller_id == Controller.id)
            .join(Station, Controller.station_id == Station.id)
            .join(Site, Station.site_id == Site.id)
            .where(Station.site_id == site_id, Site.organization_id == organization_id)
        )
        
    if model is Sensor:
        return (
            select(Sensor)
            .join(Controller, Sensor.controller_id == Controller.id)
            .join(Station, Controller.station_id == Station.id)
            .join(Site, Station.site_id == Site.id)
            .where(Station.site_id == site_id, Site.organization_id == organization_id)
        )
        
    if model is TelemetryReading:
        return (
            select(TelemetryReading)
            .join(Sensor, TelemetryReading.sensor_id == Sensor.id)
            .join(Controller, Sensor.controller_id == Controller.id)
            .join(Station, Controller.station_id == Station.id)
            .join(Site, Station.site_id == Site.id)
            .where(Station.site_id == site_id, Site.organization_id == organization_id)
        )
        
    if model is MotorCommand:
        return (
            select(MotorCommand)
            .join(Motor, MotorCommand.motor_id == Motor.id)
            .join(Controller, Motor.controller_id == Controller.id)
            .join(Station, Controller.station_id == Station.id)
            .join(Site, Station.site_id == Site.id)
            .where(Station.site_id == site_id, Site.organization_id == organization_id)
        )
        
    if model is MotorEvent:
        return (
            select(MotorEvent)
            .join(Motor, MotorEvent.motor_id == Motor.id)
            .join(Controller, Motor.controller_id == Controller.id)
            .join(Station, Controller.station_id == Station.id)
            .join(Site, Station.site_id == Site.id)
            .where(Station.site_id == site_id, Site.organization_id == organization_id)
        )
        
    if model is AuditLog:
        return (
            select(AuditLog)
            .where(AuditLog.site_id == site_id, AuditLog.organization_id == organization_id)
        )

    raise ValueError(f"Model {model.__name__} does not have a mapped site ownership chain.")


async def get_site_scoped_resource(
    session: AsyncSession,
    model: Type[T],
    resource_id: uuid.UUID,
    site_id: uuid.UUID,
    organization_id: uuid.UUID
) -> Optional[T]:
    """
    Safely retrieves a single resource by its primary key ID ensuring it belongs to the specified site
    and organization. Performs ID matching, site authorization, and tenant ownership verification in a
    single atomic database query.
    Returns None if the resource does not exist OR belongs to another site/tenant.
    """
    stmt = (
        build_site_scoped_query(model, site_id, organization_id)
        .where(model.id == resource_id)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def list_site_scoped_resources(
    session: AsyncSession,
    model: Type[T],
    site_id: uuid.UUID,
    organization_id: uuid.UUID
) -> Sequence[T]:
    """
    Lists all resources of a given model belonging to the specified site and organization.
    """
    stmt = build_site_scoped_query(model, site_id, organization_id)
    result = await session.execute(stmt)
    return result.scalars().all()
