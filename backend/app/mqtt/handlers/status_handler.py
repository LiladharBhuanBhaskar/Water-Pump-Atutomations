import uuid
import logging
from typing import Dict, Any, List, Optional
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
from app.websocket.streamer import stream_motor_state, stream_safety_alert
from app.services.motor_state_engine import (
    transition_motor_state,
    parse_payload_timestamp,
    is_stale_message,
    ensure_utc,
    MotorStateEvent
)

logger = logging.getLogger("hydracontrol.mqtt.handlers.status")


async def process_status_payload(device_uid: str, payload: Any) -> bool:
    """
    Process status report from a controller containing controller and motor operational states.
    Applies stale-message protection, evaluates deterministic motor state engine transitions,
    creates MotorEvent records on state transitions, and broadcasts real-time motor state to WebSocket subscribers.
    """
    if not isinstance(payload, dict):
        logger.warning(f"Invalid non-dict status payload from device '{device_uid}': {payload}")
        return False

    payload_now = parse_payload_timestamp(payload)

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
            logger.warning(f"Rejected status update from unprovisioned device '{device_uid}'")
            return False

        if controller.status == ControllerStatus.DECOMMISSIONED:
            return False

        last_seen_utc = ensure_utc(controller.last_seen_at)

        # Stale message defense: reject older status payloads that could regress state
        if is_stale_message(payload_now, last_seen_utc, tolerance_seconds=2.0):
            logger.warning(
                f"Stale status payload from device '{device_uid}' ignored. "
                f"Payload time ({payload_now.isoformat()}) is older than last seen ({last_seen_utc.isoformat()})."
            )
            return False

        station_id = controller.station_id if controller.station else None
        site_id = controller.station.site_id if (controller.station and controller.station.site) else None
        org_id = controller.station.site.organization_id if (controller.station and controller.station.site) else None

        controller_was_offline = (controller.status == ControllerStatus.OFFLINE)
        controller.last_seen_at = max(last_seen_utc or payload_now, payload_now)

        # Update controller status if provided
        ctrl_status_str = payload.get("controller_status") or payload.get("status")
        if ctrl_status_str and hasattr(ControllerStatus, str(ctrl_status_str).upper()):
            c_st = ControllerStatus(str(ctrl_status_str).upper())
            if c_st != ControllerStatus.DECOMMISSIONED:
                controller.status = c_st
        elif controller_was_offline:
            controller.status = ControllerStatus.ACTIVE

        session.add(controller)

        motor_transitions = []

        # Update motor statuses if provided
        motors_payload = payload.get("motors")
        if isinstance(motors_payload, list):
            motors_by_code: Dict[str, Motor] = {m.motor_code.upper(): m for m in controller.motors}
            for m_item in motors_payload:
                if not isinstance(m_item, dict):
                    continue
                m_code = str(m_item.get("motor_code", "")).strip().upper()
                m_stat_str = str(m_item.get("status", "")).strip().upper()
                if m_code in motors_by_code:
                    motor = motors_by_code[m_code]
                    old_status = motor.status

                    # Map reported hardware status to MotorStateEvent
                    event_map = {
                        "ON": MotorStateEvent.STATUS_ON,
                        "OFF": MotorStateEvent.STATUS_OFF,
                        "STARTING": MotorStateEvent.STATUS_STARTING,
                        "STOPPING": MotorStateEvent.STATUS_STOPPING,
                        "FAULT": MotorStateEvent.SAFETY_TRIP,
                        "OFFLINE": MotorStateEvent.HEARTBEAT_TIMEOUT,
                    }
                    state_event = event_map.get(m_stat_str)

                    if state_event is None:
                        logger.warning(f"Unrecognized status '{m_stat_str}' for motor '{m_code}' on device '{device_uid}'")
                        continue

                    # Status report from physical controller is authoritative hardware status sync
                    ctx = {
                        "is_reconciliation": True,
                        "hardware_state": m_stat_str,
                        "error_message": m_item.get("fault_reason") or m_item.get("description")
                    }

                    # If reconnecting from OFFLINE, evaluate HEARTBEAT_RESTORED
                    if old_status == MotorStatus.OFFLINE:
                        trans_res = transition_motor_state(old_status, MotorStateEvent.HEARTBEAT_RESTORED, ctx)
                    else:
                        trans_res = transition_motor_state(old_status, state_event, ctx)

                    if trans_res.is_valid and trans_res.next_state != old_status:
                        motor.status = trans_res.next_state
                        session.add(motor)

                        # Create MotorEvent for state transitions
                        if trans_res.event_type is not None:
                            event = MotorEvent(
                                id=uuid.uuid4(),
                                motor_id=motor.id,
                                event_type=trans_res.event_type,
                                source=MotorEventSource.CONTROLLER,
                                occurred_at=payload_now,
                                event_payload=m_item,
                                description=trans_res.reason
                            )
                            session.add(event)

                        motor_transitions.append({
                            "motor_id": motor.id,
                            "motor_code": motor.motor_code,
                            "status": trans_res.next_state,
                            "previous_status": old_status,
                            "event_type": trans_res.event_type,
                            "description": trans_res.reason,
                            "payload": m_item
                        })

        await session.commit()
        logger.info(f"Processed state sync for controller '{device_uid}'")

        # Broadcast motor state transitions to WebSocket clients
        for mt in motor_transitions:
            try:
                if mt.get("event_type") in (MotorEventType.FAULT, MotorEventType.EMERGENCY_STOP):
                    await stream_safety_alert(
                        event_type=mt["event_type"],
                        motor_id=mt["motor_id"],
                        motor_code=mt["motor_code"],
                        device_uid=device_uid,
                        organization_id=org_id,
                        site_id=site_id,
                        station_id=station_id,
                        description=mt.get("description"),
                        payload=mt.get("payload"),
                        timestamp=payload_now
                    )

                await stream_motor_state(
                    motor_id=mt["motor_id"],
                    motor_code=mt["motor_code"],
                    device_uid=device_uid,
                    status=mt["status"],
                    organization_id=org_id,
                    site_id=site_id,
                    station_id=station_id,
                    previous_status=mt["previous_status"],
                    timestamp=payload_now
                )
            except Exception as e:
                logger.error(f"Error streaming motor state for '{mt['motor_code']}': {e}")

        return True


@mqtt_router.route(f"{ROOT_PREFIX}/{{device_uid}}/status")
@mqtt_router.route(f"{SHORT_PREFIX}/{{device_uid}}/status")
async def handle_device_status(device_uid: str, payload: Any, **kwargs):
    """MQTT Route handler for device and motor status synchronization."""
    await process_status_payload(device_uid, payload)

