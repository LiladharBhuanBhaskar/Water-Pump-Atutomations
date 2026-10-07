"""
HydraControl — Notification Schemas (Phase 17).
Defines schemas for multi-channel notifications, preferences, severity levels, and delivery tracking.
"""

import uuid
import enum
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class NotificationChannel(str, enum.Enum):
    IN_APP = "IN_APP"
    EMAIL = "EMAIL"
    SMS = "SMS"


class NotificationSeverity(str, enum.Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class NotificationPreference(BaseModel):
    user_id: uuid.UUID
    email_enabled: bool = True
    sms_enabled: bool = False
    in_app_enabled: bool = True
    min_severity: NotificationSeverity = NotificationSeverity.INFO


class NotificationPreferenceUpdate(BaseModel):
    email_enabled: Optional[bool] = None
    sms_enabled: Optional[bool] = None
    in_app_enabled: Optional[bool] = None
    min_severity: Optional[NotificationSeverity] = None


class NotificationPayload(BaseModel):
    title: str
    message: str
    severity: NotificationSeverity = NotificationSeverity.INFO
    channels: List[NotificationChannel] = Field(default_factory=lambda: [NotificationChannel.IN_APP])
    organization_id: Optional[uuid.UUID] = None
    site_id: Optional[uuid.UUID] = None
    station_id: Optional[uuid.UUID] = None
    motor_id: Optional[uuid.UUID] = None
    event_type: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class NotificationDispatchResult(BaseModel):
    notification_id: str
    title: str
    severity: NotificationSeverity
    delivered_channels: List[NotificationChannel]
    throttled: bool = False
    reason: Optional[str] = None
    timestamp: datetime
