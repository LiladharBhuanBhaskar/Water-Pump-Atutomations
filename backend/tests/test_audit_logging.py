"""
HydraControl — Unit & Integration Tests for Audit Logging (Phase 19 - Wave A).
Verifies append-only audit logging, sensitive data scrubbing/redaction, RBAC query permissions, and immutability.
"""

import uuid
import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from app.main import app
from app.db.base import Base
from app.db.session import sync_engine, get_sync_session, AsyncSessionLocal
from app.models.user import User, UserRole
from app.models.organization import Organization, OrganizationStatus
from app.models.audit_log import AuditLog, AuditAction, AuditActorType
from app.services.audit_service import log_audit_event, query_audit_logs, sanitize_audit_metadata
from app.core.security import create_access_token, get_password_hash


@pytest.fixture(scope="module", autouse=True)
def setup_tables():
    Base.metadata.create_all(bind=sync_engine)
    yield
    Base.metadata.drop_all(bind=sync_engine)


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_sanitize_audit_metadata():
    """Verify recursive credential/token redaction in audit metadata."""
    raw_meta = {
        "user_email": "admin@hydracontrol.io",
        "action": "login",
        "password": "SuperSecretPassword123",
        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "nested": {
            "device_secret": "my-secret-key",
            "safe_param": 42,
        },
    }
    sanitized = sanitize_audit_metadata(raw_meta)
    assert sanitized["user_email"] == "admin@hydracontrol.io"
    assert sanitized["password"] == "[REDACTED]"
    assert sanitized["access_token"] == "[REDACTED]"
    assert sanitized["nested"]["device_secret"] == "[REDACTED]"
    assert sanitized["nested"]["safe_param"] == 42


@pytest.mark.asyncio
async def test_audit_service_logging_and_query():
    """Verify log_audit_event persists records and query_audit_logs applies filters."""
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()

    async with AsyncSessionLocal() as session:
        # 1. Create audit entries
        entry1 = await log_audit_event(
            session=session,
            action=AuditAction.START,
            resource_type="Motor",
            action_description="Started primary borewell pump",
            actor_user_id=user_id,
            organization_id=org_id,
            ip_address="192.168.1.50",
            user_agent="Mozilla/5.0",
            audit_metadata={"motor_code": "PUMP-01", "password_input": "secret"},
        )
        assert entry1.id is not None
        assert entry1.audit_metadata["password_input"] == "[REDACTED]"
        assert entry1.audit_metadata["motor_code"] == "PUMP-01"

        entry2 = await log_audit_event(
            session=session,
            action=AuditAction.EMERGENCY_STOP,
            resource_type="Motor",
            action_description="Emergency stop engaged by site manager",
            actor_user_id=user_id,
            organization_id=org_id,
        )
        assert entry2.id is not None

        # 2. Query as SUPER_ADMIN
        super_admin = User(
            id=uuid.uuid4(),
            email=f"sadmin_{uuid.uuid4().hex[:6]}@hydra.io",
            name="Super Admin",
            role=UserRole.SUPER_ADMIN,
            password_hash="hash",
            is_active=True,
        )
        logs = await query_audit_logs(
            session=session,
            current_user=super_admin,
            organization_id=org_id,
        )
        assert len(logs) == 2
        assert logs[0].action == AuditAction.EMERGENCY_STOP
        assert logs[1].action == AuditAction.START


def test_audit_logs_api_rbac_and_immutability(client: TestClient):
    """Verify RBAC on GET /api/v1/audit-logs: SuperAdmin & OrgAdmin allowed, Operator denied (403), No DELETE/UPDATE."""
    with get_sync_session() as session:
        org1 = Organization(
            id=uuid.uuid4(),
            name="Audit Org 1",
            organization_code=f"AUD1-{uuid.uuid4().hex[:6].upper()}",
            status=OrganizationStatus.ACTIVE,
        )
        org2 = Organization(
            id=uuid.uuid4(),
            name="Audit Org 2",
            organization_code=f"AUD2-{uuid.uuid4().hex[:6].upper()}",
            status=OrganizationStatus.ACTIVE,
        )
        session.add_all([org1, org2])
        session.flush()

        super_admin = User(
            id=uuid.uuid4(),
            email=f"sa_{uuid.uuid4().hex[:6]}@audit.io",
            name="Super Admin",
            role=UserRole.SUPER_ADMIN,
            password_hash=get_password_hash("Pass@123"),
            is_active=True,
        )
        org1_admin = User(
            id=uuid.uuid4(),
            email=f"oa1_{uuid.uuid4().hex[:6]}@audit.io",
            name="Org1 Admin",
            role=UserRole.ORGANIZATION_ADMIN,
            organization_id=org1.id,
            password_hash=get_password_hash("Pass@123"),
            is_active=True,
        )
        operator = User(
            id=uuid.uuid4(),
            email=f"op_{uuid.uuid4().hex[:6]}@audit.io",
            name="Operator",
            role=UserRole.STATION_OPERATOR,
            organization_id=org1.id,
            password_hash=get_password_hash("Pass@123"),
            is_active=True,
        )
        session.add_all([super_admin, org1_admin, operator])
        session.flush()

        # Seed audit entries for Org1 and Org2
        log1 = AuditLog(
            id=uuid.uuid4(),
            organization_id=org1.id,
            actor_user_id=org1_admin.id,
            actor_type=AuditActorType.USER,
            action=AuditAction.CONFIGURE,
            resource_type="StationSettings",
            action_description="Updated auto-stop threshold to 95%",
            occurred_at=datetime.now(timezone.utc),
        )
        log2 = AuditLog(
            id=uuid.uuid4(),
            organization_id=org2.id,
            actor_user_id=super_admin.id,
            actor_type=AuditActorType.USER,
            action=AuditAction.RESET,
            resource_type="Motor",
            action_description="Reset pump fault",
            occurred_at=datetime.now(timezone.utc),
        )
        session.add_all([log1, log2])
        session.commit()

        sa_id = super_admin.id
        oa1_id = org1_admin.id
        op_id = operator.id
        org1_id = org1.id
        org2_id = org2.id

    super_admin_token = create_access_token(sa_id)
    org1_admin_token = create_access_token(oa1_id)
    operator_token = create_access_token(op_id)

    # 1. SUPER_ADMIN can query all audit logs
    resp_sa = client.get(
        "/api/v1/audit-logs",
        headers={"Authorization": f"Bearer {super_admin_token}"},
    )
    assert resp_sa.status_code == 200
    sa_logs = resp_sa.json()
    assert len(sa_logs) >= 2

    # 2. ORG1_ADMIN only gets Org1 audit logs
    resp_oa = client.get(
        "/api/v1/audit-logs",
        headers={"Authorization": f"Bearer {org1_admin_token}"},
    )
    assert resp_oa.status_code == 200
    oa_logs = resp_oa.json()
    assert len(oa_logs) >= 1
    for log in oa_logs:
        assert log["organization_id"] == str(org1_id)

    # 3. STATION_OPERATOR is denied with 403 Forbidden
    resp_op = client.get(
        "/api/v1/audit-logs",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert resp_op.status_code == 403

    # 4. Immutability checks: No DELETE or PUT/PATCH endpoints for audit logs (405 Method Not Allowed)
    resp_del = client.delete(
        "/api/v1/audit-logs",
        headers={"Authorization": f"Bearer {super_admin_token}"},
    )
    assert resp_del.status_code == 405

    resp_put = client.put(
        "/api/v1/audit-logs",
        headers={"Authorization": f"Bearer {super_admin_token}"},
    )
    assert resp_put.status_code == 405
