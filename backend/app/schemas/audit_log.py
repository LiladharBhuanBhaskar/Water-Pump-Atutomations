"""Pydantic schemas for AuditLog queries (Phase 19 - Wave A)."""

import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, ConfigDict
from app.models.audit_log import AuditAction, AuditActorType


class AuditLogResponse(BaseModel):
    id: uuid.UUID
    organization_id: Optional[uuid.UUID] = None
    site_id: Optional[uuid.UUID] = None
    station_id: Optional[uuid.UUID] = None
    actor_user_id: Optional[uuid.UUID] = None
    actor_type: AuditActorType
    action: AuditAction
    resource_type: str
    resource_id: Optional[uuid.UUID] = None
    action_description: str
    audit_metadata: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    occurred_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
