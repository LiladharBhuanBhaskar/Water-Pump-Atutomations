"""
HydraControl — Audit Logging Service (Phase 19 - Wave A)
Provides tamper-evident, append-only audit event recording for critical operations
with automated credential redaction and multi-tenant scoping.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.audit_log import AuditLog, AuditAction, AuditActorType
from app.models.user import User, UserRole

SENSITIVE_KEYS = {
    "password", "password_hash", "access_token", "token", "refresh_token",
    "secret", "device_secret", "api_key", "authorization", "auth", "credential"
}


def sanitize_audit_metadata(metadata: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Recursively scrub credentials and sensitive fields from audit metadata."""
    if not metadata:
        return None

    sanitized = {}
    for k, v in metadata.items():
        k_lower = str(k).lower()
        if any(sensitive in k_lower for sensitive in SENSITIVE_KEYS):
            sanitized[k] = "[REDACTED]"
        elif isinstance(v, dict):
            sanitized[k] = sanitize_audit_metadata(v)
        else:
            sanitized[k] = v
    return sanitized


async def log_audit_event(
    session: AsyncSession,
    action: AuditAction,
    resource_type: str,
    action_description: str,
    resource_id: Optional[Any] = None,
    actor_user_id: Optional[uuid.UUID] = None,
    actor_type: AuditActorType = AuditActorType.USER,
    organization_id: Optional[uuid.UUID] = None,
    site_id: Optional[uuid.UUID] = None,
    station_id: Optional[uuid.UUID] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    audit_metadata: Optional[Dict[str, Any]] = None,
) -> AuditLog:
    """
    Creates and commits an append-only AuditLog entry.
    """
    cleaned_metadata = sanitize_audit_metadata(audit_metadata)
    now_utc = datetime.now(timezone.utc)

    resolved_resource_id = None
    if resource_id:
        if isinstance(resource_id, uuid.UUID):
            resolved_resource_id = resource_id
        elif isinstance(resource_id, str):
            try:
                resolved_resource_id = uuid.UUID(resource_id)
            except Exception:
                resolved_resource_id = None

    audit_entry = AuditLog(
        action=action,
        actor_type=actor_type,
        actor_user_id=actor_user_id,
        organization_id=organization_id,
        site_id=site_id,
        station_id=station_id,
        resource_type=resource_type,
        resource_id=resolved_resource_id,
        action_description=action_description,
        audit_metadata=cleaned_metadata,
        ip_address=ip_address,
        user_agent=user_agent,
        occurred_at=now_utc,
    )
    session.add(audit_entry)
    await session.commit()
    await session.refresh(audit_entry)
    return audit_entry


async def query_audit_logs(
    session: AsyncSession,
    current_user: User,
    organization_id: Optional[uuid.UUID] = None,
    action: Optional[AuditAction] = None,
    resource_type: Optional[str] = None,
    actor_user_id: Optional[uuid.UUID] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[AuditLog]:
    """
    Query audit logs with strict RBAC:
    - SUPER_ADMIN: can view all or filter by organization_id.
    - ORGANIZATION_ADMIN: strictly scoped to current_user.organization_id.
    """
    stmt = select(AuditLog)

    if current_user.role == UserRole.SUPER_ADMIN:
        if organization_id is not None:
            stmt = stmt.where(AuditLog.organization_id == organization_id)
    else:
        # ORGANIZATION_ADMIN
        if current_user.organization_id is None:
            return []
        stmt = stmt.where(AuditLog.organization_id == current_user.organization_id)

    if action is not None:
        stmt = stmt.where(AuditLog.action == action)
    if resource_type is not None:
        stmt = stmt.where(AuditLog.resource_type == resource_type)
    if actor_user_id is not None:
        stmt = stmt.where(AuditLog.actor_user_id == actor_user_id)
    if start_time is not None:
        stmt = stmt.where(AuditLog.occurred_at >= start_time)
    if end_time is not None:
        stmt = stmt.where(AuditLog.occurred_at <= end_time)

    stmt = stmt.order_by(AuditLog.occurred_at.desc(), AuditLog.id.desc())
    stmt = stmt.limit(limit).offset(offset)

    res = await session.execute(stmt)
    return res.scalars().all()
