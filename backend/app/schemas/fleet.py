"""
HydraControl — Fleet Management Schemas (Phase 20).
Defines aggregated models for enterprise multi-site fleet monitoring, operational statuses, and safety rollups.
"""

import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class MotorFleetStatus(BaseModel):
    total: int = 0
    running: int = 0
    off: int = 0
    fault: int = 0
    offline: int = 0
    maintenance: int = 0


class ActiveSafetyAlertSummary(BaseModel):
    motor_id: uuid.UUID
    motor_code: str
    station_id: uuid.UUID
    station_name: str
    site_id: uuid.UUID
    site_name: str
    status: str
    occurred_at: datetime


class SiteFleetSummary(BaseModel):
    site_id: uuid.UUID
    site_name: str
    site_code: str
    status: str
    station_count: int = 0
    controller_count: int = 0
    motor_count: int = 0
    running_motors: int = 0
    faulted_motors: int = 0


class OrganizationFleetSummary(BaseModel):
    organization_id: uuid.UUID
    organization_name: str
    organization_code: str
    site_count: int = 0
    station_count: int = 0
    controller_count: int = 0
    online_controllers: int = 0
    offline_controllers: int = 0
    motors: MotorFleetStatus
    total_sensor_count: int = 0
    total_power_kw: float = 0.0
    active_safety_alerts: List[ActiveSafetyAlertSummary] = Field(default_factory=list)
    sites: List[SiteFleetSummary] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.utcnow)
