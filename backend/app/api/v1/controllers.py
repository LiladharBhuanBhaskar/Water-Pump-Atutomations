import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.session import get_db
from app.api.deps import get_current_user, require_roles
from app.models.user import User, UserRole
from app.models.station import Station
from app.models.controller import Controller
from app.schemas.controller import ControllerCreate, ControllerUpdate, ControllerResponse
from app.services.controller import (
    create_controller,
    get_controller_by_id,
    list_controllers_for_org_or_station,
    update_controller,
    delete_controller,
    ControllerCodeAlreadyExistsException,
    ControllerDeviceUidAlreadyExistsException,
    ControllerHasDependentResourcesException
)
from app.services.site_auth import validate_site_access_policy
from app.services.tenant import get_org_scoped_resource

router = APIRouter(tags=["Controllers"])

@router.post("", response_model=ControllerResponse, status_code=status.HTTP_201_CREATED)
async def create_controller_endpoint(
    req: ControllerCreate,
    current_user: User = Depends(require_roles([UserRole.SUPER_ADMIN, UserRole.ORGANIZATION_ADMIN, UserRole.SITE_MANAGER])),
    session: AsyncSession = Depends(get_db)
):
    """
    Create a new controller inside a station.
    Restricted to SUPER_ADMIN, ORGANIZATION_ADMIN, SITE_MANAGER.
    Non-SUPER_ADMIN users can only create controllers inside stations belonging to their authenticated organization.
    """
    if current_user.role == UserRole.SUPER_ADMIN:
        station = await get_station_by_id_internal(session, req.station_id)
    else:
        if current_user.organization_id is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Station not found")
        station = await get_org_scoped_resource(session, Station, req.station_id, current_user.organization_id)

    if station is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Station not found"
        )

    validate_site_access_policy(station.site, current_user)

    try:
        controller = await create_controller(session, req, req.station_id)
        return controller
    except (ControllerCodeAlreadyExistsException, ControllerDeviceUidAlreadyExistsException) as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )


async def get_station_by_id_internal(session: AsyncSession, station_id: uuid.UUID) -> Optional[Station]:
    stmt = select(Station).where(Station.id == station_id)
    res = await session.execute(stmt)
    return res.scalar_one_or_none()


@router.get("", response_model=List[ControllerResponse])
async def list_controllers_endpoint(
    station_id: Optional[uuid.UUID] = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    List controllers.
    SUPER_ADMIN can list all controllers or filter by station_id.
    Non-SUPER_ADMIN users only receive controllers belonging to their authenticated organization.
    """
    if current_user.role == UserRole.SUPER_ADMIN:
        return await list_controllers_for_org_or_station(session, organization_id=None, station_id=station_id)

    if current_user.organization_id is None:
        return []

    if station_id is not None:
        station = await get_org_scoped_resource(session, Station, station_id, current_user.organization_id)
        if station is None:
            return []

    return await list_controllers_for_org_or_station(session, organization_id=current_user.organization_id, station_id=station_id)


@router.get("/{controller_id}", response_model=ControllerResponse)
async def get_controller_endpoint(
    controller_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Retrieve a controller by ID.
    Enforces Organization Tenant Isolation and Parent Site Operational Policy.
    """
    if current_user.role == UserRole.SUPER_ADMIN:
        controller = await get_controller_by_id(session, controller_id)
    else:
        if current_user.organization_id is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Controller not found")
        controller = await get_org_scoped_resource(session, Controller, controller_id, current_user.organization_id)

    if controller is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Controller not found"
        )

    validate_site_access_policy(controller.station.site, current_user)
    return controller


@router.put("/{controller_id}", response_model=ControllerResponse)
@router.patch("/{controller_id}", response_model=ControllerResponse)
async def update_controller_endpoint(
    controller_id: uuid.UUID,
    req: ControllerUpdate,
    current_user: User = Depends(require_roles([UserRole.SUPER_ADMIN, UserRole.ORGANIZATION_ADMIN, UserRole.SITE_MANAGER])),
    session: AsyncSession = Depends(get_db)
):
    """
    Update a controller.
    Restricted to SUPER_ADMIN, ORGANIZATION_ADMIN, SITE_MANAGER.
    """
    if current_user.role == UserRole.SUPER_ADMIN:
        controller = await get_controller_by_id(session, controller_id)
    else:
        if current_user.organization_id is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Controller not found")
        controller = await get_org_scoped_resource(session, Controller, controller_id, current_user.organization_id)

    if controller is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Controller not found"
        )

    validate_site_access_policy(controller.station.site, current_user)

    try:
        updated_controller = await update_controller(session, controller, req)
        return updated_controller
    except (ControllerCodeAlreadyExistsException, ControllerDeviceUidAlreadyExistsException) as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )


@router.delete("/{controller_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_controller_endpoint(
    controller_id: uuid.UUID,
    current_user: User = Depends(require_roles([UserRole.SUPER_ADMIN, UserRole.ORGANIZATION_ADMIN])),
    session: AsyncSession = Depends(get_db)
):
    """
    Delete a controller.
    Restricted to SUPER_ADMIN or ORGANIZATION_ADMIN.
    Fails if dependent motors or sensors exist (HTTP 400).
    """
    if current_user.role == UserRole.SUPER_ADMIN:
        controller = await get_controller_by_id(session, controller_id)
    else:
        if current_user.organization_id is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Controller not found")
        controller = await get_org_scoped_resource(session, Controller, controller_id, current_user.organization_id)

    if controller is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Controller not found"
        )

    try:
        await delete_controller(session, controller)
    except ControllerHasDependentResourcesException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
