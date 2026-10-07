"""
API endpoints for Audit Logs (Phase 19 - Wave A).
"""

import uuid
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.api.deps import get_current_user, require_roles
from app.models.user import User, UserRole
from app.models.audit_log import AuditAction
from app.schemas.audit_log import AuditLogResponse
from app.services.audit_service import query_audit_logs

router = APIRouter(tags=["Audit Logs"])


@router.get("/audit-logs", response_model=List[AuditLogResponse])
async def get_audit_logs_endpoint(
    organization_id: Optional[uuid.UUID] = None,
    action: Optional[AuditAction] = None,
    resource_type: Optional[str] = None,
    actor_user_id: Optional[uuid.UUID] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_roles([UserRole.SUPER_ADMIN, UserRole.ORGANIZATION_ADMIN])),
    session: AsyncSession = Depends(get_db),
):
    """
    Retrieve paginated, immutable audit logs.
    Restricted to SUPER_ADMIN (global or filtered by org) and ORGANIZATION_ADMIN (own organization only).
    """
    if start_time and end_time and start_time > end_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_time must be before end_time.",
        )

    logs = await query_audit_logs(
        session=session,
        current_user=current_user,
        organization_id=organization_id,
        action=action,
        resource_type=resource_type,
        actor_user_id=actor_user_id,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        offset=offset,
    )
    return logs
