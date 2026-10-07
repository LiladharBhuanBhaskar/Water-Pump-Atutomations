"""
HydraControl — Notification Service (Phase 17).
Provides decoupled multi-channel notification dispatching (In-App WebSocket, Email, SMS),
storm prevention throttling (5-minute cooldown), user notification preferences, and secret redaction.
"""

import uuid
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List

from app.schemas.notification import (
    NotificationChannel,
    NotificationSeverity,
    NotificationPreference,
    NotificationPreferenceUpdate,
    NotificationPayload,
    NotificationDispatchResult,
)
from app.services.audit_service import sanitize_audit_metadata
from app.websocket.streamer import stream_safety_alert

logger = logging.getLogger("hydracontrol.notifications")


class BaseNotificationProvider(ABC):
    """Abstract base provider for notification channels."""

    @abstractmethod
    async def send(self, payload: NotificationPayload) -> bool:
        pass


class InAppNotificationProvider(BaseNotificationProvider):
    """In-App notification provider that broadcasts over WebSockets."""

    async def send(self, payload: NotificationPayload) -> bool:
        try:
            await stream_safety_alert(
                event_type=f"NOTIFICATION_{payload.severity.value}",
                motor_id=payload.motor_id or uuid.UUID(int=0),
                motor_code=str(payload.motor_id or "STATION"),
                device_uid="",
                station_id=payload.station_id,
                description=f"{payload.title}: {payload.message}",
                payload={
                    "severity": payload.severity.value,
                    "event_type": payload.event_type,
                    "metadata": payload.metadata,
                },
                timestamp=payload.timestamp,
            )
            return True
        except Exception as e:
            logger.warning(f"InAppNotificationProvider broadcast error: {e}")
            return False


class MockEmailNotificationProvider(BaseNotificationProvider):
    """Mock Email provider recording sent emails in-memory for testing."""

    def __init__(self):
        self.sent_emails: List[Dict[str, Any]] = []

    async def send(self, payload: NotificationPayload) -> bool:
        self.sent_emails.append({
            "title": payload.title,
            "message": payload.message,
            "severity": payload.severity.value,
            "timestamp": payload.timestamp,
            "metadata": payload.metadata,
        })
        logger.info(f"[MOCK EMAIL] Sent: {payload.title}")
        return True


class MockSmsNotificationProvider(BaseNotificationProvider):
    """Mock SMS provider recording sent SMS in-memory for testing."""

    def __init__(self):
        self.sent_sms: List[Dict[str, Any]] = []

    async def send(self, payload: NotificationPayload) -> bool:
        self.sent_sms.append({
            "title": payload.title,
            "message": payload.message,
            "severity": payload.severity.value,
            "timestamp": payload.timestamp,
            "metadata": payload.metadata,
        })
        logger.info(f"[MOCK SMS] Sent: {payload.title}")
        return True


class NotificationService:
    def __init__(self):
        # Channel provider registry
        self.providers: Dict[NotificationChannel, BaseNotificationProvider] = {
            NotificationChannel.IN_APP: InAppNotificationProvider(),
            NotificationChannel.EMAIL: MockEmailNotificationProvider(),
            NotificationChannel.SMS: MockSmsNotificationProvider(),
        }

        # In-memory preference storage: user_id -> NotificationPreference
        self._preferences: Dict[uuid.UUID, NotificationPreference] = {}

        # In-memory throttling tracker: throttle_key -> last_sent_datetime
        # Throttling rule: max 1 alert per 5 minutes per (target_id, event_type)
        self._throttle_cache: Dict[str, datetime] = {}
        self.cooldown_seconds: int = 300  # 5 minutes

    def get_user_preferences(self, user_id: uuid.UUID) -> NotificationPreference:
        """Get or initialize default notification preferences for a user."""
        if user_id not in self._preferences:
            self._preferences[user_id] = NotificationPreference(
                user_id=user_id,
                email_enabled=True,
                sms_enabled=False,
                in_app_enabled=True,
                min_severity=NotificationSeverity.INFO,
            )
        return self._preferences[user_id]

    def update_user_preferences(
        self, user_id: uuid.UUID, update: NotificationPreferenceUpdate
    ) -> NotificationPreference:
        """Update notification preferences for a user."""
        pref = self.get_user_preferences(user_id)
        if update.email_enabled is not None:
            pref.email_enabled = update.email_enabled
        if update.sms_enabled is not None:
            pref.sms_enabled = update.sms_enabled
        if update.in_app_enabled is not None:
            pref.in_app_enabled = update.in_app_enabled
        if update.min_severity is not None:
            pref.min_severity = update.min_severity

        self._preferences[user_id] = pref
        return pref

    def _is_throttled(
        self,
        target_id: Optional[uuid.UUID],
        event_type: Optional[str],
        now: datetime,
    ) -> bool:
        """Check if notification event is within cooldown period."""
        if not target_id or not event_type:
            return False

        key = f"{target_id}:{event_type}"
        last_time = self._throttle_cache.get(key)
        if last_time:
            elapsed = (now - last_time).total_seconds()
            if elapsed < self.cooldown_seconds:
                return True

        self._throttle_cache[key] = now
        return False

    async def dispatch_notification(
        self,
        title: str,
        message: str,
        severity: NotificationSeverity = NotificationSeverity.INFO,
        channels: Optional[List[NotificationChannel]] = None,
        organization_id: Optional[uuid.UUID] = None,
        site_id: Optional[uuid.UUID] = None,
        station_id: Optional[uuid.UUID] = None,
        motor_id: Optional[uuid.UUID] = None,
        event_type: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        bypass_throttle: bool = False,
    ) -> NotificationDispatchResult:
        """
        Dispatches a notification across specified channels with throttling protection and secret scrubbing.
        """
        now = datetime.now(timezone.utc)
        target_id = motor_id or station_id or site_id or organization_id

        # 1. Storm Throttling Check
        if not bypass_throttle and self._is_throttled(target_id, event_type, now):
            return NotificationDispatchResult(
                notification_id=str(uuid.uuid4()),
                title=title,
                severity=severity,
                delivered_channels=[],
                throttled=True,
                reason=f"Notification suppressed by storm prevention cooldown ({self.cooldown_seconds}s).",
                timestamp=now,
            )

        # 2. Scrub sensitive data from metadata
        clean_metadata = sanitize_audit_metadata(metadata)

        payload = NotificationPayload(
            title=title,
            message=message,
            severity=severity,
            channels=channels or [NotificationChannel.IN_APP, NotificationChannel.EMAIL],
            organization_id=organization_id,
            site_id=site_id,
            station_id=station_id,
            motor_id=motor_id,
            event_type=event_type,
            metadata=clean_metadata,
            timestamp=now,
        )

        delivered: List[NotificationChannel] = []
        for ch in payload.channels:
            provider = self.providers.get(ch)
            if provider:
                success = await provider.send(payload)
                if success:
                    delivered.append(ch)

        return NotificationDispatchResult(
            notification_id=str(uuid.uuid4()),
            title=title,
            severity=severity,
            delivered_channels=delivered,
            throttled=False,
            reason="DELIVERED",
            timestamp=now,
        )


notification_service = NotificationService()
