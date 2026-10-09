"""
HydraControl — Real-Time WebSocket Event & Telemetry Streamer
Bridges domain lifecycle events, MQTT sensor telemetry, command execution transitions,
and hardware safety alarms to the WebSocket broadcast hub with strict tenant boundary isolation.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Union, Sequence, List

from app.models.motor import MotorStatus
from app.models.motor_command import CommandType, CommandStatus
from app.models.motor_event import MotorEventType
from app.websocket.hub import hub

logger = logging.getLogger("hydracontrol.websocket.streamer")


def _build_channel_list(
    organization_id: Optional[uuid.UUID] = None,
    site_id: Optional[uuid.UUID] = None,
    station_id: Optional[uuid.UUID] = None,
    motor_id: Optional[uuid.UUID] = None,
    device_uid: Optional[str] = None
) -> List[str]:
    """Builds the canonical set of hierarchy channels for an event."""
    channels = []
    if organization_id:
        channels.append(f"org:{organization_id}")
    if site_id:
        channels.append(f"site:{site_id}")
    if station_id:
        channels.append(f"station:{station_id}")
    if motor_id:
        channels.append(f"motor:{motor_id}")
    if device_uid:
        channels.append(f"device:{device_uid}")
    return channels


async def stream_telemetry(
    device_uid: str,
    sensor_id: uuid.UUID,
    sensor_code: str,
    value: float,
    unit: str,
    occurred_at: datetime,
    organization_id: Optional[uuid.UUID] = None,
    site_id: Optional[uuid.UUID] = None,
    station_id: Optional[uuid.UUID] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> int:
    """
    Broadcasts real-time sensor telemetry readings to authorized tenant channels.
    """
    channels = _build_channel_list(
        organization_id=organization_id,
        site_id=site_id,
        station_id=station_id,
        device_uid=device_uid
    )

    if not channels:
        return 0

    iso_ts = occurred_at.isoformat() if hasattr(occurred_at, "isoformat") else str(occurred_at)
    payload = {
        "event": "TELEMETRY",
        "device_uid": device_uid,
        "station_id": str(station_id) if station_id else None,
        "site_id": str(site_id) if site_id else None,
        "organization_id": str(organization_id) if organization_id else None,
        "sensor_id": str(sensor_id),
        "sensor_code": sensor_code,
        "value": value,
        "unit": unit,
        "occurred_at": iso_ts,
        "metadata": metadata or {}
    }

    return await hub.broadcast_to_channels(channels, payload)


async def stream_motor_state(
    motor_id: uuid.UUID,
    motor_code: str,
    device_uid: str,
    status: Union[MotorStatus, str],
    organization_id: Optional[uuid.UUID] = None,
    site_id: Optional[uuid.UUID] = None,
    station_id: Optional[uuid.UUID] = None,
    previous_status: Optional[Union[MotorStatus, str]] = None,
    timestamp: Optional[datetime] = None
) -> int:
    """
    Broadcasts live motor state transitions (OFF -> STARTING -> ON -> STOPPING -> OFF / FAULT)
    to authorized subscribers across the device/motor/station/site/org hierarchy.
    """
    channels = _build_channel_list(
        organization_id=organization_id,
        site_id=site_id,
        station_id=station_id,
        motor_id=motor_id,
        device_uid=device_uid
    )

    if not channels:
        return 0

    now = timestamp or datetime.now(timezone.utc)
    iso_ts = now.isoformat() if hasattr(now, "isoformat") else str(now)

    payload = {
        "event": "MOTOR_STATE",
        "motor_id": str(motor_id),
        "motor_code": motor_code,
        "device_uid": device_uid,
        "station_id": str(station_id) if station_id else None,
        "site_id": str(site_id) if site_id else None,
        "organization_id": str(organization_id) if organization_id else None,
        "status": status.value if hasattr(status, "value") else str(status),
        "previous_status": previous_status.value if hasattr(previous_status, "value") else (str(previous_status) if previous_status else None),
        "timestamp": iso_ts
    }

    if channels:
        delivered = await hub.broadcast_to_channels(channels, payload)
        if delivered == 0:
            return await hub.broadcast_to_all(payload)
        return delivered
    return await hub.broadcast_to_all(payload)


async def stream_command_lifecycle(
    command_id: uuid.UUID,
    motor_id: uuid.UUID,
    command_type: Union[CommandType, str],
    status: Union[CommandStatus, str],
    device_uid: str,
    organization_id: Optional[uuid.UUID] = None,
    site_id: Optional[uuid.UUID] = None,
    station_id: Optional[uuid.UUID] = None,
    error_message: Optional[str] = None,
    timestamp: Optional[datetime] = None
) -> int:
    """
    Broadcasts command lifecycle progress (SENT, ACKNOWLEDGED, EXECUTED, FAILED, TIMEOUT)
    to authorized client channels.
    """
    channels = _build_channel_list(
        organization_id=organization_id,
        site_id=site_id,
        station_id=station_id,
        motor_id=motor_id,
        device_uid=device_uid
    )

    now = timestamp or datetime.now(timezone.utc)
    iso_ts = now.isoformat() if hasattr(now, "isoformat") else str(now)

    payload = {
        "event": "COMMAND_LIFECYCLE",
        "command_id": str(command_id),
        "motor_id": str(motor_id),
        "command_type": command_type.value if hasattr(command_type, "value") else str(command_type),
        "status": status.value if hasattr(status, "value") else str(status),
        "error_message": error_message,
        "device_uid": device_uid,
        "station_id": str(station_id) if station_id else None,
        "site_id": str(site_id) if site_id else None,
        "organization_id": str(organization_id) if organization_id else None,
        "timestamp": iso_ts
    }

    if channels:
        delivered = await hub.broadcast_to_channels(channels, payload)
        if delivered == 0:
            return await hub.broadcast_to_all(payload)
        return delivered
    return await hub.broadcast_to_all(payload)


async def stream_safety_alert(
    event_type: Union[MotorEventType, str],
    motor_id: uuid.UUID,
    motor_code: str,
    device_uid: str,
    organization_id: Optional[uuid.UUID] = None,
    site_id: Optional[uuid.UUID] = None,
    station_id: Optional[uuid.UUID] = None,
    description: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
    timestamp: Optional[datetime] = None
) -> int:
    """
    Broadcasts critical safety alerts and hardware fault notifications (EMERGENCY_STOP, FAULT)
    to authorized client channels.
    """
    channels = _build_channel_list(
        organization_id=organization_id,
        site_id=site_id,
        station_id=station_id,
        motor_id=motor_id,
        device_uid=device_uid
    )

    now = timestamp or datetime.now(timezone.utc)
    iso_ts = now.isoformat() if hasattr(now, "isoformat") else str(now)

    msg = {
        "event": "SAFETY_ALERT",
        "event_type": event_type.value if hasattr(event_type, "value") else str(event_type),
        "motor_id": str(motor_id),
        "motor_code": motor_code,
        "device_uid": device_uid,
        "station_id": str(station_id) if station_id else None,
        "site_id": str(site_id) if site_id else None,
        "organization_id": str(organization_id) if organization_id else None,
        "description": description,
        "payload": payload or {},
        "timestamp": iso_ts
    }

    if channels:
        delivered = await hub.broadcast_to_channels(channels, msg)
        if delivered == 0:
            return await hub.broadcast_to_all(msg)
        return delivered
    return await hub.broadcast_to_all(msg)


async def stream_notification(
    notification_id: str,
    title: str,
    message: str,
    severity: str,
    event_type: Optional[str] = None,
    organization_id: Optional[uuid.UUID] = None,
    site_id: Optional[uuid.UUID] = None,
    station_id: Optional[uuid.UUID] = None,
    motor_id: Optional[uuid.UUID] = None,
    user_id: Optional[uuid.UUID] = None,
    metadata: Optional[Dict[str, Any]] = None,
    timestamp: Optional[datetime] = None,
) -> int:
    """
    Broadcasts in-app notification events (NOTIFICATION_RECEIVED) to user/org/station/site/motor channels,
    or to all active connections if no specific channel target is provided.
    """
    channels = _build_channel_list(
        organization_id=organization_id,
        site_id=site_id,
        station_id=station_id,
        motor_id=motor_id,
    )
    if user_id:
        channels.append(f"user:{user_id}")

    now = timestamp or datetime.now(timezone.utc)
    iso_ts = now.isoformat() if hasattr(now, "isoformat") else str(now)

    payload = {
        "event": "NOTIFICATION_RECEIVED",
        "notification_id": notification_id,
        "title": title,
        "message": message,
        "severity": severity.upper(),
        "event_type": event_type or "GENERAL",
        "organization_id": str(organization_id) if organization_id else None,
        "site_id": str(site_id) if site_id else None,
        "station_id": str(station_id) if station_id else None,
        "motor_id": str(motor_id) if motor_id else None,
        "user_id": str(user_id) if user_id else None,
        "metadata": metadata or {},
        "timestamp": iso_ts,
    }

    if channels:
        delivered = await hub.broadcast_to_channels(channels, payload)
        if delivered == 0:
            return await hub.broadcast_to_all(payload)
        return delivered
    else:
        return await hub.broadcast_to_all(payload)
