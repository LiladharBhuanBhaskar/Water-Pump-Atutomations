import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.api.deps import get_current_user, require_roles
from app.models.user import User, UserRole
from app.models.site import Site
from app.models.station import Station
from app.schemas.station import StationCreate, StationUpdate, StationResponse
from app.services.station import (
    create_station,
    get_station_by_id,
    list_stations_for_org_or_site,
    update_station,
    delete_station,
    StationAlreadyExistsException,
    StationHasDependentControllersException
)
from app.services.site_auth import validate_site_access_policy
from app.services.tenant import get_org_scoped_resource

router = APIRouter(tags=["Stations"])

@router.post("", response_model=StationResponse, status_code=status.HTTP_201_CREATED)
async def create_station_endpoint(
    req: StationCreate,
    current_user: User = Depends(require_roles([UserRole.SUPER_ADMIN, UserRole.ORGANIZATION_ADMIN, UserRole.SITE_MANAGER])),
    session: AsyncSession = Depends(get_db)
):
    """
    Create a new station inside a site.
    Restricted to SUPER_ADMIN, ORGANIZATION_ADMIN, SITE_MANAGER.
    Non-SUPER_ADMIN users can only create stations inside sites belonging to their authenticated organization.
    """
    if current_user.role == UserRole.SUPER_ADMIN:
        site = await get_site_by_id_internal(session, req.site_id)
    else:
        if current_user.organization_id is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
        site = await get_org_scoped_resource(session, Site, req.site_id, current_user.organization_id)

    if site is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Site not found"
        )

    validate_site_access_policy(site, current_user)

    try:
        station = await create_station(session, req, req.site_id)
        return station
    except StationAlreadyExistsException as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )

async def get_site_by_id_internal(session: AsyncSession, site_id: uuid.UUID) -> Optional[Site]:
    from sqlalchemy.future import select
    stmt = select(Site).where(Site.id == site_id)
    res = await session.execute(stmt)
    return res.scalar_one_or_none()

@router.get("", response_model=List[StationResponse])
async def list_stations_endpoint(
    site_id: Optional[uuid.UUID] = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    List stations.
    SUPER_ADMIN can list all stations or filter by site_id.
    Non-SUPER_ADMIN users only receive stations belonging to their authenticated organization and permitted sites.
    """
    if current_user.role == UserRole.SUPER_ADMIN:
        return await list_stations_for_org_or_site(session, organization_id=None, site_id=site_id)

    if current_user.organization_id is None:
        return []

    if site_id is not None:
        # Verify site belongs to tenant
        site = await get_org_scoped_resource(session, Site, site_id, current_user.organization_id)
        if site is None:
            return []

    return await list_stations_for_org_or_site(session, organization_id=current_user.organization_id, site_id=site_id)

@router.get("/{station_id}", response_model=StationResponse)
async def get_station_endpoint(
    station_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Retrieve a station by ID.
    Enforces Organization Tenant Isolation (returns 404 for foreign stations) and Site Operational Status Policy (403 for restricted statuses).
    """
    if current_user.role == UserRole.SUPER_ADMIN:
        station = await get_station_by_id(session, station_id)
    else:
        if current_user.organization_id is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Station not found")
        station = await get_org_scoped_resource(session, Station, station_id, current_user.organization_id)

    if station is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Station not found"
        )

    # Validate parent site access policy
    validate_site_access_policy(station.site, current_user)
    return station

@router.put("/{station_id}", response_model=StationResponse)
@router.patch("/{station_id}", response_model=StationResponse)
async def update_station_endpoint(
    station_id: uuid.UUID,
    req: StationUpdate,
    current_user: User = Depends(require_roles([UserRole.SUPER_ADMIN, UserRole.ORGANIZATION_ADMIN, UserRole.SITE_MANAGER])),
    session: AsyncSession = Depends(get_db)
):
    """
    Update a station.
    Restricted to SUPER_ADMIN, ORGANIZATION_ADMIN, SITE_MANAGER.
    Non-SUPER_ADMIN can only update stations within their own organization.
    """
    if current_user.role == UserRole.SUPER_ADMIN:
        station = await get_station_by_id(session, station_id)
    else:
        if current_user.organization_id is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Station not found")
        station = await get_org_scoped_resource(session, Station, station_id, current_user.organization_id)

    if station is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Station not found"
        )

    validate_site_access_policy(station.site, current_user)

    try:
        updated_station = await update_station(session, station, req)
        return updated_station
    except StationAlreadyExistsException as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )

@router.delete("/{station_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_station_endpoint(
    station_id: uuid.UUID,
    current_user: User = Depends(require_roles([UserRole.SUPER_ADMIN, UserRole.ORGANIZATION_ADMIN])),
    session: AsyncSession = Depends(get_db)
):
    """
    Delete a station.
    Restricted to SUPER_ADMIN or ORGANIZATION_ADMIN.
    Fails if dependent controllers exist (HTTP 400).
    """
    if current_user.role == UserRole.SUPER_ADMIN:
        station = await get_station_by_id(session, station_id)
    else:
        if current_user.organization_id is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Station not found")
        station = await get_org_scoped_resource(session, Station, station_id, current_user.organization_id)

    if station is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Station not found"
        )

    try:
        await delete_station(session, station)
    except StationHasDependentControllersException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# ==========================================
# Station Settings (Phase 12 - Wave 2A)
# ==========================================
from app.schemas.settings import StationSettingsUpdate, StationSettingsResponse
from app.services.station_settings import (
    get_or_create_station_settings,
    update_station_settings,
    verify_station_tenant_access,
)


@router.get("/{station_id}/settings", response_model=StationSettingsResponse)
async def get_station_settings_endpoint(
    station_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Get settings for a station.
    Enforces multi-tenant isolation and site policy.
    """
    station = await verify_station_tenant_access(session, station_id, current_user)
    if station is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Station not found"
        )

    validate_site_access_policy(station.site, current_user)
    settings = await get_or_create_station_settings(session, station_id, timezone=station.timezone)
    return settings


@router.put("/{station_id}/settings", response_model=StationSettingsResponse)
async def update_station_settings_endpoint(
    station_id: uuid.UUID,
    req: StationSettingsUpdate,
    current_user: User = Depends(require_roles([UserRole.SUPER_ADMIN, UserRole.ORGANIZATION_ADMIN, UserRole.SITE_MANAGER])),
    session: AsyncSession = Depends(get_db)
):
    """
    Update settings for a station.
    Restricted to SUPER_ADMIN, ORGANIZATION_ADMIN, SITE_MANAGER.
    Enforces multi-tenant isolation and site policy.
    """
    station = await verify_station_tenant_access(session, station_id, current_user)
    if station is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Station not found"
        )

    validate_site_access_policy(station.site, current_user)
    updated_settings = await update_station_settings(session, station_id, req)
    return updated_settings


# ==========================================
# Water Quality Diagnostics (Phase 13 - Wave 2B)
# ==========================================
from app.schemas.diagnostics import WaterQualityResponse
from app.services.diagnostics_service import get_station_water_quality_diagnostics


@router.get("/{station_id}/water-quality", response_model=WaterQualityResponse)
async def get_station_water_quality_endpoint(
    station_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Get latest water quality telemetry (Turbidity, pH) and safety assessment for a station.
    Enforces multi-tenant isolation and site policy.
    """
    station = await verify_station_tenant_access(session, station_id, current_user)
    if station is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Station not found",
        )

    validate_site_access_policy(station.site, current_user)
    diagnostics = await get_station_water_quality_diagnostics(session, station_id)
    return diagnostics


