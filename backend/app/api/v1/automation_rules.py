"""API endpoints for AutomationRules (Phase 12 - Wave 2A)."""

import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.api.deps import get_current_user, require_roles
from app.models.user import User, UserRole
from app.models.automation_rule import AutomationRuleStatus
from app.schemas.automation_rule import (
    AutomationRuleCreate,
    AutomationRuleUpdate,
    AutomationRuleResponse,
)
from app.services.automation_rule import (
    get_automation_rule_by_id,
    list_automation_rules_for_station,
    create_automation_rule,
    update_automation_rule,
    delete_automation_rule,
)
from app.services.station_settings import verify_station_tenant_access
from app.services.site_auth import validate_site_access_policy

router = APIRouter(tags=["Automation Rules"])


@router.get("", response_model=List[AutomationRuleResponse])
async def list_automation_rules_endpoint(
    station_id: uuid.UUID = Query(..., description="Target station ID"),
    rule_status: Optional[AutomationRuleStatus] = Query(None, alias="status"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """List automation rules for a station with tenant scoping."""
    station = await verify_station_tenant_access(session, station_id, current_user)
    if station is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Station not found",
        )

    validate_site_access_policy(station.site, current_user)
    rules = await list_automation_rules_for_station(session, station_id, status=rule_status)
    return rules


@router.post("", response_model=AutomationRuleResponse, status_code=status.HTTP_201_CREATED)
async def create_automation_rule_endpoint(
    req: AutomationRuleCreate,
    current_user: User = Depends(require_roles([UserRole.SUPER_ADMIN, UserRole.ORGANIZATION_ADMIN, UserRole.SITE_MANAGER])),
    session: AsyncSession = Depends(get_db),
):
    """Create an automation rule for a station."""
    station = await verify_station_tenant_access(session, req.station_id, current_user)
    if station is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Station not found",
        )

    validate_site_access_policy(station.site, current_user)
    rule = await create_automation_rule(session, req, creator_id=current_user.id)
    return rule


@router.put("/{rule_id}", response_model=AutomationRuleResponse)
async def update_automation_rule_endpoint(
    rule_id: uuid.UUID,
    req: AutomationRuleUpdate,
    current_user: User = Depends(require_roles([UserRole.SUPER_ADMIN, UserRole.ORGANIZATION_ADMIN, UserRole.SITE_MANAGER])),
    session: AsyncSession = Depends(get_db),
):
    """Update an automation rule."""
    rule = await get_automation_rule_by_id(session, rule_id)
    if rule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Automation rule not found",
        )

    station = await verify_station_tenant_access(session, rule.station_id, current_user)
    if station is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Automation rule not found",
        )

    validate_site_access_policy(station.site, current_user)
    updated_rule = await update_automation_rule(session, rule, req)
    return updated_rule


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_automation_rule_endpoint(
    rule_id: uuid.UUID,
    current_user: User = Depends(require_roles([UserRole.SUPER_ADMIN, UserRole.ORGANIZATION_ADMIN, UserRole.SITE_MANAGER])),
    session: AsyncSession = Depends(get_db),
):
    """Delete an automation rule."""
    rule = await get_automation_rule_by_id(session, rule_id)
    if rule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Automation rule not found",
        )

    station = await verify_station_tenant_access(session, rule.station_id, current_user)
    if station is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Automation rule not found",
        )

    validate_site_access_policy(station.site, current_user)
    await delete_automation_rule(session, rule)
