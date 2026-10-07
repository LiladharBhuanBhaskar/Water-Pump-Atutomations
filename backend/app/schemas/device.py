import uuid
from typing import Optional
from datetime import datetime
import enum
from pydantic import BaseModel, Field

try:
    from app.models.controller import ControllerStatus, ControllerType
except ImportError:
    from backend.app.models.controller import ControllerStatus, ControllerType


class LivenessState(str, enum.Enum):
    """Calculated liveness state based on last_seen_at timestamp."""
    ONLINE = "ONLINE"
    STALE = "STALE"
    OFFLINE = "OFFLINE"
    DECOMMISSIONED = "DECOMMISSIONED"


class DeviceRegistrationRequest(BaseModel):
    """Payload sent by IoT device/gateway during provisioning/initial connection."""
    device_uid: str = Field(..., min_length=1, max_length=100, description="Unique hardware identifier")
    firmware_version: Optional[str] = Field(None, max_length=50)
    ip_address: Optional[str] = Field(None, max_length=45)
    mac_address: Optional[str] = Field(None, max_length=17)
    controller_type: Optional[ControllerType] = None


class DeviceRegistrationResponse(BaseModel):
    """Response returned upon successful device provisioning."""
    controller_id: uuid.UUID
    station_id: uuid.UUID
    device_uid: str
    controller_name: str
    status: ControllerStatus
    device_token: str
    server_time: datetime
    mqtt_topic_prefix: str


class DeviceHeartbeatRequest(BaseModel):
    """Payload sent periodically by IoT device to report liveness and telemetry/diagnostics."""
    device_uid: str = Field(..., min_length=1, max_length=100, description="Unique hardware identifier")
    firmware_version: Optional[str] = Field(None, max_length=50)
    ip_address: Optional[str] = Field(None, max_length=45)
    uptime_seconds: Optional[int] = Field(None, ge=0)
    free_heap: Optional[int] = Field(None, ge=0)
    rssi: Optional[int] = None
    status: Optional[ControllerStatus] = None


class DeviceHeartbeatResponse(BaseModel):
    """Response returned upon heartbeat processing."""
    device_uid: str
    status: ControllerStatus
    server_time: datetime
    acknowledged: bool = True
    commands_pending: int = 0


class DeviceLivenessResponse(BaseModel):
    """Detailed liveness and status report for a controller."""
    controller_id: uuid.UUID
    station_id: uuid.UUID
    device_uid: str
    controller_name: str
    status: ControllerStatus
    liveness_state: LivenessState
    last_seen_at: Optional[datetime] = None
    seconds_since_last_seen: Optional[float] = None
