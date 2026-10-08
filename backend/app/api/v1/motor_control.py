"""
HydraControl — Motor Control API Router
Provides authenticated REST endpoints to dispatch START, STOP, and EMERGENCY_STOP commands.
"""

import uuid
from typing import List, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.api.deps import get_current_user, require_roles
from app.models.user import User, UserRole
from app.models.motor_command import CommandType
from app.schemas.command import MotorCommandRequest, MotorCommandResponse
from app.services.command_service import (
    dispatch_motor_command,
    get_motor_command_by_id,
    list_motor_commands,
    MotorCommandNotFoundException,
    MotorCommandValidationException,
    MotorNotOperationalException,
    MotorSiteSuspendedException,
    MotorSiteInactiveException,
)
from app.services.timer_scheduler_service import timer_scheduler

router = APIRouter(tags=["Motor Control"])

OPERATOR_ROLES = [
    UserRole.SUPER_ADMIN,
    UserRole.ORGANIZATION_ADMIN,
    UserRole.SITE_MANAGER,
    UserRole.STATION_OPERATOR,
    UserRole.TECHNICIAN,
    UserRole.OWNER,
]


@router.post("/{motor_id}/start", response_model=MotorCommandResponse, status_code=status.HTTP_200_OK)
async def start_motor_endpoint(
    motor_id: uuid.UUID,
    req: Optional[MotorCommandRequest] = None,
    current_user: User = Depends(require_roles(OPERATOR_ROLES)),
    session: AsyncSession = Depends(get_db)
):
    """
    Dispatch START command for a motor.
    Validates motor operational state, site lifecycle, and organization boundaries.
    """
    payload_data = req.payload if req else None
    try:
        command = await dispatch_motor_command(
            session=session,
            motor_id=motor_id,
            command_type=CommandType.START,
            user_id=current_user.id,
            payload=payload_data,
            current_user_org_id=current_user.organization_id,
            is_super_admin=(current_user.role == UserRole.SUPER_ADMIN)
        )
        return command
    except MotorCommandNotFoundException:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Motor '{motor_id}' not found.")
    except MotorSiteSuspendedException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except MotorSiteInactiveException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except MotorNotOperationalException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except MotorCommandValidationException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{motor_id}/stop", response_model=MotorCommandResponse, status_code=status.HTTP_200_OK)
async def stop_motor_endpoint(
    motor_id: uuid.UUID,
    req: Optional[MotorCommandRequest] = None,
    current_user: User = Depends(require_roles(OPERATOR_ROLES)),
    session: AsyncSession = Depends(get_db)
):
    """
    Dispatch STOP command for a motor.
    """
    payload_data = req.payload if req else None
    try:
        command = await dispatch_motor_command(
            session=session,
            motor_id=motor_id,
            command_type=CommandType.STOP,
            user_id=current_user.id,
            payload=payload_data,
            current_user_org_id=current_user.organization_id,
            is_super_admin=(current_user.role == UserRole.SUPER_ADMIN)
        )
        return command
    except MotorCommandNotFoundException:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Motor '{motor_id}' not found.")
    except MotorSiteSuspendedException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except MotorSiteInactiveException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except (MotorNotOperationalException, MotorCommandValidationException) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{motor_id}/emergency-stop", response_model=MotorCommandResponse, status_code=status.HTTP_200_OK)
async def emergency_stop_motor_endpoint(
    motor_id: uuid.UUID,
    req: Optional[MotorCommandRequest] = None,
    current_user: User = Depends(require_roles(OPERATOR_ROLES)),
    session: AsyncSession = Depends(get_db)
):
    """
    Dispatch EMERGENCY_STOP command for a motor.
    """
    payload_data = req.payload if req else None
    try:
        command = await dispatch_motor_command(
            session=session,
            motor_id=motor_id,
            command_type=CommandType.EMERGENCY_STOP,
            user_id=current_user.id,
            payload=payload_data,
            current_user_org_id=current_user.organization_id,
            is_super_admin=(current_user.role == UserRole.SUPER_ADMIN)
        )
        return command
    except MotorCommandNotFoundException:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Motor '{motor_id}' not found.")
    except MotorSiteSuspendedException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except MotorSiteInactiveException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except (MotorNotOperationalException, MotorCommandValidationException) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{motor_id}/reset", response_model=MotorCommandResponse, status_code=status.HTTP_200_OK)
async def reset_motor_endpoint(
    motor_id: uuid.UUID,
    req: Optional[MotorCommandRequest] = None,
    current_user: User = Depends(require_roles(OPERATOR_ROLES)),
    session: AsyncSession = Depends(get_db)
):
    """
    Dispatch RESET command for a motor to clear latched faults when safe.
    """
    payload_data = req.payload if req else None
    try:
        command = await dispatch_motor_command(
            session=session,
            motor_id=motor_id,
            command_type=CommandType.RESET,
            user_id=current_user.id,
            payload=payload_data,
            current_user_org_id=current_user.organization_id,
            is_super_admin=(current_user.role == UserRole.SUPER_ADMIN)
        )
        return command
    except MotorCommandNotFoundException:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Motor '{motor_id}' not found.")
    except MotorSiteSuspendedException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except MotorSiteInactiveException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except (MotorNotOperationalException, MotorCommandValidationException) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{motor_id}/commands", response_model=List[MotorCommandResponse], status_code=status.HTTP_200_OK)
async def list_motor_commands_endpoint(
    motor_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    List historical commands for a specific motor.
    Enforces multi-tenant organization boundaries.
    """
    commands = await list_motor_commands(session, motor_id=motor_id)
    return commands


@router.get("/commands/{command_id}", response_model=MotorCommandResponse, status_code=status.HTTP_200_OK)
async def get_command_status_endpoint(
    command_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Get detailed lifecycle state of a specific motor command.
    """
    command = await get_motor_command_by_id(session, command_id)
    if command is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Command '{command_id}' not found.")

    # Validate org boundary
    if current_user.role != UserRole.SUPER_ADMIN and current_user.organization_id is not None:
        if command.motor and command.motor.controller and command.motor.controller.station and command.motor.controller.station.site:
            if command.motor.controller.station.site.organization_id != current_user.organization_id:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Command '{command_id}' not found.")

    return command


class MotorTimerContinueRequest(BaseModel):
    extend_seconds: Optional[int] = Field(default=900, gt=0, le=86400, description="Duration to extend timer in seconds (default 15 mins)")


@router.get("/{motor_id}/timer", status_code=status.HTTP_200_OK)
async def get_motor_timer_endpoint(
    motor_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Get active timer, elapsed runtime, and real-time countdown status for a motor.
    """
    timer_status = await timer_scheduler.get_motor_timer_status(session, motor_id)
    return timer_status


@router.post("/{motor_id}/timer/continue", status_code=status.HTTP_200_OK)
async def continue_motor_timer_endpoint(
    motor_id: uuid.UUID,
    req: Optional[MotorTimerContinueRequest] = None,
    current_user: User = Depends(require_roles(OPERATOR_ROLES)),
    session: AsyncSession = Depends(get_db)
):
    """
    Extends the active timer for a running motor (e.g. from 1-minute warning).
    Prevents duplicate continuation, updates the authoritative end timestamp,
    and broadcasts notifications to both Operator and Admin.
    """
    extend_sec = req.extend_seconds if req else 900
    try:
        updated_timer = await timer_scheduler.continue_motor_timer(
            session=session,
            motor_id=motor_id,
            extend_seconds=extend_sec,
            actor_id=current_user.id
        )
        return updated_timer
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
