"""
HydraControl — Fleet Management API (Phase 20).
Provides multi-site enterprise fleet summary endpoints.
"""

import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.api.deps import get_current_user
from app.models.user import User, UserRole
from app.schemas.fleet import OrganizationFleetSummary
from app.services.fleet_service import get_organization_fleet_summary

router = APIRouter(tags=["Fleet"])


@router.get("/organizations/{organization_id}/fleet-summary", response_model=OrganizationFleetSummary)
async def get_org_fleet_summary(
    organization_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Retrieve comprehensive multi-site fleet operational status and fault rollup for an organization.
    Restricted to SUPER_ADMIN and users belonging to the requested organization.
    """
    summary = await get_organization_fleet_summary(session, organization_id, current_user)
    if summary is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found or access denied.",
        )
    return summary
