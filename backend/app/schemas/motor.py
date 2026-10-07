import uuid
from typing import Optional
from decimal import Decimal
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

from app.models.motor import MotorType, MotorStatus

class MotorCreate(BaseModel):
    controller_id: uuid.UUID
    name: str = Field(..., min_length=1, max_length=150, description="Display name of the motor")
    motor_code: str = Field(..., min_length=1, max_length=50, description="Unique motor code within the controller")
    motor_type: Optional[MotorType] = Field(default=MotorType.WATER_PUMP, description="Type of motor/pump hardware")
    status: Optional[MotorStatus] = Field(default=MotorStatus.OFFLINE, description="Operational status of the motor")
    rated_power: Optional[Decimal] = Field(default=None, ge=0, description="Rated power in kW or HP")
    description: Optional[str] = Field(default=None, max_length=500, description="Optional description")


class MotorUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=150)
    motor_code: Optional[str] = Field(default=None, min_length=1, max_length=50)
    motor_type: Optional[MotorType] = None
    status: Optional[MotorStatus] = None
    rated_power: Optional[Decimal] = Field(default=None, ge=0)
    description: Optional[str] = Field(default=None, max_length=500)


class MotorResponse(BaseModel):
    id: uuid.UUID
    controller_id: uuid.UUID
    name: str
    motor_code: str
    motor_type: MotorType
    status: MotorStatus
    rated_power: Optional[Decimal] = None
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
