import uuid
from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

from app.models.motor_command import CommandType, CommandStatus


class MotorCommandRequest(BaseModel):
    """Optional payload / parameters passed when dispatching a motor command."""
    payload: Optional[Dict[str, Any]] = Field(default=None, description="Optional parameters (e.g. timeout, target flow/level)")


class MotorCommandResponse(BaseModel):
    """Response containing status and lifecycle timestamps of a motor command."""
    id: uuid.UUID
    motor_id: uuid.UUID
    command_type: CommandType
    status: CommandStatus
    requested_by: Optional[uuid.UUID] = None
    command_payload: Optional[Dict[str, Any]] = None
    requested_at: datetime
    sent_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    executed_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    error_message: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
