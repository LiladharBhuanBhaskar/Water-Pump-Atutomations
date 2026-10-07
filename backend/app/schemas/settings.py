"""Pydantic schemas for StationSettings (Phase 12 - Wave 2A)."""

import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class StationSettingsUpdate(BaseModel):
    timezone: Optional[str] = Field(default=None, max_length=64)
    auto_stop_on_tank_full: Optional[bool] = None
    water_level_threshold: Optional[float] = None
    turbidity_threshold: Optional[float] = None
    default_timer_seconds: Optional[int] = None
    offline_alert_enabled: Optional[bool] = None
    offline_timeout_seconds: Optional[int] = None


class StationSettingsResponse(BaseModel):
    id: uuid.UUID
    station_id: uuid.UUID
    timezone: str
    auto_stop_on_tank_full: bool
    water_level_threshold: Optional[float] = None
    turbidity_threshold: Optional[float] = None
    default_timer_seconds: Optional[int] = None
    offline_alert_enabled: bool
    offline_timeout_seconds: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
