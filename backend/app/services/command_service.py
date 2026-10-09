"""
HydraControl — Motor Command Service & DB Dispatch
Manages validation, creation, database persistence, and MQTT dispatching of motor commands.
"""

import uuid
import logging
from typing import Optional, Sequence, Union, Dict, Any
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.models.motor import Motor, MotorStatus
from app.models.motor_command import MotorCommand, CommandType, CommandStatus
from app.models.motor_event import MotorEvent, MotorEventType, MotorEventSource
from app.models.controller import Controller
from app.models.station import Station
from app.models.site import Site, SiteStatus
from app.mqtt.client import mqtt_client_service, MQTTClientService
from app.mqtt.router import build_device_command_topic
from app.websocket.streamer import stream_command_lifecycle, stream_motor_state, stream_safety_alert
from app.services.motor_state_engine import (
    transition_motor_state,
    MotorStateEvent,
    InvalidStateTransitionException
)

logger = logging.getLogger("hydracontrol.commands")


class MotorCommandNotFoundException(Exception):
    """Raised when requested motor command cannot be found."""
    pass


class MotorCommandValidationException(Exception):
    """Raised when motor command parameters or state are invalid."""
    pass


class MotorNotOperationalException(Exception):
    """Raised when motor state (OFFLINE, MAINTENANCE, DISABLED) prevents command execution."""
    pass


class MotorSiteSuspendedException(Exception):
    """Raised when the target motor belongs to a suspended site."""
    pass


class MotorSiteInactiveException(Exception):
    """Raised when the target motor belongs to an inactive site."""
    pass


