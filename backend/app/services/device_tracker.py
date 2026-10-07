import uuid
from typing import Optional, Tuple, Dict, Any, Sequence
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

try:
    from app.models.controller import Controller, ControllerStatus, ControllerType
    from app.models.station import Station
    from app.models.site import Site, SiteStatus
    from app.schemas.device import (
        DeviceRegistrationRequest,
        DeviceHeartbeatRequest,
        LivenessState,
    )
    from app.core.security import create_device_token
except ImportError:
    from backend.app.models.controller import Controller, ControllerStatus, ControllerType
    from backend.app.models.station import Station
    from backend.app.models.site import Site, SiteStatus
    from backend.app.schemas.device import (
        DeviceRegistrationRequest,
        DeviceHeartbeatRequest,
        LivenessState,
    )
    from backend.app.core.security import create_device_token


class DeviceNotProvisionedException(Exception):
    """Raised when an unregistered/unknown device UID attempts to connect or heartbeat."""
    pass


class DeviceSiteSuspendedException(Exception):
    """Raised when device's site or organization is suspended."""
    pass


class DeviceDecommissionedException(Exception):
    """Raised when device has been permanently decommissioned."""
    pass


DEFAULT_STALE_THRESHOLD_SECONDS = 60
DEFAULT_OFFLINE_THRESHOLD_SECONDS = 180


def calculate_liveness_state(
    controller: Controller,
    now: Optional[datetime] = None,
    stale_threshold_seconds: int = DEFAULT_STALE_THRESHOLD_SECONDS,
    offline_threshold_seconds: int = DEFAULT_OFFLINE_THRESHOLD_SECONDS
) -> Tuple[LivenessState, Optional[float]]:
    """
    Calculate the dynamic liveness state of a controller based on last_seen_at.
    ONLINE: last_seen_at within stale_threshold_seconds.
    STALE: last_seen_at between stale_threshold_seconds and offline_threshold_seconds.
    OFFLINE: last_seen_at older than offline_threshold_seconds or never seen.
    DECOMMISSIONED: controller has been decommissioned.
    """
    if controller.status == ControllerStatus.DECOMMISSIONED:
        return LivenessState.DECOMMISSIONED, None

    if controller.last_seen_at is None:
        return LivenessState.OFFLINE, None

    if now is None:
        now = datetime.now(timezone.utc)

    # Ensure timezone awareness for comparison
    last_seen = controller.last_seen_at
    if last_seen.tzinfo is None:
        last_seen = last_seen.replace(tzinfo=timezone.utc)

    diff_seconds = max(0.0, (now - last_seen).total_seconds())

    if diff_seconds <= stale_threshold_seconds:
        return LivenessState.ONLINE, diff_seconds
    elif diff_seconds <= offline_threshold_seconds:
        return LivenessState.STALE, diff_seconds
    else:
        return LivenessState.OFFLINE, diff_seconds


async def register_device(
    session: AsyncSession,
    req: DeviceRegistrationRequest
) -> Tuple[Controller, str]:
    """
    Provision/register a physical controller device with the backend.
    Updates firmware, IP, MAC, last_seen_at, and transitions OFFLINE/INACTIVE to ACTIVE.
    Generates and returns a signed device JWT token.
    """
    device_uid = req.device_uid.strip()

    stmt = (
        select(Controller)
        .options(selectinload(Controller.station).selectinload(Station.site))
        .where(Controller.device_uid == device_uid)
    )
    res = await session.execute(stmt)
    controller = res.scalar_one_or_none()

    if controller is None:
        raise DeviceNotProvisionedException(f"Device UID '{device_uid}' is not provisioned.")

    # Check site operational state
    if controller.station and controller.station.site:
        if controller.station.site.status == SiteStatus.SUSPENDED:
            raise DeviceSiteSuspendedException(f"Parent site of device '{device_uid}' is suspended.")

    if controller.status == ControllerStatus.DECOMMISSIONED:
        raise DeviceDecommissionedException(f"Device '{device_uid}' is decommissioned.")

    # Update metadata
    now = datetime.now(timezone.utc)
    controller.last_seen_at = now

    if req.firmware_version is not None:
        controller.firmware_version = req.firmware_version.strip()
    if req.ip_address is not None:
        controller.ip_address = req.ip_address.strip()
    if req.mac_address is not None:
        controller.mac_address = req.mac_address.strip()
    if req.controller_type is not None:
        controller.controller_type = req.controller_type

    # Transition to ACTIVE if currently OFFLINE or INACTIVE
    if controller.status in (ControllerStatus.OFFLINE, ControllerStatus.INACTIVE):
        controller.status = ControllerStatus.ACTIVE

    session.add(controller)
    await session.commit()
    await session.refresh(controller)

    # Issue device JWT token
    token = create_device_token(
        device_uid=controller.device_uid,
        controller_id=controller.id,
        extra_claims={
            "station_id": str(controller.station_id),
            "site_id": str(controller.station.site_id) if controller.station else None,
        }
    )

    return controller, token


