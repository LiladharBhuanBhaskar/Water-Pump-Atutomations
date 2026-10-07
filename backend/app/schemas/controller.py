import uuid
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

from app.models.controller import ControllerType, ControllerStatus

class ControllerCreate(BaseModel):
    station_id: uuid.UUID
    name: str = Field(..., min_length=1, max_length=150, description="Display name of the controller")
    controller_code: str = Field(..., min_length=1, max_length=50, description="Unique controller code within the station")
    device_uid: str = Field(..., min_length=1, max_length=100, description="Globally unique hardware device identifier")
    controller_type: Optional[ControllerType] = Field(default=ControllerType.ESP32, description="Type of controller hardware")
    status: Optional[ControllerStatus] = Field(default=ControllerStatus.ACTIVE, description="Operational status of the controller")
    firmware_version: Optional[str] = Field(default=None, max_length=50, description="Firmware version string")
    ip_address: Optional[str] = Field(default=None, max_length=45, description="IP address of controller")
    mac_address: Optional[str] = Field(default=None, max_length=17, description="MAC address of controller")
    description: Optional[str] = Field(default=None, max_length=500, description="Optional description")


class ControllerUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=150)
    controller_code: Optional[str] = Field(default=None, min_length=1, max_length=50)
    device_uid: Optional[str] = Field(default=None, min_length=1, max_length=100)
    controller_type: Optional[ControllerType] = None
    status: Optional[ControllerStatus] = None
    firmware_version: Optional[str] = Field(default=None, max_length=50)
    ip_address: Optional[str] = Field(default=None, max_length=45)
    mac_address: Optional[str] = Field(default=None, max_length=17)
    description: Optional[str] = Field(default=None, max_length=500)


class ControllerResponse(BaseModel):
    id: uuid.UUID
    station_id: uuid.UUID
    name: str
    controller_code: str
    device_uid: str
    controller_type: ControllerType
    status: ControllerStatus
    firmware_version: Optional[str] = None
    ip_address: Optional[str] = None
    mac_address: Optional[str] = None
    last_seen_at: Optional[datetime] = None
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
