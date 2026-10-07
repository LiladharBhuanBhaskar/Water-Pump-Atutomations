"""
HydraControl — Inbound MQTT Command ACK Handler
Processes command execution acknowledgments from controllers and updates MotorCommand lifecycle states.
"""

import uuid
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.db.session import AsyncSessionLocal
from app.models.controller import Controller
from app.models.station import Station
from app.models.site import Site
from app.models.motor import Motor, MotorStatus
from app.models.motor_command import MotorCommand, CommandType, CommandStatus
from app.models.motor_event import MotorEvent, MotorEventType, MotorEventSource
from app.mqtt.router import mqtt_router, ROOT_PREFIX, SHORT_PREFIX
from app.websocket.streamer import stream_command_lifecycle, stream_motor_state, stream_safety_alert
from app.services.motor_state_engine import (
    transition_motor_state,
    parse_payload_timestamp,
    is_stale_message,
    ensure_utc,
    MotorStateEvent
)

logger = logging.getLogger("hydracontrol.mqtt.handlers.ack")


async def process_ack_payload(device_uid: str, payload: Any) -> Optional[MotorCommand]:
    """
    Process command acknowledgment response from a controller.
    Validates command ownership under controller, updates command state in database,
    drives motor state transitions, creates domain MotorEvents,
    and broadcasts command lifecycle and motor state events over WebSocket.
    Ensures idempotency, stale-message protection, and terminal state preservation.
    """
    if not isinstance(payload, dict):
        logger.warning(f"Invalid non-dict ACK payload from device '{device_uid}': {payload}")
        return None

    raw_command_id = payload.get("command_id")
    if not raw_command_id:
        logger.warning(f"Missing command_id in ACK payload from device '{device_uid}'")
        return None

    try:
        command_id = uuid.UUID(str(raw_command_id))
    except (ValueError, TypeError):
        logger.warning(f"Invalid UUID command_id '{raw_command_id}' in ACK payload")
        return None

    status_str = str(payload.get("status", "ACKNOWLEDGED")).strip().upper()
    error_message = payload.get("error_message") or payload.get("message")
    payload_now = parse_payload_timestamp(payload)
    now = datetime.now(timezone.utc)

    async with AsyncSessionLocal() as session:
        # Fetch command and join motor, controller, station, and site
        stmt = (
            select(MotorCommand)
            .options(
                selectinload(MotorCommand.motor)
                .selectinload(Motor.controller)
                .selectinload(Controller.station)
                .selectinload(Station.site)
            )
            .where(MotorCommand.id == command_id)
        )
        res = await session.execute(stmt)
        command = res.scalar_one_or_none()

        if command is None:
            logger.warning(f"Received ACK for unknown command '{command_id}'")
            return None

        # Verify that the command's motor belongs to this reporting controller (anti-spoofing)
        if command.motor is None or command.motor.controller is None or command.motor.controller.device_uid != device_uid:
            logger.warning(f"Security mismatch: Device '{device_uid}' attempted to ACK command '{command_id}' belonging to another controller.")
            return None

        motor = command.motor
        controller = motor.controller
        last_seen_utc = ensure_utc(controller.last_seen_at)
        controller.last_seen_at = max(last_seen_utc or payload_now, payload_now)
        session.add(controller)

        # Terminal state protection (idempotency)
        terminal_states = {CommandStatus.EXECUTED, CommandStatus.FAILED, CommandStatus.TIMEOUT}

        # Check for stale ACK on already terminal command
        if command.status in terminal_states:
            logger.info(f"Ignoring ACK for already terminal command '{command_id}' (status={command.status.value})")
            return command

        old_motor_status = motor.status
        motor_transition_res = None
        created_event: Optional[MotorEvent] = None

        if status_str in ("ACKNOWLEDGED", "ACK", "RECEIVED"):
            command.status = CommandStatus.ACKNOWLEDGED
            if command.acknowledged_at is None:
                command.acknowledged_at = payload_now

            # Optional pre-transition on ACK receipt
            if command.command_type == CommandType.START and motor.status == MotorStatus.OFF:
                motor_transition_res = transition_motor_state(motor.status, MotorStateEvent.STATUS_STARTING)
                if motor_transition_res.is_valid:
                    motor.status = motor_transition_res.next_state
                    session.add(motor)
            elif command.command_type == CommandType.STOP and motor.status == MotorStatus.ON:
                motor_transition_res = transition_motor_state(motor.status, MotorStateEvent.STATUS_STOPPING)
                if motor_transition_res.is_valid:
                    motor.status = motor_transition_res.next_state
                    session.add(motor)

        elif status_str in ("EXECUTED", "COMPLETED", "SUCCESS"):
            command.status = CommandStatus.EXECUTED
            command.executed_at = payload_now
            if command.acknowledged_at is None:
                command.acknowledged_at = payload_now

            # Execute state transition based on command type
            if command.command_type == CommandType.START:
                motor_transition_res = transition_motor_state(
                    motor.status,
                    MotorStateEvent.STATUS_ON,
                    {"error_message": "Motor confirmed RUNNING (ON) via controller ACK"}
                )
            elif command.command_type == CommandType.STOP:
                motor_transition_res = transition_motor_state(
                    motor.status,
                    MotorStateEvent.STATUS_OFF,
                    {"error_message": "Motor confirmed STOPPED (OFF) via controller ACK"}
                )
            elif command.command_type == CommandType.EMERGENCY_STOP:
                motor_transition_res = transition_motor_state(
                    motor.status,
                    MotorStateEvent.CMD_EMERGENCY_STOP,
                    {"error_message": "Emergency stop executed via controller ACK"}
                )
            elif command.command_type == CommandType.RESET:
                motor_transition_res = transition_motor_state(
                    motor.status,
                    MotorStateEvent.CMD_RESET,
                    {"error_message": "Fault reset confirmed via controller ACK"}
                )

            if motor_transition_res and motor_transition_res.is_valid:
                motor.status = motor_transition_res.next_state
                session.add(motor)
                if motor_transition_res.event_type is not None:
                    created_event = MotorEvent(
                        id=uuid.uuid4(),
                        motor_id=motor.id,
                        event_type=motor_transition_res.event_type,
                        source=MotorEventSource.CONTROLLER,
                        occurred_at=payload_now,
                        event_payload=payload,
                        description=motor_transition_res.reason
                    )
                    session.add(created_event)

        elif status_str in ("FAILED", "REJECTED", "ERROR"):
            command.status = CommandStatus.FAILED
            command.failed_at = payload_now
            if error_message:
                command.error_message = str(error_message)[:1000]

            err_lower = str(error_message or "").lower()
            is_safety_trip = any(k in err_lower for k in ("safety", "turbidity", "tank", "fault", "estop", "trip", "latch"))

            if command.command_type == CommandType.START:
                if is_safety_trip:
                    motor_transition_res = transition_motor_state(
                        motor.status,
                        MotorStateEvent.SAFETY_TRIP,
                        {"error_message": error_message or "Startup rejected due to active safety condition."}
                    )
                else:
                    motor_transition_res = transition_motor_state(
                        motor.status,
                        MotorStateEvent.STARTUP_FAILED,
                        {"error_message": error_message or "Motor startup sequence failed."}
                    )
            elif command.command_type == CommandType.STOP:
                if motor.status == MotorStatus.STOPPING:
                    motor_transition_res = transition_motor_state(
                        motor.status,
                        MotorStateEvent.SHUTDOWN_FAILED,
                        {"error_message": error_message or "Motor shutdown sequence failed."}
                    )

            if motor_transition_res and motor_transition_res.is_valid:
                motor.status = motor_transition_res.next_state
                session.add(motor)
                if motor_transition_res.event_type is not None:
                    created_event = MotorEvent(
                        id=uuid.uuid4(),
                        motor_id=motor.id,
                        event_type=motor_transition_res.event_type,
                        source=MotorEventSource.CONTROLLER,
                        occurred_at=payload_now,
                        event_payload=payload,
                        description=motor_transition_res.reason
                    )
                    session.add(created_event)

        session.add(command)
        await session.commit()
        await session.refresh(command)
        logger.info(f"Updated MotorCommand '{command_id}' to status '{command.status.value}' via MQTT ACK from '{device_uid}'")

        # Extract hierarchy for WebSocket broadcast
        ctrl = motor.controller if motor else None
        stn = ctrl.station if ctrl else None
        site = stn.site if stn else None
        org_id = site.organization_id if site else None
        site_id = site.id if site else None
        stn_id = stn.id if stn else None

        try:
            await stream_command_lifecycle(
                command_id=command.id,
                motor_id=command.motor_id,
                command_type=command.command_type,
                status=command.status,
                device_uid=device_uid,
                organization_id=org_id,
                site_id=site_id,
                station_id=stn_id,
                error_message=command.error_message,
                timestamp=payload_now
            )

            if motor_transition_res and motor_transition_res.is_valid and motor.status != old_motor_status:
                if motor_transition_res.event_type in (MotorEventType.FAULT, MotorEventType.EMERGENCY_STOP):
                    await stream_safety_alert(
                        event_type=motor_transition_res.event_type,
                        motor_id=motor.id,
                        motor_code=motor.motor_code,
                        device_uid=device_uid,
                        organization_id=org_id,
                        site_id=site_id,
                        station_id=stn_id,
                        description=motor_transition_res.reason,
                        payload=payload,
                        timestamp=payload_now
                    )

                await stream_motor_state(
                    motor_id=motor.id,
                    motor_code=motor.motor_code,
                    device_uid=device_uid,
                    status=motor.status,
                    organization_id=org_id,
                    site_id=site_id,
                    station_id=stn_id,
                    previous_status=old_motor_status,
                    timestamp=payload_now
                )
        except Exception as e:
            logger.error(f"Error streaming state/lifecycle for command '{command.id}': {e}")

        return command


@mqtt_router.route(f"{ROOT_PREFIX}/{{device_uid}}/ack")
@mqtt_router.route(f"{SHORT_PREFIX}/{{device_uid}}/ack")
async def handle_device_ack(device_uid: str, payload: Any, **kwargs):
    """MQTT Route handler for device command acknowledgment."""
    await process_ack_payload(device_uid, payload)
