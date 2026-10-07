"""
HydraControl — Notification & Preference API (Phase 17).
Provides endpoints to manage user multi-channel notification preferences and trigger test dispatches.
"""

from fastapi import APIRouter, Depends, status
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.notification import (
    NotificationPreference,
    NotificationPreferenceUpdate,
    NotificationDispatchResult,
    NotificationSeverity,
    NotificationChannel,
)
from app.services.notification_service import notification_service

router = APIRouter(tags=["Notifications"])


@router.get("/users/me/notification-preferences", response_model=NotificationPreference)
async def get_my_notification_preferences(
    current_user: User = Depends(get_current_user),
):
    """Retrieve current user's multi-channel notification preferences."""
    return notification_service.get_user_preferences(current_user.id)


@router.put("/users/me/notification-preferences", response_model=NotificationPreference)
async def update_my_notification_preferences(
    req: NotificationPreferenceUpdate,
    current_user: User = Depends(get_current_user),
):
    """Update current user's multi-channel notification preferences."""
    return notification_service.update_user_preferences(current_user.id, req)


@router.post("/notifications/test", response_model=NotificationDispatchResult)
async def trigger_test_notification(
    current_user: User = Depends(get_current_user),
):
    """Trigger a test notification to verify delivery channels."""
    pref = notification_service.get_user_preferences(current_user.id)
    channels = []
    if pref.in_app_enabled:
        channels.append(NotificationChannel.IN_APP)
    if pref.email_enabled:
        channels.append(NotificationChannel.EMAIL)
    if pref.sms_enabled:
        channels.append(NotificationChannel.SMS)

    return await notification_service.dispatch_notification(
        title="HydraControl Test Alert",
        message=f"Test notification dispatched successfully for user {current_user.email}.",
        severity=NotificationSeverity.INFO,
        channels=channels or [NotificationChannel.IN_APP],
        organization_id=current_user.organization_id,
        bypass_throttle=True,
    )
