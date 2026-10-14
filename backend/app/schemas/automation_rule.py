"""Pydantic schemas for AutomationRule (Phase 12 - Wave 2A)."""

import uuid
from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field, ConfigDict, field_validator
from app.models.automation_rule import (
    AutomationRuleType,
    AutomationOperator,
    AutomationAction,
    AutomationRuleStatus,
)


class AutomationRuleCreate(BaseModel):
    station_id: uuid.UUID = Field(..., description="Target physical station ID")
    name: str = Field(..., min_length=1, max_length=150, description="Rule display name")
    description: Optional[str] = Field(default=None, max_length=500)
    rule_type: AutomationRuleType
    status: Optional[AutomationRuleStatus] = AutomationRuleStatus.ACTIVE
    sensor_id: Optional[uuid.UUID] = None
    operator: Optional[AutomationOperator] = None
    threshold_value: Optional[float] = None
    threshold_unit: Optional[str] = Field(default=None, max_length=32)
    duration_seconds: Optional[int] = None
    motor_id: uuid.UUID
    action: AutomationAction
    cooldown_seconds: Optional[int] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v_stripped = v.strip()
        if not v_stripped:
            raise ValueError("Rule name cannot be blank.")
        return v_stripped

    @field_validator("rule_type", mode="before")
    @classmethod
    def validate_rule_type(cls, v: Any) -> Any:
        if isinstance(v, str):
            v_upper = v.upper()
            if "TANK" in v_upper or "LEVEL" in v_upper:
                return AutomationRuleType.WATER_LEVEL
            elif "TURBIDITY" in v_upper:
                return AutomationRuleType.TURBIDITY
            elif "TIMER" in v_upper or "SCHEDULE" in v_upper:
                return AutomationRuleType.TIMER
        return v

    @field_validator("action", mode="before")
    @classmethod
    def validate_action(cls, v: Any) -> Any:
        if isinstance(v, str):
            v_upper = v.upper()
            if v_upper in ("STOP", "STOP_MOTOR"):
                return AutomationAction.STOP_MOTOR
            elif v_upper in ("START", "START_MOTOR"):
                return AutomationAction.START_MOTOR
            elif v_upper in ("RESET", "RESET_MOTOR"):
                return AutomationAction.RESET_MOTOR
            elif v_upper in ("LOCKOUT", "EMERGENCY_STOP", "EMERGENCY_STOP_MOTOR"):
                return AutomationAction.EMERGENCY_STOP_MOTOR
        return v


class AutomationRuleUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=150)
    description: Optional[str] = Field(default=None, max_length=500)
    rule_type: Optional[AutomationRuleType] = None
    status: Optional[AutomationRuleStatus] = None
    sensor_id: Optional[uuid.UUID] = None
    operator: Optional[AutomationOperator] = None
    threshold_value: Optional[float] = None
    threshold_unit: Optional[str] = Field(default=None, max_length=32)
    duration_seconds: Optional[int] = None
    motor_id: Optional[uuid.UUID] = None
    action: Optional[AutomationAction] = None
    cooldown_seconds: Optional[int] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v_stripped = v.strip()
            if not v_stripped:
                raise ValueError("Rule name cannot be blank.")
            return v_stripped
        return v


class AutomationRuleResponse(BaseModel):
    id: uuid.UUID
    station_id: uuid.UUID
    name: str
    description: Optional[str]
    rule_type: AutomationRuleType
    status: AutomationRuleStatus
    sensor_id: Optional[uuid.UUID]
    operator: Optional[AutomationOperator]
    threshold_value: Optional[float]
    threshold_unit: Optional[str]
    duration_seconds: Optional[int]
    motor_id: uuid.UUID
    action: AutomationAction
    cooldown_seconds: Optional[int]
    created_by: Optional[uuid.UUID]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
