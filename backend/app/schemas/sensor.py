import uuid
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

from app.models.sensor import SensorType, SensorStatus

class SensorCreate(BaseModel):
    controller_id: uuid.UUID
    name: str = Field(..., min_length=1, max_length=150, description="Display name of the sensor")
    sensor_code: str = Field(..., min_length=1, max_length=50, description="Unique sensor code within the controller")
    sensor_type: Optional[SensorType] = Field(default=SensorType.OTHER, description="Type of sensor measurement")
    status: Optional[SensorStatus] = Field(default=SensorStatus.ACTIVE, description="Operational status of the sensor")
    description: Optional[str] = Field(default=None, max_length=500, description="Optional description")


class SensorUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=150)
    sensor_code: Optional[str] = Field(default=None, min_length=1, max_length=50)
    sensor_type: Optional[SensorType] = None
    status: Optional[SensorStatus] = None
    description: Optional[str] = Field(default=None, max_length=500)


class SensorResponse(BaseModel):
    id: uuid.UUID
    controller_id: uuid.UUID
    name: str
    sensor_code: str
    sensor_type: SensorType
    status: SensorStatus
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
