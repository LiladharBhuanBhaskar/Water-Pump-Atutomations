import uuid
from typing import Sequence, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, and_

from app.models.controller import Controller, ControllerStatus, ControllerType
from app.models.station import Station
from app.models.site import Site
from app.models.motor import Motor
from app.models.sensor import Sensor
from app.schemas.controller import ControllerCreate, ControllerUpdate

class ControllerCodeAlreadyExistsException(Exception):
    pass

class ControllerDeviceUidAlreadyExistsException(Exception):
    pass

class ControllerNotFoundException(Exception):
    pass

class ControllerHasDependentResourcesException(Exception):
    pass


async def create_controller(
    session: AsyncSession,
    req: ControllerCreate,
    target_station_id: uuid.UUID
) -> Controller:
    code = req.controller_code.strip().upper()
    device_uid = req.device_uid.strip()
    name = req.name.strip()

    # Check global device_uid uniqueness
    stmt_uid = select(Controller).where(Controller.device_uid == device_uid)
    res_uid = await session.execute(stmt_uid)
    if res_uid.scalar_one_or_none() is not None:
        raise ControllerDeviceUidAlreadyExistsException(f"Controller with device UID '{device_uid}' already exists.")

    # Check composite uniqueness on (station_id, controller_code)
    stmt_code = select(Controller).where(
        and_(
            Controller.station_id == target_station_id,
            Controller.controller_code == code
        )
    )
    res_code = await session.execute(stmt_code)
    if res_code.scalar_one_or_none() is not None:
        raise ControllerCodeAlreadyExistsException(f"Controller code '{code}' already exists in this station.")

    controller = Controller(
        id=uuid.uuid4(),
        station_id=target_station_id,
        name=name,
        controller_code=code,
        device_uid=device_uid,
        controller_type=req.controller_type or ControllerType.ESP32,
        status=req.status or ControllerStatus.ACTIVE,
        firmware_version=req.firmware_version.strip() if req.firmware_version else None,
        ip_address=req.ip_address.strip() if req.ip_address else None,
        mac_address=req.mac_address.strip() if req.mac_address else None,
        description=req.description.strip() if req.description else None
    )
    session.add(controller)
    await session.commit()
    await session.refresh(controller)
    return controller


async def get_controller_by_id(session: AsyncSession, controller_id: uuid.UUID) -> Optional[Controller]:
    stmt = select(Controller).where(Controller.id == controller_id)
    res = await session.execute(stmt)
    return res.scalar_one_or_none()


async def list_controllers_for_org_or_station(
    session: AsyncSession,
    organization_id: Optional[uuid.UUID] = None,
    station_id: Optional[uuid.UUID] = None
) -> Sequence[Controller]:
    stmt = (
        select(Controller)
        .join(Station, Controller.station_id == Station.id)
        .join(Site, Station.site_id == Site.id)
    )
    
    if organization_id is not None:
        stmt = stmt.where(Site.organization_id == organization_id)
    if station_id is not None:
        stmt = stmt.where(Controller.station_id == station_id)

    stmt = stmt.order_by(Controller.created_at.desc())
    res = await session.execute(stmt)
    return res.scalars().all()


async def update_controller(
    session: AsyncSession,
    controller: Controller,
    req: ControllerUpdate
) -> Controller:
    if req.device_uid is not None:
        new_uid = req.device_uid.strip()
        if new_uid != controller.device_uid:
            stmt = select(Controller).where(Controller.device_uid == new_uid)
            res = await session.execute(stmt)
            if res.scalar_one_or_none() is not None:
                raise ControllerDeviceUidAlreadyExistsException(f"Controller with device UID '{new_uid}' already exists.")
            controller.device_uid = new_uid

    if req.controller_code is not None:
        new_code = req.controller_code.strip().upper()
        if new_code != controller.controller_code:
            stmt = select(Controller).where(
                and_(
                    Controller.station_id == controller.station_id,
                    Controller.controller_code == new_code
                )
            )
            res = await session.execute(stmt)
            if res.scalar_one_or_none() is not None:
                raise ControllerCodeAlreadyExistsException(f"Controller code '{new_code}' already exists in this station.")
            controller.controller_code = new_code

    if req.name is not None:
        controller.name = req.name.strip()

    if req.controller_type is not None:
        controller.controller_type = req.controller_type

    if req.status is not None:
        controller.status = req.status

    if req.firmware_version is not None:
        controller.firmware_version = req.firmware_version.strip() if req.firmware_version else None

    if req.ip_address is not None:
        controller.ip_address = req.ip_address.strip() if req.ip_address else None

    if req.mac_address is not None:
        controller.mac_address = req.mac_address.strip() if req.mac_address else None

    if req.description is not None:
        controller.description = req.description.strip() if req.description else None

    session.add(controller)
    await session.commit()
    await session.refresh(controller)
    return controller


async def delete_controller(session: AsyncSession, controller: Controller) -> None:
    # Check if dependent motors or sensors exist
    stmt_motor = select(func.count(Motor.id)).where(Motor.controller_id == controller.id)
    res_motor = await session.execute(stmt_motor)
    motor_count = res_motor.scalar() or 0

    stmt_sensor = select(func.count(Sensor.id)).where(Sensor.controller_id == controller.id)
    res_sensor = await session.execute(stmt_sensor)
    sensor_count = res_sensor.scalar() or 0

    if motor_count > 0 or sensor_count > 0:
        raise ControllerHasDependentResourcesException("Cannot delete controller with active motors or sensors.")

    await session.delete(controller)
    await session.commit()
