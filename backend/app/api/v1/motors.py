import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.session import get_db
from app.api.deps import get_current_user, require_roles
from app.models.user import User, UserRole
from app.models.controller import Controller
from app.models.motor import Motor
from app.schemas.motor import MotorCreate, MotorUpdate, MotorResponse
from app.services.motor import (
    create_motor,
    get_motor_by_id,
    list_motors_for_org_or_controller,
    update_motor,
    delete_motor,
    MotorCodeAlreadyExistsException,
    MotorHasDependentResourcesException
)
from app.services.site_auth import validate_site_access_policy
from app.services.tenant import get_org_scoped_resource

router = APIRouter(tags=["Motors"])

@router.post("", response_model=MotorResponse, status_code=status.HTTP_201_CREATED)
async def create_motor_endpoint(
    req: MotorCreate,
    current_user: User = Depends(require_roles([UserRole.SUPER_ADMIN, UserRole.ORGANIZATION_ADMIN, UserRole.SITE_MANAGER])),
    session: AsyncSession = Depends(get_db)
):
    """
    Create a new motor under a controller.
    Restricted to SUPER_ADMIN, ORGANIZATION_ADMIN, SITE_MANAGER.
    Non-SUPER_ADMIN users can only create motors under controllers belonging to their authenticated organization.
    """
    if current_user.role == UserRole.SUPER_ADMIN:
        controller = await get_controller_by_id_internal(session, req.controller_id)
    else:
        if current_user.organization_id is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Controller not found")
        controller = await get_org_scoped_resource(session, Controller, req.controller_id, current_user.organization_id)

    if controller is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Controller not found"
        )

    validate_site_access_policy(controller.station.site, current_user)

    try:
        motor = await create_motor(session, req, req.controller_id)
        return motor
    except MotorCodeAlreadyExistsException as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )


async def get_controller_by_id_internal(session: AsyncSession, controller_id: uuid.UUID) -> Optional[Controller]:
    stmt = select(Controller).where(Controller.id == controller_id)
    res = await session.execute(stmt)
    return res.scalar_one_or_none()


@router.get("", response_model=List[MotorResponse])
async def list_motors_endpoint(
    controller_id: Optional[uuid.UUID] = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    List motors.
    SUPER_ADMIN can list all motors or filter by controller_id.
    Non-SUPER_ADMIN users only receive motors belonging to their authenticated organization.
    """
    if current_user.role == UserRole.SUPER_ADMIN:
        return await list_motors_for_org_or_controller(session, organization_id=None, controller_id=controller_id)

    if current_user.organization_id is None:
        return []

    if controller_id is not None:
        controller = await get_org_scoped_resource(session, Controller, controller_id, current_user.organization_id)
        if controller is None:
            return []

    return await list_motors_for_org_or_controller(session, organization_id=current_user.organization_id, controller_id=controller_id)


@router.get("/{motor_id}", response_model=MotorResponse)
async def get_motor_endpoint(
    motor_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Retrieve a motor by ID.
    Enforces Organization Tenant Isolation and Parent Site Operational Policy.
    """
    if current_user.role == UserRole.SUPER_ADMIN:
        motor = await get_motor_by_id(session, motor_id)
    else:
        if current_user.organization_id is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Motor not found")
        motor = await get_org_scoped_resource(session, Motor, motor_id, current_user.organization_id)

    if motor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Motor not found"
        )

    validate_site_access_policy(motor.controller.station.site, current_user)
    return motor


@router.put("/{motor_id}", response_model=MotorResponse)
@router.patch("/{motor_id}", response_model=MotorResponse)
async def update_motor_endpoint(
    motor_id: uuid.UUID,
    req: MotorUpdate,
    current_user: User = Depends(require_roles([UserRole.SUPER_ADMIN, UserRole.ORGANIZATION_ADMIN, UserRole.SITE_MANAGER])),
    session: AsyncSession = Depends(get_db)
):
    """
    Update a motor.
    Restricted to SUPER_ADMIN, ORGANIZATION_ADMIN, SITE_MANAGER.
    """
    if current_user.role == UserRole.SUPER_ADMIN:
        motor = await get_motor_by_id(session, motor_id)
    else:
        if current_user.organization_id is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Motor not found")
        motor = await get_org_scoped_resource(session, Motor, motor_id, current_user.organization_id)

    if motor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Motor not found"
        )

    validate_site_access_policy(motor.controller.station.site, current_user)

    try:
        updated_motor = await update_motor(session, motor, req)
        return updated_motor
    except MotorCodeAlreadyExistsException as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )


@router.delete("/{motor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_motor_endpoint(
    motor_id: uuid.UUID,
    current_user: User = Depends(require_roles([UserRole.SUPER_ADMIN, UserRole.ORGANIZATION_ADMIN])),
    session: AsyncSession = Depends(get_db)
):
    """
    Delete a motor.
    Restricted to SUPER_ADMIN or ORGANIZATION_ADMIN.
    Fails if dependent commands, events, or automation rules exist (HTTP 400).
    """
    if current_user.role == UserRole.SUPER_ADMIN:
        motor = await get_motor_by_id(session, motor_id)
    else:
        if current_user.organization_id is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Motor not found")
        motor = await get_org_scoped_resource(session, Motor, motor_id, current_user.organization_id)

    if motor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Motor not found"
        )

    try:
        await delete_motor(session, motor)
    except MotorHasDependentResourcesException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# ==========================================
# Motor Diagnostics (Phase 14 & 15 - Wave 2B)
# ==========================================
from app.schemas.diagnostics import FlowDiagnosticsResponse, ElectricalMetricsResponse
from app.services.diagnostics_service import (
    get_motor_flow_diagnostics,
    get_motor_electrical_metrics,
    verify_motor_tenant_access,
)


@router.get("/{motor_id}/flow-diagnostics", response_model=FlowDiagnosticsResponse)
async def get_motor_flow_diagnostics_endpoint(
    motor_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Get flow telemetry diagnostics, grace period status, and dry-run evaluation for a motor.
    Enforces multi-tenant isolation and site policy.
    """
    motor = await verify_motor_tenant_access(session, motor_id, current_user)
    if motor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Motor not found",
        )

    validate_site_access_policy(motor.controller.station.site, current_user)
    diagnostics = await get_motor_flow_diagnostics(session, motor)
    return diagnostics


@router.get("/{motor_id}/electrical-metrics", response_model=ElectricalMetricsResponse)
async def get_motor_electrical_metrics_endpoint(
    motor_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Get electrical telemetry (Current, Voltage), power estimation, load %, and electrical safety evaluation.
    Enforces multi-tenant isolation and site policy.
    """
    motor = await verify_motor_tenant_access(session, motor_id, current_user)
    if motor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Motor not found",
        )

    validate_site_access_policy(motor.controller.station.site, current_user)
    metrics = await get_motor_electrical_metrics(session, motor)
    return metrics

