"""Pydantic schemas for Schedules (Phase 16 - Wave A)."""

import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict, field_validator


class ScheduleCreate(BaseModel):
    station_id: uuid.UUID
    motor_id: uuid.UUID
    name: str = Field(..., min_length=1, max_length=150)
    days_of_week: List[str] = Field(default=["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"])
    start_time: str = Field(..., pattern=r"^([01]\d|2[0-3]):([0-5]\d)$", description="HH:MM 24-hour time")
    duration_seconds: int = Field(..., gt=0, le=86400, description="Duration in seconds (up to 24h)")
    is_active: bool = True

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v_clean = v.strip()
        if not v_clean:
            raise ValueError("Schedule name cannot be empty.")
        return v_clean


class ScheduleUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=150)
    days_of_week: Optional[List[str]] = None
    start_time: Optional[str] = Field(default=None, pattern=r"^([01]\d|2[0-3]):([0-5]\d)$")
    duration_seconds: Optional[int] = Field(default=None, gt=0, le=86400)
    is_active: Optional[bool] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v_clean = v.strip()
            if not v_clean:
                raise ValueError("Schedule name cannot be empty.")
            return v_clean
        return v


class ScheduleResponse(BaseModel):
    id: uuid.UUID
    station_id: uuid.UUID
    motor_id: uuid.UUID
    name: str
    days_of_week: List[str]
    start_time: str
    duration_seconds: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
