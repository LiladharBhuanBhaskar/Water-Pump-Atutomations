import uuid
from typing import Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Header, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.core.security import decode_access_token
from app.api.deps import get_current_user, require_roles
from app.models.user import User, UserRole
from app.schemas.device import (
    DeviceRegistrationRequest,
    DeviceRegistrationResponse,
    DeviceHeartbeatRequest,
    DeviceHeartbeatResponse,
    DeviceLivenessResponse,
)
from app.services.device_tracker import (
    register_device,
    record_heartbeat,
    get_device_liveness,
    sync_device_liveness,
    DeviceNotProvisionedException,
    DeviceSiteSuspendedException,
    DeviceDecommissionedException,
    DEFAULT_STALE_THRESHOLD_SECONDS,
    DEFAULT_OFFLINE_THRESHOLD_SECONDS,
)
from app.services.tenant import build_org_scoped_query
from app.models.controller import Controller
from app.models.station import Station
from app.models.site import Site

router = APIRouter(tags=["Devices"])


@router.post("/register", response_model=DeviceRegistrationResponse, status_code=status.HTTP_200_OK)
async def register_device_endpoint(
    req: DeviceRegistrationRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Device Provisioning & Registration Endpoint.
    Physical IoT devices/gateways call this endpoint on startup to verify provisioning,
    synchronize hardware details, and receive a signed JWT device token and MQTT routing config.
    """
    try:
        controller, device_token = await register_device(db, req)
    except DeviceNotProvisionedException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except DeviceSiteSuspendedException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except DeviceDecommissionedException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    now = datetime.now(timezone.utc)
    return DeviceRegistrationResponse(
        controller_id=controller.id,
        station_id=controller.station_id,
        device_uid=controller.device_uid,
        controller_name=controller.name,
        status=controller.status,
        device_token=device_token,
        server_time=now,
        mqtt_topic_prefix=f"hydracontrol/devices/{controller.device_uid}"
    )


@router.post("/heartbeat", response_model=DeviceHeartbeatResponse, status_code=status.HTTP_200_OK)
async def heartbeat_device_endpoint(
    req: DeviceHeartbeatRequest,
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Device Heartbeat Endpoint.
    Physical IoT controllers post periodic telemetry/heartbeats to maintain online status,
    report diagnostics (uptime, free heap, RSSI), and receive server time & pending command notices.
    """
    # If device token is provided in Authorization header, validate token identity
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
        try:
            payload = decode_access_token(token)
            if payload.get("type") == "device" and payload.get("sub") != req.device_uid:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Token device identity does not match heartbeat device UID."
                )
        except Exception as e:
            if isinstance(e, HTTPException):
                raise e
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid device token.")

    try:
        controller = await record_heartbeat(db, req)
    except DeviceNotProvisionedException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except DeviceSiteSuspendedException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except DeviceDecommissionedException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    now = datetime.now(timezone.utc)
    return DeviceHeartbeatResponse(
        device_uid=controller.device_uid,
        status=controller.status,
        server_time=now,
        acknowledged=True,
        commands_pending=0
    )


@router.get("/{device_uid}/status", response_model=DeviceLivenessResponse, status_code=status.HTTP_200_OK)
async def get_device_status_endpoint(
    device_uid: str,
    stale_threshold: int = Query(DEFAULT_STALE_THRESHOLD_SECONDS, ge=10, le=3600),
    offline_threshold: int = Query(DEFAULT_OFFLINE_THRESHOLD_SECONDS, ge=20, le=7200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve real-time liveness and status for a device.
    Enforces tenant/organization isolation for authenticated users.
    """
    try:
        controller, state, diff = await get_device_liveness(
            session=db,
            device_uid=device_uid,
            stale_threshold_seconds=stale_threshold,
            offline_threshold_seconds=offline_threshold
        )
    except DeviceNotProvisionedException:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Device '{device_uid}' not found.")

    # Organization isolation check
    if current_user.role != UserRole.SUPER_ADMIN:
        # Check if controller belongs to user's org
        if controller.station and controller.station.site:
            if controller.station.site.organization_id != current_user.organization_id:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Device '{device_uid}' not found.")

    return DeviceLivenessResponse(
        controller_id=controller.id,
        station_id=controller.station_id,
        device_uid=controller.device_uid,
        controller_name=controller.name,
        status=controller.status,
        liveness_state=state,
        last_seen_at=controller.last_seen_at,
        seconds_since_last_seen=diff
    )


@router.post("/liveness-check", status_code=status.HTTP_200_OK)
async def trigger_liveness_sync_endpoint(
    stale_threshold: int = Query(DEFAULT_STALE_THRESHOLD_SECONDS, ge=10, le=3600),
    offline_threshold: int = Query(DEFAULT_OFFLINE_THRESHOLD_SECONDS, ge=20, le=7200),
    current_user: User = Depends(require_roles([UserRole.SUPER_ADMIN, UserRole.ORGANIZATION_ADMIN, UserRole.SITE_MANAGER])),
    db: AsyncSession = Depends(get_db)
):
    """
    Trigger liveness evaluation across all controllers.
    Transitions stale/unresponsive controllers to OFFLINE status.
    """
    summary = await sync_device_liveness(
        session=db,
        stale_threshold_seconds=stale_threshold,
        offline_threshold_seconds=offline_threshold
    )
    return summary
