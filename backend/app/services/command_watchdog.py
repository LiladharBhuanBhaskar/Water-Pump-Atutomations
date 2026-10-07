"""
HydraControl — Motor Command Timeout Watchdog Service
Scans pending and sent motor commands and transitions expired commands to TIMEOUT status.
Ensures terminal-state preservation, idempotency, and deterministic monitoring.
"""

import logging
from typing import Optional, Dict, Any, Sequence, List
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

try:
    from app.models.motor_command import MotorCommand, CommandType, CommandStatus
    from app.models.motor import Motor, MotorStatus
    from app.models.motor_event import MotorEvent, MotorEventType, MotorEventSource
    from app.models.controller import Controller
    from app.models.station import Station
    from app.models.site import Site
    from app.websocket.streamer import stream_command_lifecycle, stream_motor_state
except ImportError:
    from backend.app.models.motor_command import MotorCommand, CommandType, CommandStatus
    from backend.app.models.motor import Motor, MotorStatus
    from backend.app.models.motor_event import MotorEvent, MotorEventType, MotorEventSource
    from backend.app.models.controller import Controller
    from backend.app.models.station import Station
    from backend.app.models.site import Site
    from backend.app.websocket.streamer import stream_command_lifecycle, stream_motor_state

logger = logging.getLogger("hydracontrol.services.command_watchdog")

DEFAULT_COMMAND_TIMEOUT_SECONDS = 30


async def process_command_timeouts(
    session: AsyncSession,
    timeout_seconds: int = DEFAULT_COMMAND_TIMEOUT_SECONDS,
    now: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    Identifies unresolved motor commands (PENDING or SENT) that have exceeded the timeout duration
    and transitions them safely to TIMEOUT state with populated failure metadata.
    Broadcasts TIMEOUT lifecycle events to WebSocket clients.

    Guarantees:
    - Terminal commands (EXECUTED, FAILED, TIMEOUT) are untouched.
    - Idempotent execution (repeated runs do not alter already processed records).
    - No MQTT republishes are generated during watchdog execution.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    # Query all active non-terminal commands with hierarchy
    terminal_statuses = (
        CommandStatus.EXECUTED,
        CommandStatus.FAILED,
        CommandStatus.TIMEOUT
    )

    stmt = (
        select(MotorCommand)
        .options(
            selectinload(MotorCommand.motor)
            .selectinload(Motor.controller)
            .selectinload(Controller.station)
            .selectinload(Station.site)
        )
        .where(MotorCommand.status.not_in(terminal_statuses))
    )
    res = await session.execute(stmt)
    active_commands: Sequence[MotorCommand] = res.scalars().all()

    timed_out_count = 0
    unaffected_count = 0
    timed_out_items: List[Dict[str, Any]] = []

    for cmd in active_commands:
        # Determine reference timestamp: prefer sent_at, fall back to requested_at
        ref_time = cmd.sent_at or cmd.requested_at
        if ref_time is None:
            unaffected_count += 1
            continue

        if ref_time.tzinfo is None:
            ref_time = ref_time.replace(tzinfo=timezone.utc)

        elapsed_seconds = (now - ref_time).total_seconds()

        if elapsed_seconds > timeout_seconds:
            cmd.status = CommandStatus.TIMEOUT
            cmd.failed_at = now
            cmd.error_message = (
                f"Command timed out after {int(elapsed_seconds)}s (limit: {timeout_seconds}s) "
                f"without receiving execution confirmation."
            )
            session.add(cmd)
            timed_out_count += 1

            ctrl = cmd.motor.controller if cmd.motor else None
            stn = ctrl.station if ctrl else None
            site = stn.site if stn else None
            motor = cmd.motor

            old_motor_status = motor.status if motor else None
            motor_reverted = False
            # Revert unconfirmed STARTING state to OFF so motor does not remain falsely STARTING/ON
            if motor and cmd.command_type == CommandType.START and motor.status == MotorStatus.STARTING:
                motor.status = MotorStatus.OFF
                session.add(motor)
                motor_reverted = True

            timed_out_items.append({
                "command_id": cmd.id,
                "motor_id": cmd.motor_id,
                "command_type": cmd.command_type,
                "status": cmd.status,
                "device_uid": ctrl.device_uid if ctrl else "UNKNOWN",
                "motor_code": motor.motor_code if motor else "UNKNOWN",
                "organization_id": site.organization_id if site else None,
                "site_id": site.id if site else None,
                "station_id": stn.id if stn else None,
                "error_message": cmd.error_message,
                "motor_reverted": motor_reverted,
                "old_motor_status": old_motor_status,
                "new_motor_status": motor.status if motor else None,
                "timestamp": now
            })

            logger.warning(
                f"MotorCommand '{cmd.id}' ({cmd.command_type.value}) timed out after "
                f"{elapsed_seconds:.1f}s. Transitioned to TIMEOUT."
            )
        else:
            unaffected_count += 1

    if timed_out_count > 0:
        await session.commit()

        # Stream timeout notifications to WebSocket subscribers
        for item in timed_out_items:
            try:
                await stream_command_lifecycle(
                    command_id=item["command_id"],
                    motor_id=item["motor_id"],
                    command_type=item["command_type"],
                    status=item["status"],
                    device_uid=item["device_uid"],
                    organization_id=item["organization_id"],
                    site_id=item["site_id"],
                    station_id=item["station_id"],
                    error_message=item["error_message"],
                    timestamp=item["timestamp"]
                )

                if item.get("motor_reverted") and item.get("new_motor_status"):
                    await stream_motor_state(
                        motor_id=item["motor_id"],
                        motor_code=item["motor_code"],
                        device_uid=item["device_uid"],
                        status=item["new_motor_status"],
                        organization_id=item["organization_id"],
                        site_id=item["site_id"],
                        station_id=item["station_id"],
                        previous_status=item["old_motor_status"],
                        timestamp=item["timestamp"]
                    )
            except Exception as e:
                logger.error(f"Error streaming timeout lifecycle for '{item['command_id']}': {e}")

    return {
        "checked_at": now.isoformat(),
        "total_checked": len(active_commands),
        "timed_out_count": timed_out_count,
        "unaffected_count": unaffected_count,
        "timeout_seconds": timeout_seconds,
    }
