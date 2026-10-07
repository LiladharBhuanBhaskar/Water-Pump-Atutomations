"""
HydraControl — Unit & Integration Tests for Notification Service & Preferences (Phase 17).
Verifies multi-channel provider dispatching, mock adapters, storm prevention throttling,
secret scrubbing, and user preference REST APIs.
"""

import uuid
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from app.main import app
from app.db.base import Base
from app.db.session import sync_engine, get_sync_session
from app.models.user import User, UserRole
from app.models.organization import Organization, OrganizationStatus
from app.core.security import create_access_token, get_password_hash
from app.schemas.notification import (
    NotificationChannel,
    NotificationSeverity,
    NotificationPreferenceUpdate,
)
from app.services.notification_service import (
    notification_service,
    NotificationService,
    MockEmailNotificationProvider,
    MockSmsNotificationProvider,
)


@pytest.fixture(scope="module", autouse=True)
def setup_tables():
    Base.metadata.create_all(bind=sync_engine)
    yield
    Base.metadata.drop_all(bind=sync_engine)


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def helper_create_test_user():
    with get_sync_session() as session:
        org = Organization(
            id=uuid.uuid4(),
            name="Notification Org",
            organization_code=f"NOTIF-{uuid.uuid4().hex[:6].upper()}",
            status=OrganizationStatus.ACTIVE,
        )
        session.add(org)
        session.flush()

        user = User(
            id=uuid.uuid4(),
            email=f"notify_{uuid.uuid4().hex[:6]}@test.io",
            name="Notification User",
            role=UserRole.ORGANIZATION_ADMIN,
            organization_id=org.id,
            password_hash=get_password_hash("Pass@123"),
            is_active=True,
        )
        session.add(user)
        session.commit()
        return {"user_id": user.id, "org_id": org.id, "email": user.email}


@pytest.mark.asyncio
async def test_notification_dispatch_and_mock_providers():
    """Verify notification dispatching to mocked Email and SMS providers."""
    svc = NotificationService()
    email_prov: MockEmailNotificationProvider = svc.providers[NotificationChannel.EMAIL]  # type: ignore
    sms_prov: MockSmsNotificationProvider = svc.providers[NotificationChannel.SMS]  # type: ignore

    res = await svc.dispatch_notification(
        title="Turbidity Safety Alert",
        message="Turbidity level exceeded 25.0 NTU trip cutoff.",
        severity=NotificationSeverity.CRITICAL,
        channels=[NotificationChannel.EMAIL, NotificationChannel.SMS],
        event_type="TURBIDITY_TRIP",
        motor_id=uuid.uuid4(),
        metadata={"measured_ntu": 28.5, "password_leak": "supersecret"},
    )

    assert res.throttled is False
    assert len(res.delivered_channels) == 2
    assert NotificationChannel.EMAIL in res.delivered_channels
    assert NotificationChannel.SMS in res.delivered_channels

    # Verify Email Provider received message with redacted metadata
    assert len(email_prov.sent_emails) == 1
    assert email_prov.sent_emails[0]["title"] == "Turbidity Safety Alert"
    assert email_prov.sent_emails[0]["metadata"]["password_leak"] == "[REDACTED]"
    assert email_prov.sent_emails[0]["metadata"]["measured_ntu"] == 28.5

    # Verify SMS Provider received message
    assert len(sms_prov.sent_sms) == 1
    assert sms_prov.sent_sms[0]["title"] == "Turbidity Safety Alert"


@pytest.mark.asyncio
async def test_notification_storm_throttling():
    """Verify maximum 1 alert per 5 minutes per motor fault type."""
    svc = NotificationService()
    svc.cooldown_seconds = 300  # 5 minutes
    motor_id = uuid.uuid4()

    # Pass 1: First alert delivered
    res1 = await svc.dispatch_notification(
        title="Dry-Run Trip",
        message="Flow rate below minimum threshold.",
        severity=NotificationSeverity.CRITICAL,
        event_type="DRY_RUN_TRIP",
        motor_id=motor_id,
    )
    assert res1.throttled is False

    # Pass 2: Immediate second alert of same type is throttled
    res2 = await svc.dispatch_notification(
        title="Dry-Run Trip",
        message="Flow rate below minimum threshold.",
        severity=NotificationSeverity.CRITICAL,
        event_type="DRY_RUN_TRIP",
        motor_id=motor_id,
    )
    assert res2.throttled is True
    assert "suppressed by storm prevention cooldown" in (res2.reason or "")

    # Pass 3: Different event type on same motor is NOT throttled
    res3 = await svc.dispatch_notification(
        title="Overload Trip",
        message="Current exceeded 12.0A.",
        severity=NotificationSeverity.CRITICAL,
        event_type="OVERLOAD_TRIP",
        motor_id=motor_id,
    )
    assert res3.throttled is False


def test_notification_preferences_api(client: TestClient):
    """Verify GET/PUT /api/v1/users/me/notification-preferences and test notification trigger."""
    u = helper_create_test_user()
    token = create_access_token(u["user_id"])

    # 1. GET initial default preferences
    get_resp = client.get(
        "/api/v1/users/me/notification-preferences",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_resp.status_code == 200
    pref = get_resp.json()
    assert pref["email_enabled"] is True
    assert pref["sms_enabled"] is False
    assert pref["in_app_enabled"] is True
    assert pref["min_severity"] == "INFO"

    # 2. PUT update preferences (enable SMS, set min_severity=WARNING)
    put_resp = client.put(
        "/api/v1/users/me/notification-preferences",
        json={"sms_enabled": True, "min_severity": "WARNING"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert put_resp.status_code == 200
    updated = put_resp.json()
    assert updated["sms_enabled"] is True
    assert updated["min_severity"] == "WARNING"

    # 3. Trigger test notification
    test_resp = client.post(
        "/api/v1/notifications/test",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert test_resp.status_code == 200
    dispatch_res = test_resp.json()
    assert dispatch_res["throttled"] is False
    assert NotificationChannel.EMAIL in dispatch_res["delivered_channels"]
    assert NotificationChannel.SMS in dispatch_res["delivered_channels"]
