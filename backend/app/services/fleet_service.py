"""
HydraControl — Fleet Management Service (Phase 20).
Aggregates enterprise multi-site operational status, running/faulted motors, online controllers,
and active critical safety alerts with strict multi-tenant isolation and performant queries.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.models.organization import Organization
from app.models.site import Site
from app.models.station import Station
from app.models.controller import Controller, ControllerStatus
from app.models.motor import Motor, MotorStatus
from app.models.sensor import Sensor
from app.models.user import User, UserRole
from app.schemas.fleet import (
    OrganizationFleetSummary,
    MotorFleetStatus,
    SiteFleetSummary,
    ActiveSafetyAlertSummary,
)


async def get_organization_fleet_summary(
    session: AsyncSession,
    organization_id: uuid.UUID,
    current_user: User,
) -> Optional[OrganizationFleetSummary]:
    """
    Computes an organization-wide fleet summary.
    Enforces multi-tenant isolation: SUPER_ADMIN allowed, ORG_ADMIN allowed for own org, others checked.
    """
    # 1. Organization Authorization Check
    if current_user.role != UserRole.SUPER_ADMIN:
        if current_user.organization_id != organization_id:
            return None

    # 2. Fetch Organization with complete operational hierarchy in a single optimized pass
    stmt = (
        select(Organization)
        .where(Organization.id == organization_id)
        .options(
            selectinload(Organization.sites)
            .selectinload(Site.stations)
            .selectinload(Station.controllers)
            .selectinload(Controller.motors),
            selectinload(Organization.sites)
            .selectinload(Site.stations)
            .selectinload(Station.controllers)
            .selectinload(Controller.sensors),
        )
    )
    res = await session.execute(stmt)
    org = res.scalar_one_or_none()
    if org is None:
        return None

    # 3. Aggregate metrics across the loaded hierarchy
    site_summaries: List[SiteFleetSummary] = []
    active_alerts: List[ActiveSafetyAlertSummary] = []

    total_stations = 0
    total_controllers = 0
    online_controllers = 0
    offline_controllers = 0
    total_sensors = 0
    total_power_kw = 0.0

    motor_counts = MotorFleetStatus()

    for site in org.sites:
        site_station_count = len(site.stations)
        total_stations += site_station_count

        site_controller_count = 0
        site_motor_count = 0
        site_running_motors = 0
        site_faulted_motors = 0

        for station in site.stations:
            for controller in station.controllers:
                site_controller_count += 1
                total_controllers += 1

                if controller.status == ControllerStatus.ACTIVE:
                    online_controllers += 1
                else:
                    offline_controllers += 1

                total_sensors += len(controller.sensors)

                for motor in controller.motors:
                    site_motor_count += 1
                    motor_counts.total += 1

                    if motor.status in (MotorStatus.ON, MotorStatus.STARTING):
                        motor_counts.running += 1
                        site_running_motors += 1
                        total_power_kw += float(motor.rated_power or 0.0)
                    elif motor.status in (MotorStatus.OFF, MotorStatus.STOPPING):
                        motor_counts.off += 1
                    elif motor.status in (MotorStatus.FAULT,):
                        motor_counts.fault += 1
                        site_faulted_motors += 1
                        active_alerts.append(
                            ActiveSafetyAlertSummary(
                                motor_id=motor.id,
                                motor_code=motor.motor_code,
                                station_id=station.id,
                                station_name=station.name,
                                site_id=site.id,
                                site_name=site.name,
                                status=motor.status.value,
                                occurred_at=motor.updated_at or motor.created_at or datetime.now(timezone.utc),
                            )
                        )
                    elif motor.status in (MotorStatus.MAINTENANCE,):
                        motor_counts.maintenance += 1
                    else:
                        motor_counts.offline += 1

        site_summaries.append(
            SiteFleetSummary(
                site_id=site.id,
                site_name=site.name,
                site_code=site.site_code,
                status=site.status.value,
                station_count=site_station_count,
                controller_count=site_controller_count,
                motor_count=site_motor_count,
                running_motors=site_running_motors,
                faulted_motors=site_faulted_motors,
            )
        )

    return OrganizationFleetSummary(
        organization_id=org.id,
        organization_name=org.name,
        organization_code=org.organization_code,
        site_count=len(org.sites),
        station_count=total_stations,
        controller_count=total_controllers,
        online_controllers=online_controllers,
        offline_controllers=offline_controllers,
        motors=motor_counts,
        total_sensor_count=total_sensors,
        total_power_kw=round(total_power_kw, 2),
        active_safety_alerts=active_alerts,
        sites=site_summaries,
        generated_at=datetime.now(timezone.utc),
    )