async def dispatch_motor_command(
    session: AsyncSession,
    motor_id: uuid.UUID,
    command_type: Union[CommandType, str],
    user_id: Optional[uuid.UUID] = None,
    payload: Optional[Dict[str, Any]] = None,
    current_user_org_id: Optional[uuid.UUID] = None,
    is_super_admin: bool = False,
    mqtt_client: Optional[MQTTClientService] = None,
) -> MotorCommand:
    """
    Validate, persist, and dispatch a motor command over MQTT.
    1. Resolves motor, controller, station, and site relationships.
    2. Enforces organization tenant boundary & operational site lifecycle policies.
    3. Validates motor state (e.g. preventing START when DISABLED, MAINTENANCE, OFFLINE).
    4. Creates MotorCommand database record in PENDING state.
    5. Dispatches MQTT command to `hydracontrol/devices/{device_uid}/commands`.
    6. On successful publish, updates status to SENT with UTC timestamp.
    """
    # 1. Resolve motor and hierarchical associations
    stmt = (
        select(Motor)
        .options(
            selectinload(Motor.controller)
            .selectinload(Controller.station)
            .selectinload(Station.site)
        )
        .where(Motor.id == motor_id)
    )
    res = await session.execute(stmt)
    motor = res.scalar_one_or_none()

    if motor is None:
        raise MotorCommandNotFoundException(f"Motor with ID '{motor_id}' not found.")

    # 2. Validate hierarchy completeness
    controller = motor.controller
    if controller is None:
        raise MotorCommandValidationException(f"Motor '{motor_id}' is not linked to any controller.")

    station = controller.station
    if station is None:
        raise MotorCommandValidationException(f"Controller '{controller.id}' is not linked to any station.")

    site = station.site
    if site is None:
        raise MotorCommandValidationException(f"Station '{station.id}' is not linked to any site.")

    # 3. Validate Organization Isolation (IDOR Defense)
    if not is_super_admin and current_user_org_id is not None:
        if site.organization_id != current_user_org_id:
            # Mask foreign resource as not found to prevent tenant enumeration
            raise MotorCommandNotFoundException(f"Motor with ID '{motor_id}' not found.")

    # 4. Validate Site Operational State
    if site.status == SiteStatus.SUSPENDED:
        raise MotorSiteSuspendedException(f"Cannot dispatch command: Site '{site.name}' is suspended.")
    if site.status == SiteStatus.INACTIVE:
        raise MotorSiteInactiveException(f"Cannot dispatch command: Site '{site.name}' is inactive.")

    # 5. Convert & Validate Command Type
    if isinstance(command_type, str):
        try:
            cmd_type = CommandType(command_type.strip().upper())
        except ValueError:
            raise MotorCommandValidationException(f"Invalid command type '{command_type}'.")
    else:
        cmd_type = command_type

    # Validate Controller Operational State
    from app.models.controller import ControllerStatus
    if controller.status in (ControllerStatus.OFFLINE, ControllerStatus.DECOMMISSIONED, ControllerStatus.INACTIVE):
        if cmd_type != CommandType.EMERGENCY_STOP:
            raise MotorNotOperationalException(
                f"Cannot dispatch command: Controller '{controller.controller_code}' is in status '{controller.status.value}'."
            )

    # 6. Enforce Motor State Constraints & Pre-Start Safety Checks
    if cmd_type == CommandType.START:
        if motor.status in (MotorStatus.DISABLED, MotorStatus.MAINTENANCE, MotorStatus.OFFLINE, MotorStatus.FAULT):
            raise MotorNotOperationalException(
                f"Cannot START motor '{motor.motor_code}' in status '{motor.status.value}'."
            )

        # Pre-start Water Quality Check (Phase 13 / P13-T02)
        from app.models.sensor import Sensor, SensorType
        from app.models.telemetry import TelemetryReading
        from app.models.settings import StationSettings
        from app.services.water_quality_service import evaluate_turbidity
        from sqlalchemy import desc

        stmt_turb = (
            select(TelemetryReading)
            .join(Sensor, TelemetryReading.sensor_id == Sensor.id)
            .join(Controller, Sensor.controller_id == Controller.id)
            .where(Controller.station_id == station.id)
            .where(Sensor.sensor_type == SensorType.TURBIDITY)
            .order_by(desc(TelemetryReading.occurred_at))
            .limit(1)
        )
        res_turb = await session.execute(stmt_turb)
        latest_turb = res_turb.scalar_one_or_none()
        if latest_turb is not None:
            turb_val = float(latest_turb.value)
            stmt_st_settings = select(StationSettings).where(StationSettings.station_id == station.id)
            res_st_settings = await session.execute(stmt_st_settings)
            st_settings = res_st_settings.scalar_one_or_none()
            configured_limit = float(st_settings.turbidity_threshold) if (st_settings and st_settings.turbidity_threshold is not None) else None

            turb_eval = evaluate_turbidity(turb_val, configured_limit)
            if not turb_eval.is_safe and turb_eval.hard_cutoff_exceeded:
                raise MotorCommandValidationException(
                    f"Safety Violation: Cannot START motor when water turbidity ({turb_val:.1f} NTU) exceeds hard safety limit (25 NTU)."
                )

    # 7. Create MotorCommand in Database (Initial State: PENDING)

    command_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    cmd_payload = payload or {}

    command = MotorCommand(
        id=command_id,
        motor_id=motor.id,
        command_type=cmd_type,
        status=CommandStatus.PENDING,
        requested_by=user_id,
        command_payload=cmd_payload,
        requested_at=now
    )
    session.add(command)
    await session.commit()
    await session.refresh(command)

    # 8. Build MQTT Payload and Destination Topic
    topic = build_device_command_topic(controller.device_uid)
    mqtt_payload = {
        "command_id": str(command.id),
        "command_type": command.command_type.value,
        "motor_code": motor.motor_code,
        "timestamp": now.isoformat(),
        "payload": cmd_payload
    }

    # 9. Publish via Phase 5 MQTT Client Service
    published = False
    if mqtt_client is not None:
        try:
            published = await mqtt_client.publish(topic=topic, payload=mqtt_payload, qos=1)
        except Exception as e:
            logger.warning(f"MQTT publish error on topic '{topic}': {e}")
    else:
        if mqtt_client_service and mqtt_client_service.is_connected:
            try:
                published = await mqtt_client_service.publish(topic=topic, payload=mqtt_payload, qos=1)
            except Exception as e:
                logger.warning(f"MQTT publish error on topic '{topic}': {e}")
        else:
            logger.info(f"MQTT broker not connected; queued as PENDING for topic '{topic}'")
            published = False

    if published:
        command.status = CommandStatus.SENT
        command.sent_at = datetime.now(timezone.utc)
        session.add(command)

    # 10. Motor State Transition on Command Dispatch
    event_map = {
        CommandType.START: MotorStateEvent.CMD_START,
        CommandType.STOP: MotorStateEvent.CMD_STOP,
        CommandType.EMERGENCY_STOP: MotorStateEvent.CMD_EMERGENCY_STOP,
        CommandType.RESET: MotorStateEvent.CMD_RESET,
    }
    state_event = event_map.get(cmd_type)
    old_motor_status = motor.status
    transition_res = None
    if state_event:
        transition_res = transition_motor_state(
            current_state=motor.status,
            event=state_event,
            context={"error_message": f"Command {cmd_type.value} dispatched by user {user_id}"}
        )
        if transition_res.is_valid:
            motor.status = transition_res.next_state
            session.add(motor)

            if transition_res.event_type is not None:
                is_auto_or_schedule = False
                if cmd_payload and isinstance(cmd_payload, dict):
                    reason_str = str(cmd_payload.get("reason", "")).upper()
                    if "SCHEDULE" in reason_str or "TIMER" in reason_str or "AUTO" in reason_str or "schedule_id" in cmd_payload:
                        is_auto_or_schedule = True

                event_source = (
                    MotorEventSource.AUTOMATION
                    if is_auto_or_schedule
                    else (MotorEventSource.USER if user_id else MotorEventSource.SYSTEM)
                )

                desc_text = transition_res.reason
                if cmd_payload and isinstance(cmd_payload, dict):
                    if cmd_payload.get("schedule_name"):
                        sched = cmd_payload.get("schedule_name")
                        desc_text = f"Schedule Completed: {sched}" if cmd_type == CommandType.STOP else f"Schedule: {sched}"
                    elif cmd_payload.get("reason") == "MANUAL_STOP":
                        desc_text = "Manual stop command by operator"
                    elif cmd_payload.get("reason") == "TIMER_EXPIRED":
                        desc_text = "Timer Expired - Normal Auto Stop"
                    elif cmd_payload.get("description"):
                        desc_text = str(cmd_payload.get("description"))

                event_entry = MotorEvent(
                    id=uuid.uuid4(),
                    motor_id=motor.id,
                    event_type=transition_res.event_type,
                    source=event_source,
                    occurred_at=command.sent_at or datetime.now(timezone.utc),
                    event_payload=cmd_payload,
                    description=desc_text
                )
                session.add(event_entry)

        # Register dynamic runtime timer metadata with TimerSchedulerService
        try:
            from app.services.timer_scheduler_service import timer_scheduler
            if cmd_type == CommandType.START:
                dur = (cmd_payload.get("duration_seconds") if isinstance(cmd_payload, dict) else None) or 1800
                is_auto_or_sched = False
                if cmd_payload and isinstance(cmd_payload, dict):
                    reason_str = str(cmd_payload.get("reason", "")).upper()
                    if "SCHEDULE" in reason_str or "TIMER" in reason_str or "AUTO" in reason_str or "schedule_id" in cmd_payload:
                        is_auto_or_sched = True
                timer_scheduler._active_timer_metadata[motor.id] = {
                    "duration_seconds": int(dur),
                    "source": "SCHEDULED" if is_auto_or_sched else "MANUAL",
                    "started_at": (command.sent_at or datetime.now(timezone.utc)).isoformat(),
                    "reason": cmd_payload.get("reason", "MANUAL_START") if isinstance(cmd_payload, dict) else "MANUAL_START",
                    "schedule_name": cmd_payload.get("schedule_name") if isinstance(cmd_payload, dict) else None,
                }
                timer_scheduler._warned_cycles.pop(motor.id, None)
                timer_scheduler._stopped_cycles.pop(motor.id, None)
                timer_scheduler._timer_extensions[motor.id] = 0
            elif cmd_type in (CommandType.STOP, CommandType.EMERGENCY_STOP):
                timer_scheduler._active_timer_metadata.pop(motor.id, None)
                timer_scheduler._timer_extensions.pop(motor.id, None)
                timer_scheduler._warned_cycles.pop(motor.id, None)
                timer_scheduler._stopped_cycles.pop(motor.id, None)
        except Exception as t_err:
            logger.warning(f"Error registering timer metadata: {t_err}")

    await session.commit()
    await session.refresh(command)
    logger.info(f"Dispatched MotorCommand '{command.id}' ({cmd_type.value}) -> {topic} [{command.status.value}]")

    if published:
        try:
            await stream_command_lifecycle(
                command_id=command.id,
                motor_id=motor.id,
                command_type=command.command_type,
                status=command.status,
                device_uid=controller.device_uid,
                organization_id=site.organization_id,
                site_id=site.id,
                station_id=station.id,
                timestamp=command.sent_at
            )

            if transition_res and transition_res.is_valid and transition_res.next_state != old_motor_status:
                if transition_res.event_type in (MotorEventType.FAULT, MotorEventType.EMERGENCY_STOP):
                    await stream_safety_alert(
                        event_type=transition_res.event_type,
                        station_id=station.id,
                        device_uid=controller.device_uid,
                        motor_code=motor.motor_code,
                        organization_id=site.organization_id,
                        site_id=site.id,
                        description=transition_res.reason,
                        timestamp=command.sent_at
                    )
                else:
                    await stream_motor_state(
                        motor_id=motor.id,
                        motor_code=motor.motor_code,
                        device_uid=controller.device_uid,
                        status=motor.status,
                        previous_status=old_motor_status,
                        organization_id=site.organization_id,
                        site_id=site.id,
                        station_id=station.id,
                        timestamp=command.sent_at
                    )
        except Exception as ws_err:
            logger.warning(f"Failed to broadcast command dispatch websocket event: {ws_err}")
    else:
        logger.warning(f"MotorCommand '{command.id}' queued as PENDING (MQTT broker unavailable)")

    return command


async def get_motor_command_by_id(
    session: AsyncSession,
    command_id: uuid.UUID
) -> Optional[MotorCommand]:
    """Retrieve a motor command by its UUID."""
    stmt = (
        select(MotorCommand)
        .options(selectinload(MotorCommand.motor).selectinload(Motor.controller))
        .where(MotorCommand.id == command_id)
    )
    res = await session.execute(stmt)
    return res.scalar_one_or_none()


async def list_motor_commands(
    session: AsyncSession,
    motor_id: Optional[uuid.UUID] = None
) -> Sequence[MotorCommand]:
    """List motor commands, optionally filtered by motor_id."""
    stmt = select(MotorCommand).options(selectinload(MotorCommand.motor))
    if motor_id is not None:
        stmt = stmt.where(MotorCommand.motor_id == motor_id)
    stmt = stmt.order_by(MotorCommand.requested_at.desc())
    res = await session.execute(stmt)
    return res.scalars().all()
