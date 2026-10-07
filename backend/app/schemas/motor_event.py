"""Pydantic schemas for MotorEvent query responses (Phase 18 - Wave A)."""

import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, ConfigDict
from app.models.motor_event import MotorEventType, MotorEventSource


class MotorEventResponse(BaseModel):
    id: uuid.UUID
    motor_id: uuid.UUID
    event_type: MotorEventType
    source: MotorEventSource
    occurred_at: datetime
    event_payload: Optional[Dict[str, Any]] = None
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
