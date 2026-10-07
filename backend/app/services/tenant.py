"""
HydraControl — Tenant Isolation & Organization-Scoped Query Services
Provides secure, single-query tenant boundaries across direct and hierarchical domain models.
"""
import uuid
from typing import Type, TypeVar, Optional, Sequence
from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.organization import Organization
from app.models.site import Site
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
from app.models.user import User

T = TypeVar("T")

# Map of model classes to their join chain function or path to reach Site.organization_id
def build_org_scoped_query(model: Type[T], organization_id: uuid.UUID) -> Select:
    """
    Builds a secure SQLAlchemy SELECT statement that filters records by tenant organization_id
    using direct foreign keys or explicit relational join paths through the domain hierarchy.
    """
    if model is Organization:
        return select(Organization).where(Organization.id == organization_id)
    
    if model in (Site, User, AuditLog):
        return select(model).where(model.organization_id == organization_id)
        
    if model is Station:
        return (
            select(Station)
            .join(Site, Station.site_id == Site.id)
            .where(Site.organization_id == organization_id)
        )
        
    if model is StationSettings:
        return (
            select(StationSettings)
            .join(Station, StationSettings.station_id == Station.id)
            .join(Site, Station.site_id == Site.id)
            .where(Site.organization_id == organization_id)
        )
        
    if model is AutomationRule:
        return (
            select(AutomationRule)
            .join(Station, AutomationRule.station_id == Station.id)
            .join(Site, Station.site_id == Site.id)
            .where(Site.organization_id == organization_id)
        )
        
    if model is Controller:
        return (
            select(Controller)
            .join(Station, Controller.station_id == Station.id)
            .join(Site, Station.site_id == Site.id)
            .where(Site.organization_id == organization_id)
        )
        
    if model is Motor:
        return (
            select(Motor)
            .join(Controller, Motor.controller_id == Controller.id)
            .join(Station, Controller.station_id == Station.id)
            .join(Site, Station.site_id == Site.id)
            .where(Site.organization_id == organization_id)
        )
        
    if model is Sensor:
        return (
            select(Sensor)
            .join(Controller, Sensor.controller_id == Controller.id)
            .join(Station, Controller.station_id == Station.id)
            .join(Site, Station.site_id == Site.id)
            .where(Site.organization_id == organization_id)
        )
        
    if model is TelemetryReading:
        return (
            select(TelemetryReading)
            .join(Sensor, TelemetryReading.sensor_id == Sensor.id)
            .join(Controller, Sensor.controller_id == Controller.id)
            .join(Station, Controller.station_id == Station.id)
            .join(Site, Station.site_id == Site.id)
            .where(Site.organization_id == organization_id)
        )
        
    if model is MotorCommand:
        return (
            select(MotorCommand)
            .join(Motor, MotorCommand.motor_id == Motor.id)
            .join(Controller, Motor.controller_id == Controller.id)
            .join(Station, Controller.station_id == Station.id)
            .join(Site, Station.site_id == Site.id)
            .where(Site.organization_id == organization_id)
        )
        
    if model is MotorEvent:
        return (
            select(MotorEvent)
            .join(Motor, MotorEvent.motor_id == Motor.id)
            .join(Controller, Motor.controller_id == Controller.id)
            .join(Station, Controller.station_id == Station.id)
            .join(Site, Station.site_id == Site.id)
            .where(Site.organization_id == organization_id)
        )
        
    raise ValueError(f"Model {model.__name__} does not have a mapped tenant ownership chain.")


async def get_org_scoped_resource(
    session: AsyncSession,
    model: Type[T],
    resource_id: uuid.UUID,
    organization_id: uuid.UUID
) -> Optional[T]:
    """
    Safely retrieves a single resource by its primary key ID ensuring it belongs to the specified organization.
    Performs ID matching and tenant ownership verification in a single atomic database query.
    Returns None if the resource does not exist OR belongs to another tenant.
    """
    stmt = build_org_scoped_query(model, organization_id).where(model.id == resource_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def list_org_scoped_resources(
    session: AsyncSession,
    model: Type[T],
    organization_id: uuid.UUID
) -> Sequence[T]:
    """
    Lists all resources of a given model belonging to the specified organization.
    """
    stmt = build_org_scoped_query(model, organization_id)
    result = await session.execute(stmt)
    return result.scalars().all()
