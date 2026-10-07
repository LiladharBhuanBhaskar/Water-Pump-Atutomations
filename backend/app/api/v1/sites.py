import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.api.deps import get_current_user, require_roles
from app.models.user import User, UserRole
from app.models.site import Site
from app.schemas.site import SiteCreate, SiteUpdate, SiteResponse
from app.services.site import (
    create_site,
    get_site_by_id,
    list_sites_for_org,
    update_site,
    delete_site,
    SiteAlreadyExistsException,
    SiteHasDependentStationsException
)
from app.services.site_auth import validate_site_access_policy
from app.services.tenant import get_org_scoped_resource

router = APIRouter(tags=["Sites"])

@router.post("", response_model=SiteResponse, status_code=status.HTTP_201_CREATED)
async def create_site_endpoint(
    req: SiteCreate,
    current_user: User = Depends(require_roles([UserRole.SUPER_ADMIN, UserRole.ORGANIZATION_ADMIN, UserRole.SITE_MANAGER])),
    session: AsyncSession = Depends(get_db)
):
    """
    Create a new site scoped to an organization.
    Restricted to SUPER_ADMIN, ORGANIZATION_ADMIN, SITE_MANAGER.
    Non-SUPER_ADMIN users automatically create sites in their own organization.
    """
    if current_user.role == UserRole.SUPER_ADMIN:
        target_org_id = req.organization_id or current_user.organization_id
        if target_org_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="organization_id is required for SUPER_ADMIN when user has no organization_id"
            )
    else:
        if current_user.organization_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User does not belong to any organization"
            )
        target_org_id = current_user.organization_id

    try:
        site = await create_site(session, req, target_org_id)
        return site
    except SiteAlreadyExistsException as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )

@router.get("", response_model=List[SiteResponse])
async def list_sites_endpoint(
    organization_id: Optional[uuid.UUID] = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    List sites.
    SUPER_ADMIN can list all sites or filter by organization_id.
    Non-SUPER_ADMIN users only receive sites for their authenticated organization.
    """
    if current_user.role == UserRole.SUPER_ADMIN:
        return await list_sites_for_org(session, organization_id=organization_id)

    if current_user.organization_id is None:
        return []

    return await list_sites_for_org(session, organization_id=current_user.organization_id)

@router.get("/{site_id}", response_model=SiteResponse)
async def get_site_endpoint(
    site_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Retrieve a site by ID.
    Enforces Organization Tenant Isolation (returns 404 for foreign sites) and Site Operational Status Policy (403 for inactive/suspended/maintenance).
    """
    if current_user.role == UserRole.SUPER_ADMIN:
        site = await get_site_by_id(session, site_id)
    else:
        if current_user.organization_id is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
        site = await get_org_scoped_resource(session, Site, site_id, current_user.organization_id)

    if site is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Site not found"
        )

    validate_site_access_policy(site, current_user)
    return site

@router.put("/{site_id}", response_model=SiteResponse)
@router.patch("/{site_id}", response_model=SiteResponse)
async def update_site_endpoint(
    site_id: uuid.UUID,
    req: SiteUpdate,
    current_user: User = Depends(require_roles([UserRole.SUPER_ADMIN, UserRole.ORGANIZATION_ADMIN, UserRole.SITE_MANAGER])),
    session: AsyncSession = Depends(get_db)
):
    """
    Update a site.
    Restricted to SUPER_ADMIN, ORGANIZATION_ADMIN, SITE_MANAGER.
    Non-SUPER_ADMIN can only update sites within their own organization.
    """
    if current_user.role == UserRole.SUPER_ADMIN:
        site = await get_site_by_id(session, site_id)
    else:
        if current_user.organization_id is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
        site = await get_org_scoped_resource(session, Site, site_id, current_user.organization_id)

    if site is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Site not found"
        )

    try:
        updated_site = await update_site(session, site, req)
        return updated_site
    except SiteAlreadyExistsException as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )

@router.delete("/{site_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_site_endpoint(
    site_id: uuid.UUID,
    current_user: User = Depends(require_roles([UserRole.SUPER_ADMIN, UserRole.ORGANIZATION_ADMIN])),
    session: AsyncSession = Depends(get_db)
):
    """
    Delete a site.
    Restricted to SUPER_ADMIN or ORGANIZATION_ADMIN.
    Fails if dependent stations exist (HTTP 400).
    """
    if current_user.role == UserRole.SUPER_ADMIN:
        site = await get_site_by_id(session, site_id)
    else:
        if current_user.organization_id is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
        site = await get_org_scoped_resource(session, Site, site_id, current_user.organization_id)

    if site is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Site not found"
        )

    try:
        await delete_site(session, site)
    except SiteHasDependentStationsException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
