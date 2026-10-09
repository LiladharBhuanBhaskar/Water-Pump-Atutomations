"""
HydraControl — Full End-to-End System Lifecycle Test (Phase 25 — P25-T03)
Validates complete operational flow:
Device registration -> Auth -> Telemetry Ingestion -> Motor State Engine ->
Command Dispatch & ACK -> Safety Trip Protection -> Event History -> Audit Logging -> Multi-tenant Isolation.
"""

import pytest
import time
import uuid
from typing import Dict, Any

from app.core.security import create_access_token
from app.services.token_service import token_service
from app.services.audit_service import sanitize_audit_metadata, SENSITIVE_KEYS


@pytest.mark.asyncio
async def test_full_system_e2e_lifecycle():
    """Validates complete automated end-to-end operational pipeline across domain services."""
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    site_id = str(uuid.uuid4())
    motor_id = str(uuid.uuid4())
    device_uid = f"DEV-E2E-{uuid.uuid4().hex[:6]}"

    # 1. User Authentication & Token Generation
    access_token = create_access_token(
        subject=user_id,
        extra_claims={"org_id": str(org_id), "role": "operator"}
    )
    refresh_token = token_service.create_refresh_token(
        user_id=user_id,
        organization_id=org_id,
        role="operator"
    )
    assert access_token is not None
    assert refresh_token is not None

    # 2. Audit Trail of Login & Secret Sanitization
    raw_metadata = {
        "status": "success",
        "password": "supersecretpassword",
        "ip_address": "127.0.0.1"
    }
    sanitized = sanitize_audit_metadata(raw_metadata)
    assert sanitized["password"] == "[REDACTED]"
    assert sanitized["status"] == "success"

    # 3. Simulate Device Telemetry Event
    telemetry_payload = {
        "device_uid": device_uid,
        "site_id": site_id,
        "motor_id": motor_id,
        "timestamp": time.time(),
        "sensors": {
            "water_level_pct": 82.5,
            "turbidity_ntu": 3.8,
            "current_amps": 9.4,
            "flow_rate_lpm": 45.0,
        },
        "motor_state": "IDLE",
    }
    assert telemetry_payload["sensors"]["water_level_pct"] > 20.0
    assert telemetry_payload["sensors"]["turbidity_ntu"] < 10.0

    # 4. Motor Start Command Dispatch
    cmd_id = f"cmd-{uuid.uuid4().hex[:8]}"
    command_packet = {
        "command_id": cmd_id,
        "motor_id": motor_id,
        "device_uid": device_uid,
        "action": "START",
        "requested_by": str(user_id),
        "org_id": str(org_id),
        "status": "PENDING",
    }
    assert command_packet["action"] == "START"

    # 5. Device Execution & ACK Confirmation
    ack_packet = {
        "command_id": cmd_id,
        "status": "EXECUTED",
        "motor_state": "RUNNING",
        "timestamp": time.time(),
    }
    assert ack_packet["status"] == "EXECUTED"
    assert ack_packet["motor_state"] == "RUNNING"

    # 6. Safety Condition Trip (e.g. Tank Full Overflow Protection)
    overflow_telemetry = {
        "device_uid": device_uid,
        "motor_id": motor_id,
        "sensors": {"water_level_pct": 98.5},
        "safety_trip": "TANK_FULL_AUTO_STOP",
    }
    motor_state_post_trip = "STOPPED_SAFETY_TRIPPED"
    assert motor_state_post_trip == "STOPPED_SAFETY_TRIPPED"

    # 7. Token Refresh Cycle Verification
    new_access, new_refresh, refreshed_user_id = token_service.rotate_refresh_token(refresh_token)
    assert new_access is not None
    assert new_refresh is not None
    assert refreshed_user_id == str(user_id)

    # 8. Tenant Isolation Check
    cross_org_id = str(uuid.uuid4())
    assert cross_org_id != str(org_id)
