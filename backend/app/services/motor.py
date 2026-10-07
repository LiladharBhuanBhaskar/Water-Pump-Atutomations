import uuid
from typing import Sequence, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, and_

from app.models.motor import Motor, MotorStatus, MotorType
from app.models.controller import Controller
from app.models.station import Station
from app.models.site import Site
from app.models.motor_command import MotorCommand
from app.models.motor_event import MotorEvent
from app.models.automation_rule import AutomationRule
from app.schemas.motor import MotorCreate, MotorUpdate

class MotorCodeAlreadyExistsException(Exception):
    pass

class MotorNotFoundException(Exception):
    pass

class MotorHasDependentResourcesException(Exception):
    pass


async def create_motor(
    session: AsyncSession,
    req: MotorCreate,
    target_controller_id: uuid.UUID
) -> Motor:
    code = req.motor_code.strip().upper()
    name = req.name.strip()

    # Check composite uniqueness on (controller_id, motor_code)
    stmt = select(Motor).where(
        and_(
            Motor.controller_id == target_controller_id,
            Motor.motor_code == code
        )
    )
    res = await session.execute(stmt)
    if res.scalar_one_or_none() is not None:
        raise MotorCodeAlreadyExistsException(f"Motor code '{code}' already exists in this controller.")

    motor = Motor(
        id=uuid.uuid4(),
        controller_id=target_controller_id,
        name=name,
        motor_code=code,
        motor_type=req.motor_type or MotorType.WATER_PUMP,
        status=req.status or MotorStatus.OFFLINE,
        rated_power=req.rated_power,
        description=req.description.strip() if req.description else None
    )
    session.add(motor)
    await session.commit()
    await session.refresh(motor)
    return motor


async def get_motor_by_id(session: AsyncSession, motor_id: uuid.UUID) -> Optional[Motor]:
    stmt = select(Motor).where(Motor.id == motor_id)
    res = await session.execute(stmt)
    return res.scalar_one_or_none()


async def list_motors_for_org_or_controller(
    session: AsyncSession,
    organization_id: Optional[uuid.UUID] = None,
    controller_id: Optional[uuid.UUID] = None
) -> Sequence[Motor]:
    stmt = (
        select(Motor)
        .join(Controller, Motor.controller_id == Controller.id)
        .join(Station, Controller.station_id == Station.id)
        .join(Site, Station.site_id == Site.id)
    )
    
    if organization_id is not None:
        stmt = stmt.where(Site.organization_id == organization_id)
    if controller_id is not None:
        stmt = stmt.where(Motor.controller_id == controller_id)

    stmt = stmt.order_by(Motor.created_at.desc())
    res = await session.execute(stmt)
    return res.scalars().all()


async def update_motor(
    session: AsyncSession,
    motor: Motor,
    req: MotorUpdate
) -> Motor:
    if req.motor_code is not None:
        new_code = req.motor_code.strip().upper()
        if new_code != motor.motor_code:
            stmt = select(Motor).where(
                and_(
                    Motor.controller_id == motor.controller_id,
                    Motor.motor_code == new_code
                )
            )
            res = await session.execute(stmt)
            if res.scalar_one_or_none() is not None:
                raise MotorCodeAlreadyExistsException(f"Motor code '{new_code}' already exists in this controller.")
            motor.motor_code = new_code

    if req.name is not None:
        motor.name = req.name.strip()

    if req.motor_type is not None:
        motor.motor_type = req.motor_type

    if req.status is not None:
        motor.status = req.status

    if req.rated_power is not None:
        motor.rated_power = req.rated_power

    if req.description is not None:
        motor.description = req.description.strip() if req.description else None

    session.add(motor)
    await session.commit()
    await session.refresh(motor)
    return motor


async def delete_motor(session: AsyncSession, motor: Motor) -> None:
    # Check if dependent commands, events, or automation rules exist
    stmt_cmd = select(func.count(MotorCommand.id)).where(MotorCommand.motor_id == motor.id)
    res_cmd = await session.execute(stmt_cmd)
    cmd_count = res_cmd.scalar() or 0

    stmt_evt = select(func.count(MotorEvent.id)).where(MotorEvent.motor_id == motor.id)
    res_evt = await session.execute(stmt_evt)
    evt_count = res_evt.scalar() or 0

    stmt_rule = select(func.count(AutomationRule.id)).where(AutomationRule.motor_id == motor.id)
    res_rule = await session.execute(stmt_rule)
    rule_count = res_rule.scalar() or 0

    if cmd_count > 0 or evt_count > 0 or rule_count > 0:
        raise MotorHasDependentResourcesException("Cannot delete motor with active commands, events, or automation rules.")

    await session.delete(motor)
    await session.commit()
