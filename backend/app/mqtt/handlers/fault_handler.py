"""
HydraControl — Inbound MQTT Fault & Safety Event Handler
Processes emergency stops, sensor fault trips, and hardware alarms, records MotorEvent records,
and transitions affected motor state to FAULT.
"""

import uuid
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.db.session import AsyncSessionLocal
from app.models.controller import Controller, ControllerStatus
from app.models.station import Station
from app.models.site import Site
from app.models.motor import Motor, MotorStatus
from app.models.motor_event import MotorEvent, MotorEventType, MotorEventSource
from app.mqtt.router import mqtt_router, ROOT_PREFIX, SHORT_PREFIX
from app.websocket.streamer import stream_safety_alert, stream_motor_state
from app.services.motor_state_engine import (
    transition_motor_state,
    parse_payload_timestamp,
    is_stale_message,
    ensure_utc,
    MotorStateEvent
)

logger = logging.getLogger("hydracontrol.mqtt.handlers.fault")


async def process_fault_payload(device_uid: str, payload: Any) -> Optional[MotorEvent]:
    """
    Process fault or emergency stop event reported by a controller.
    Validates anti-spoofing and stale timestamps, evaluates state engine transitions,
    records a MotorEvent entry, updates motor status,
    and broadcasts safety/fault alerts and motor states over WebSocket.
    """
    if not isinstance(payload, dict):
        logger.warning(f"Invalid non-dict fault payload from device '{device_uid}': {payload}")
        return None

    payload_now = parse_payload_timestamp(payload)
    now = datetime.now(timezone.utc)

    motor_code = str(payload.get("motor_code", "")).strip().upper()
    fault_type_str = str(payload.get("fault_type", "FAULT")).strip().upper()
    description = payload.get("description") or payload.get("message") or "Hardware safety trip"
    event_payload = payload.get("event_payload") or payload.get("payload")
    if event_payload is not None and not isinstance(event_payload, dict):
        event_payload = {"raw": event_payload}

    async with AsyncSessionLocal() as session:
        stmt = (
            select(Controller)
            .options(
                selectinload(Controller.motors),
                selectinload(Controller.station).selectinload(Station.site)
            )
            .where(Controller.device_uid == device_uid)
        )
        res = await session.execute(stmt)
        controller = res.scalar_one_or_none()

        if controller is None:
            logger.warning(f"Rejected fault report from unknown device '{device_uid}'")
            return None

        last_seen_utc = ensure_utc(controller.last_seen_at)
        # Stale message protection
        if is_stale_message(payload_now, last_seen_utc, tolerance_seconds=2.0):
            logger.warning(f"Stale fault payload from device '{device_uid}' ignored.")
            return None

        station_id = controller.station_id if controller.station else None
        site_id = controller.station.site_id if (controller.station and controller.station.site) else None
        org_id = controller.station.site.organization_id if (controller.station and controller.station.site) else None

        controller.last_seen_at = max(last_seen_utc or payload_now, payload_now)
        session.add(controller)

        target_motor: Optional[Motor] = None
        if motor_code:
            for m in controller.motors:
                if m.motor_code.upper() == motor_code:
                    target_motor = m
                    break
        elif controller.motors:
            # Default to first motor if motor_code was omitted
            target_motor = controller.motors[0]

        if target_motor is None:
            logger.warning(f"Fault event on controller '{device_uid}' could not resolve motor '{motor_code}'")
            return None

        old_status = target_motor.status

        # Evaluate state transition via motor state engine
        if "EMERGENCY" in fault_type_str or "ESTOP" in fault_type_str:
            state_event = MotorStateEvent.LOCAL_ESTOP
        elif "RESET" in fault_type_str:
            state_event = MotorStateEvent.CMD_RESET
        else:
            state_event = MotorStateEvent.SAFETY_TRIP

        trans_res = transition_motor_state(
            current_state=old_status,
            event=state_event,
            context={"error_message": description}
        )

        if trans_res.is_valid:
            target_motor.status = trans_res.next_state
            session.add(target_motor)

        event_type = trans_res.event_type or MotorEventType.FAULT

        event = MotorEvent(
            id=uuid.uuid4(),
            motor_id=target_motor.id,
            event_type=event_type,
            source=MotorEventSource.CONTROLLER,
            occurred_at=payload_now,
            event_payload=event_payload,
            description=str(description)[:500]
        )
        session.add(event)
        await session.commit()
        await session.refresh(event)
        logger.warning(f"Recorded {event_type.value} event for motor '{target_motor.motor_code}' ({target_motor.id}) on device '{device_uid}'")

        try:
            if event_type in (MotorEventType.FAULT, MotorEventType.EMERGENCY_STOP):
                await stream_safety_alert(
                    event_type=event_type,
                    motor_id=target_motor.id,
                    motor_code=target_motor.motor_code,
                    device_uid=device_uid,
                    organization_id=org_id,
                    site_id=site_id,
                    station_id=station_id,
                    description=event.description,
                    payload=event_payload,
                    timestamp=payload_now
                )

            if target_motor.status != old_status:
                await stream_motor_state(
                    motor_id=target_motor.id,
                    motor_code=target_motor.motor_code,
                    device_uid=device_uid,
                    status=target_motor.status,
                    organization_id=org_id,
                    site_id=site_id,
                    station_id=station_id,
                    previous_status=old_status,
                    timestamp=payload_now
                )
        except Exception as e:
            logger.error(f"Error streaming safety alert for '{device_uid}': {e}")

        return event


@mqtt_router.route(f"{ROOT_PREFIX}/{{device_uid}}/fault")
@mqtt_router.route(f"{SHORT_PREFIX}/{{device_uid}}/fault")
async def handle_device_fault(device_uid: str, payload: Any, **kwargs):
    """MQTT Route handler for device/motor safety fault events."""
    await process_fault_payload(device_uid, payload)

