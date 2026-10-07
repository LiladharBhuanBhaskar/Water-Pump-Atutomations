import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.api.deps import get_current_user, require_roles
from app.models.user import User, UserRole
from app.schemas.organization import OrganizationCreate, OrganizationUpdate, OrganizationResponse
from app.services.organization import (
    create_organization,
    get_organization,
    list_organizations,
    update_organization,
    delete_organization,
    OrganizationAlreadyExistsException,
    OrganizationHasDependentSitesException
)

router = APIRouter(tags=["Organizations"])

@router.post("", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
async def create_org(
    req: OrganizationCreate,
    current_user: User = Depends(require_roles([UserRole.SUPER_ADMIN])),
    session: AsyncSession = Depends(get_db)
):
    """
    Create a new organization.
    Restricted to SUPER_ADMIN.
    """
    try:
        org = await create_organization(session, req)
        return org
    except OrganizationAlreadyExistsException as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )

@router.get("", response_model=List[OrganizationResponse])
async def list_orgs(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    List organizations.
    SUPER_ADMIN sees all organizations across the platform.
    Non-SUPER_ADMIN users only see their authenticated organization (Tenant Isolation).
    """
    if current_user.role == UserRole.SUPER_ADMIN:
        return await list_organizations(session)
    
    if current_user.organization_id is None:
        return []

    org = await get_organization(session, current_user.organization_id)
    return [org] if org else []

@router.get("/{organization_id}", response_model=OrganizationResponse)
async def get_org(
    organization_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Retrieve an organization by ID.
    SUPER_ADMIN can access any organization.
    Non-SUPER_ADMIN users can only access their own organization.
    Accessing another tenant's organization ID returns 404 Not Found (IDOR defense).
    """
    if current_user.role != UserRole.SUPER_ADMIN:
        if current_user.organization_id != organization_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found"
            )

    org = await get_organization(session, organization_id)
    if org is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )
    return org

@router.put("/{organization_id}", response_model=OrganizationResponse)
@router.patch("/{organization_id}", response_model=OrganizationResponse)
async def update_org(
    organization_id: uuid.UUID,
    req: OrganizationUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Update organization details.
    SUPER_ADMIN can update any organization.
    ORGANIZATION_ADMIN can update their own organization.
    All other roles are forbidden (403 Forbidden).
    Cross-organization attempts by ORGANIZATION_ADMIN return 404 Not Found (IDOR defense).
    """
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.ORGANIZATION_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )

    if current_user.role != UserRole.SUPER_ADMIN:
        if current_user.organization_id != organization_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found"
            )

    org = await get_organization(session, organization_id)
    if org is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )

    try:
        updated_org = await update_organization(session, org, req)
        return updated_org
    except OrganizationAlreadyExistsException as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )

@router.delete("/{organization_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_org(
    organization_id: uuid.UUID,
    current_user: User = Depends(require_roles([UserRole.SUPER_ADMIN])),
    session: AsyncSession = Depends(get_db)
):
    """
    Delete an organization.
    Restricted strictly to SUPER_ADMIN.
    Fails if dependent sites exist.
    """
    org = await get_organization(session, organization_id)
    if org is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )

    try:
        await delete_organization(session, org)
    except OrganizationHasDependentSitesException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