async def record_heartbeat(
    session: AsyncSession,
    req: DeviceHeartbeatRequest
) -> Controller:
    """
    Process periodic heartbeat telemetry from a controller.
    Updates last_seen_at timestamp and network/firmware parameters.
    Transitions OFFLINE status back to ACTIVE if applicable.
    """
    device_uid = req.device_uid.strip()

    stmt = (
        select(Controller)
        .options(selectinload(Controller.station).selectinload(Station.site))
        .where(Controller.device_uid == device_uid)
    )
    res = await session.execute(stmt)
    controller = res.scalar_one_or_none()

    if controller is None:
        raise DeviceNotProvisionedException(f"Device UID '{device_uid}' is not provisioned.")

    if controller.station and controller.station.site:
        if controller.station.site.status == SiteStatus.SUSPENDED:
            raise DeviceSiteSuspendedException(f"Parent site of device '{device_uid}' is suspended.")

    if controller.status == ControllerStatus.DECOMMISSIONED:
        raise DeviceDecommissionedException(f"Device '{device_uid}' is decommissioned.")

    now = datetime.now(timezone.utc)
    controller.last_seen_at = now

    if req.firmware_version is not None:
        controller.firmware_version = req.firmware_version.strip()
    if req.ip_address is not None:
        controller.ip_address = req.ip_address.strip()
    if req.status is not None and req.status != ControllerStatus.DECOMMISSIONED:
        controller.status = req.status
    elif controller.status == ControllerStatus.OFFLINE:
        controller.status = ControllerStatus.ACTIVE

    session.add(controller)
    await session.commit()
    await session.refresh(controller)
    return controller


async def get_device_liveness(
    session: AsyncSession,
    device_uid: str,
    stale_threshold_seconds: int = DEFAULT_STALE_THRESHOLD_SECONDS,
    offline_threshold_seconds: int = DEFAULT_OFFLINE_THRESHOLD_SECONDS
) -> Tuple[Controller, LivenessState, Optional[float]]:
    """
    Retrieve controller and calculate its real-time liveness.
    """
    stmt = (
        select(Controller)
        .options(selectinload(Controller.station).selectinload(Station.site))
        .where(Controller.device_uid == device_uid.strip())
    )
    res = await session.execute(stmt)
    controller = res.scalar_one_or_none()

    if controller is None:
        raise DeviceNotProvisionedException(f"Device UID '{device_uid}' is not provisioned.")

    state, diff = calculate_liveness_state(
        controller=controller,
        stale_threshold_seconds=stale_threshold_seconds,
        offline_threshold_seconds=offline_threshold_seconds
    )
    return controller, state, diff


async def sync_device_liveness(
    session: AsyncSession,
    stale_threshold_seconds: int = DEFAULT_STALE_THRESHOLD_SECONDS,
    offline_threshold_seconds: int = DEFAULT_OFFLINE_THRESHOLD_SECONDS
) -> Dict[str, Any]:
    """
    Background liveness check service.
    Scans all controllers and updates ACTIVE/STALE controllers to OFFLINE if last_seen_at > offline_threshold.
    Returns counts of online, stale, offline, and updated controllers.
    """
    now = datetime.now(timezone.utc)
    stmt = select(Controller).where(Controller.status != ControllerStatus.DECOMMISSIONED)
    res = await session.execute(stmt)
    controllers: Sequence[Controller] = res.scalars().all()

    online_count = 0
    stale_count = 0
    offline_count = 0
    transitioned_to_offline = 0

    for controller in controllers:
        state, _ = calculate_liveness_state(
            controller=controller,
            now=now,
            stale_threshold_seconds=stale_threshold_seconds,
            offline_threshold_seconds=offline_threshold_seconds
        )

        if state == LivenessState.ONLINE:
            online_count += 1
        elif state == LivenessState.STALE:
            stale_count += 1
        elif state == LivenessState.OFFLINE:
            offline_count += 1
            if controller.status == ControllerStatus.ACTIVE:
                controller.status = ControllerStatus.OFFLINE
                session.add(controller)
                transitioned_to_offline += 1

    if transitioned_to_offline > 0:
        await session.commit()

    return {
        "checked_at": now.isoformat(),
        "total_checked": len(controllers),
        "online_count": online_count,
        "stale_count": stale_count,
        "offline_count": offline_count,
        "transitioned_to_offline": transitioned_to_offline,
    }
