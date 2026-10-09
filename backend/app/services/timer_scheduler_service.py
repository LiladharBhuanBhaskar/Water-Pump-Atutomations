"""
HydraControl — Timer & Countdown Scheduler Service (Phase 16 - Wave A & Phase 17).
Provides deterministic evaluation of active motor runtimes against configured timers,
triggers 1-minute pre-expiration warnings over WebSockets, dispatches authoritative
CMD_STOP via the Command Service without bypassing the Phase 10 Motor State Engine,
and executes time-of-day/days-of-week scheduled motor start operations safely with full
in-app notifications and WebSocket broadcasts.
"""

import uuid
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Set, Any
from zoneinfo import ZoneInfo
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.models.motor import Motor, MotorStatus
from app.models.station import Station
from app.models.site import Site
from app.models.controller import Controller
from app.models.settings import StationSettings
from app.models.automation_rule import AutomationRule, AutomationRuleType, AutomationRuleStatus, AutomationAction
from app.models.motor_command import CommandType
from app.models.motor_event import MotorEvent, MotorEventType
from app.models.audit_log import AuditAction, AuditActorType
from app.services.command_service import dispatch_motor_command
from app.services.audit_service import log_audit_event
from app.services.notification_service import notification_service
from app.schemas.notification import NotificationChannel, NotificationSeverity
from app.websocket.streamer import stream_safety_alert, stream_notification
from app.mqtt.client import mqtt_client_service
from app.mqtt.handlers.ack_handler import process_ack_payload

logger = logging.getLogger("hydracontrol.scheduler")


def ensure_utc(dt: Optional[datetime]) -> datetime:
    """Ensure datetime has UTC timezone."""
    if dt is None:
        return datetime.now(timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def get_local_datetime(dt_utc: datetime, tz_str: Optional[str] = None) -> datetime:
    """Converts a UTC datetime to target timezone, defaulting to Asia/Kolkata (IST)."""
    tz_name = tz_str or "Asia/Kolkata"
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        if tz_name in ("Asia/Kolkata", "Asia/Calcutta", "IST", "India Standard Time"):
            tz = timezone(timedelta(hours=5, minutes=30), name="Asia/Kolkata")
        else:
            tz = timezone.utc
    return dt_utc.astimezone(tz)


@dataclass
class TimerEvaluationResult:
    is_running: bool
    duration_seconds: int
    elapsed_seconds: float
    remaining_seconds: float
    should_warn_1min: bool
    should_stop: bool
    is_expired: bool


@dataclass
class TimerProcessingResult:
    motor_id: uuid.UUID
    motor_code: str
    status: MotorStatus
    duration_seconds: int
    elapsed_seconds: float
    remaining_seconds: float
    warning_triggered: bool
    stop_dispatched: bool
    reason: Optional[str] = None


@dataclass
class ScheduleExecutionResult:
    schedule_id: uuid.UUID
    schedule_name: str
    station_id: uuid.UUID
    motor_id: Optional[uuid.UUID]
    executed: bool
    reason: Optional[str] = None
    command_id: Optional[uuid.UUID] = None


class TimerSchedulerService:
    def __init__(self):
        # In-memory deduplication sets for active motor run cycles: motor_id -> cycle_start_iso
        self._warned_cycles: Dict[uuid.UUID, str] = {}
        self._stopped_cycles: Dict[uuid.UUID, str] = {}
        # In-memory deduplication for time-of-day scheduled triggers: rule_id -> "YYYY-MM-DD-HH:MM"
        self._scheduled_triggers: Dict[uuid.UUID, str] = {}
        # Active timer extensions and metadata: motor_id -> additional seconds
        self._timer_extensions: Dict[uuid.UUID, int] = {}
        self._last_continue_times: Dict[uuid.UUID, datetime] = {}
        self._active_timer_metadata: Dict[uuid.UUID, Dict[str, Any]] = {}

    def evaluate_motor_timer(
        self,
        motor_status: MotorStatus,
        started_at: datetime,
        duration_seconds: int,
        current_time: Optional[datetime] = None,
    ) -> TimerEvaluationResult:
        """
        Pure, deterministic timer evaluation function.
        Testable without requiring real wall-clock delays.
        """
        now = ensure_utc(current_time)
        start_utc = ensure_utc(started_at)

        if duration_seconds <= 0:
            duration_seconds = 3600  # fallback 1h default

        is_running = motor_status in (MotorStatus.ON, MotorStatus.STARTING)
        if not is_running:
            return TimerEvaluationResult(
                is_running=False,
                duration_seconds=duration_seconds,
                elapsed_seconds=0.0,
                remaining_seconds=float(duration_seconds),
                should_warn_1min=False,
                should_stop=False,
                is_expired=False,
            )

        elapsed = max(0.0, (now - start_utc).total_seconds())
        remaining = max(0.0, float(duration_seconds) - elapsed)
        is_expired = remaining <= 0.0
        should_warn = (remaining <= 60.0 and remaining > 0.0)
        should_stop = is_expired

        return TimerEvaluationResult(
            is_running=True,
            duration_seconds=duration_seconds,
            elapsed_seconds=elapsed,
            remaining_seconds=remaining,
            should_warn_1min=should_warn,
            should_stop=should_stop,
            is_expired=is_expired,
        )

    async def get_effective_duration_for_motor(
        self,
        session: AsyncSession,
        motor: Motor,
    ) -> int:
        """
        Determines the effective timer duration for a motor:
        1. Explicit active AutomationRule of type TIMER targeting this motor.
        2. StationSettings.default_timer_seconds for the parent station.
        3. Fallback default of 1800s (30 minutes).
        Applies any active in-memory timer extensions.
        """
        base_duration = 1800

        # 1. Check active metadata if populated
        meta = self._active_timer_metadata.get(motor.id)
        if meta and meta.get("duration_seconds"):
            base_duration = int(meta["duration_seconds"])
        else:
            # 2. Check AutomationRule
            rule_stmt = (
                select(AutomationRule)
                .where(
                    AutomationRule.motor_id == motor.id,
                    AutomationRule.rule_type == AutomationRuleType.TIMER,
                    AutomationRule.status == AutomationRuleStatus.ACTIVE,
                    AutomationRule.action == AutomationAction.STOP_MOTOR,
                )
                .limit(1)
            )
            rule_res = await session.execute(rule_stmt)
            rule = rule_res.scalar_one_or_none()
            if rule and rule.duration_seconds and rule.duration_seconds > 0:
                base_duration = rule.duration_seconds
            elif motor.controller and motor.controller.station_id:
                # 3. Check StationSettings
                settings_stmt = (
                    select(StationSettings)
                    .where(StationSettings.station_id == motor.controller.station_id)
                    .limit(1)
                )
                settings_res = await session.execute(settings_stmt)
                settings = settings_res.scalar_one_or_none()
                if settings and settings.default_timer_seconds and settings.default_timer_seconds > 0:
                    base_duration = settings.default_timer_seconds

        # Add any active timer continuation extensions
        ext = self._timer_extensions.get(motor.id, 0)
        return max(1, base_duration + ext)

    async def get_motor_timer_status(
        self,
        session: AsyncSession,
        motor_id: uuid.UUID,
        current_time: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Returns the real-time active timer and countdown status for a motor."""
        now = ensure_utc(current_time)
        stmt = (
            select(Motor)
            .where(Motor.id == motor_id)
            .options(
                selectinload(Motor.controller)
                .selectinload(Controller.station)
                .selectinload(Station.site)
            )
        )
        res = await session.execute(stmt)
        motor = res.scalar_one_or_none()
        if not motor:
            return {
                "motor_id": str(motor_id),
                "is_running": False,
                "status": "OFF",
                "remaining_seconds": 0,
                "duration_seconds": 0,
                "end_time": None,
            }

        is_running = motor.status in (MotorStatus.ON, MotorStatus.STARTING)
        duration = await self.get_effective_duration_for_motor(session, motor)
        start_time = await self.get_motor_start_time(session, motor.id, motor.updated_at or motor.created_at)
        eval_res = self.evaluate_motor_timer(
            motor_status=motor.status,
            started_at=start_time,
            duration_seconds=duration,
            current_time=now,
        )
        end_time = start_time + timedelta(seconds=duration)
        meta = self._active_timer_metadata.get(motor.id, {})

        return {
            "motor_id": str(motor.id),
            "motor_code": motor.motor_code,
            "status": motor.status.value if hasattr(motor.status, "value") else str(motor.status),
            "is_running": is_running,
            "started_at": start_time.isoformat(),
            "duration_seconds": duration,
            "end_time": end_time.isoformat() if is_running else None,
            "elapsed_seconds": round(eval_res.elapsed_seconds, 1),
            "remaining_seconds": round(eval_res.remaining_seconds, 1) if is_running else 0,
            "is_warning_active": eval_res.should_warn_1min if is_running else False,
            "is_expired": eval_res.is_expired if is_running else False,
            "schedule_id": meta.get("schedule_id"),
            "schedule_name": meta.get("schedule_name"),
            "source": meta.get("source", "SCHEDULED" if meta.get("schedule_id") else "MANUAL"),
        }

    async def continue_motor_timer(
        self,
        session: AsyncSession,
        motor_id: uuid.UUID,
        extend_seconds: Optional[int] = None,
        actor_id: Optional[uuid.UUID] = None,
    ) -> Dict[str, Any]:
        """
        Extends the running timer for a motor, preventing duplicate extends within 5s,
        cancelling previous expiration cycles, updating the authoritative end time,
        and broadcasting WebSocket notifications to both Operator and Admin.
        """
        now = datetime.now(timezone.utc)
        stmt = (
            select(Motor)
            .where(Motor.id == motor_id)
            .options(
                selectinload(Motor.controller)
                .selectinload(Controller.station)
                .selectinload(Station.site)
            )
        )
        res = await session.execute(stmt)
        motor = res.scalar_one_or_none()
        if not motor or motor.status not in (MotorStatus.ON, MotorStatus.STARTING):
            raise Exception(f"Cannot continue timer: Motor '{motor_id}' is not currently running.")

        # Default extension: 900s (15 minutes) or specified
        extension = extend_seconds if (extend_seconds and extend_seconds > 0) else 900

        # Idempotency: prevent double-clicks within 5 seconds
        last_time = self._last_continue_times.get(motor.id)
        if last_time and (now - last_time).total_seconds() < 5:
            logger.info(f"Duplicate continue request ignored for motor '{motor.motor_code}' (within cooldown)")
            return await self.get_motor_timer_status(session, motor_id, now)

        self._last_continue_times[motor.id] = now
        current_ext = self._timer_extensions.get(motor.id, 0)
        self._timer_extensions[motor.id] = current_ext + extension

        # Reset warning and stop cycle dedup so the new expiration window triggers properly
        self._warned_cycles.pop(motor.id, None)
        self._stopped_cycles.pop(motor.id, None)

        status_data = await self.get_motor_timer_status(session, motor_id, now)
        new_end_time_str = status_data["end_time"]
        new_end_dt = datetime.fromisoformat(new_end_time_str)

        org_id = motor.controller.station.site.organization_id if (motor.controller and motor.controller.station and motor.controller.station.site) else None
        site_id = motor.controller.station.site_id if (motor.controller and motor.controller.station) else None
        station_id = motor.controller.station_id if motor.controller else None
        site_tz = motor.controller.station.site.timezone if (motor.controller and motor.controller.station and motor.controller.station.site and motor.controller.station.site.timezone) else "Asia/Kolkata"
        local_new_end = get_local_datetime(new_end_dt, site_tz).strftime("%H:%M")

        # Broadcast TIMER_CONTINUED WebSocket notification and create in-app notification
        try:
            await notification_service.dispatch_notification(
                title="Motor Operation Continued",
                message=f"Motor {motor.motor_code} will continue running. New scheduled end: {local_new_end}",
                severity=NotificationSeverity.INFO,
                channels=[NotificationChannel.IN_APP, NotificationChannel.EMAIL],
                organization_id=org_id,
                site_id=site_id,
                station_id=station_id,
                motor_id=motor.id,
                event_type="TIMER_CONTINUED",
                metadata={
                    "motor_id": str(motor.id),
                    "motor_code": motor.motor_code,
                    "extended_seconds": extension,
                    "duration_seconds": status_data["duration_seconds"],
                    "end_time": new_end_time_str,
                    "remaining_seconds": status_data["remaining_seconds"],
                },
                bypass_throttle=True,
            )
        except Exception as notif_err:
            logger.warning(f"Error dispatching continue notification: {notif_err}")

        return status_data

    def cancel_motor_timer(self, motor_id: uuid.UUID) -> None:
        """Cleans up active timer extensions and metadata when motor stops."""
        self._timer_extensions.pop(motor_id, None)
        self._warned_cycles.pop(motor_id, None)
        self._stopped_cycles.pop(motor_id, None)
        self._active_timer_metadata.pop(motor_id, None)

    async def get_configured_timer_duration(
        self,
        session: AsyncSession,
        motor: Motor,
    ) -> int:
        """Determines configured timer duration from AutomationRule or StationSettings."""
        rule_stmt = (
            select(AutomationRule)
            .where(
                AutomationRule.motor_id == motor.id,
                AutomationRule.rule_type == AutomationRuleType.TIMER,
                AutomationRule.status == AutomationRuleStatus.ACTIVE,
                AutomationRule.action == AutomationAction.STOP_MOTOR,
            )
            .limit(1)
        )
        rule_res = await session.execute(rule_stmt)
        rule = rule_res.scalar_one_or_none()
        if rule and rule.duration_seconds and rule.duration_seconds > 0:
            return rule.duration_seconds

        # 2. Check StationSettings via controller -> station
        if motor.controller and motor.controller.station_id:
            settings_stmt = (
                select(StationSettings)
                .where(StationSettings.station_id == motor.controller.station_id)
                .limit(1)
            )
            settings_res = await session.execute(settings_stmt)
            settings = settings_res.scalar_one_or_none()
            if settings and settings.default_timer_seconds and settings.default_timer_seconds > 0:
                return settings.default_timer_seconds

        return 1800  # Default 30 min fallback

    async def get_motor_start_time(
        self,
        session: AsyncSession,
        motor_id: uuid.UUID,
        fallback_time: datetime,
    ) -> datetime:
        """Finds when the motor entered ON state via latest active STARTED MotorEvent."""
        stmt = (
            select(MotorEvent)
            .where(
                MotorEvent.motor_id == motor_id,
                MotorEvent.event_type.in_([MotorEventType.STARTED, MotorEventType.ONLINE]),
            )
            .order_by(MotorEvent.occurred_at.desc())
            .limit(1)
        )
        res = await session.execute(stmt)
        event = res.scalar_one_or_none()
        if event and event.occurred_at:
            # Check if there is a STOP/FAULT event at or after this start event
            stop_stmt = (
                select(MotorEvent)
                .where(
                    MotorEvent.motor_id == motor_id,
                    MotorEvent.event_type.in_([
                        MotorEventType.STOPPED,
                        MotorEventType.FAULT,
                        MotorEventType.EMERGENCY_STOP,
                    ]),
                    MotorEvent.occurred_at >= event.occurred_at,
                )
                .limit(1)
            )
            stop_res = await session.execute(stop_stmt)
            if stop_res.scalar_one_or_none() is None:
                return ensure_utc(event.occurred_at)
        return ensure_utc(fallback_time)

    async def check_and_process_motor_timers(
        self,
        session: AsyncSession,
        current_time: Optional[datetime] = None,
    ) -> List[TimerProcessingResult]:
        """
        Evaluates all running motors against configured timers,
        broadcasting 1-minute warnings and dispatching STOP commands when expired.
        """
        now = ensure_utc(current_time)
        results: List[TimerProcessingResult] = []

        # Find all motors that are currently ON or STARTING
        stmt = (
            select(Motor)
            .where(Motor.status.in_([MotorStatus.ON, MotorStatus.STARTING]))
            .options(
                selectinload(Motor.controller)
                .selectinload(Controller.station)
                .selectinload(Station.site)
            )
        )
        res = await session.execute(stmt)
        running_motors = res.scalars().all()

        for motor in running_motors:
            duration = await self.get_effective_duration_for_motor(session, motor)
            start_time = await self.get_motor_start_time(session, motor.id, motor.updated_at or motor.created_at)
            cycle_key = start_time.isoformat()

            eval_res = self.evaluate_motor_timer(
                motor_status=motor.status,
                started_at=start_time,
                duration_seconds=duration,
                current_time=now,
            )

            warning_triggered = False
            stop_dispatched = False
            reason = None

            # Resolve hierarchy IDs
            org_id = None
            site_id = None
            station_id = None
            if motor.controller:
                station_id = motor.controller.station_id
                if motor.controller.station:
                    site_id = motor.controller.station.site_id
                    if motor.controller.station.site:
                        org_id = motor.controller.station.site.organization_id

            # 1. 1-Minute Warning Trigger
            if eval_res.should_warn_1min:
                if self._warned_cycles.get(motor.id) != cycle_key:
                    self._warned_cycles[motor.id] = cycle_key
                    warning_triggered = True
                    reason = "1_MIN_WARNING"

                    # Broadcast safety alert and notification
                    try:
                        await stream_safety_alert(
                            event_type="TIMER_WARNING_1MIN",
                            motor_id=motor.id,
                            motor_code=motor.motor_code,
                            device_uid=motor.controller.device_uid if motor.controller else "",
                            organization_id=org_id,
                            site_id=site_id,
                            station_id=station_id,
                            description=f"Motor {motor.motor_code} will automatically stop in {int(eval_res.remaining_seconds)} seconds.",
                            payload={
                                "remaining_seconds": eval_res.remaining_seconds,
                                "duration_seconds": duration,
                            },
                            timestamp=now,
                        )
                    except Exception:
                        pass

                    try:
                        await notification_service.dispatch_notification(
                            title="Scheduled Pump Ending Soon",
                            message=f"Motor {motor.motor_code} will automatically stop in {int(eval_res.remaining_seconds)} seconds.",
                            severity=NotificationSeverity.WARNING,
                            channels=[NotificationChannel.IN_APP],
                            organization_id=org_id,
                            site_id=site_id,
                            station_id=station_id,
                            motor_id=motor.id,
                            event_type="TIMER_WARNING",
                            metadata={
                                "remaining_seconds": eval_res.remaining_seconds,
                                "duration_seconds": duration,
                            },
                            bypass_throttle=True,
                        )
                    except Exception as e:
                        logger.warning(f"Error dispatching timer warning notification: {e}")

            # 2. Expiration Auto-Stop Trigger
            if eval_res.should_stop:
                if self._stopped_cycles.get(motor.id) != cycle_key:
                    self._stopped_cycles[motor.id] = cycle_key
                    stop_dispatched = True
                    reason = "TIMER_EXPIRED"

                    meta = self._active_timer_metadata.get(motor.id, {})
                    sched_name = meta.get("schedule_name")
                    is_scheduled = bool(sched_name or meta.get("schedule_id"))
                    stop_reason = "SCHEDULE_COMPLETED" if is_scheduled else "TIMER_EXPIRED"

                    # Dispatch authoritative STOP command via command service
                    try:
                        stop_cmd = await dispatch_motor_command(
                            session=session,
                            motor_id=motor.id,
                            command_type=CommandType.STOP,
                            user_id=None,
                            payload={
                                "reason": stop_reason,
                                "schedule_name": sched_name,
                                "runtime_seconds": eval_res.elapsed_seconds,
                                "configured_duration": duration,
                            },
                            is_super_admin=True,
                        )
                        await session.commit()
                        if not mqtt_client_service.is_connected and motor.controller:
                            await process_ack_payload(
                                device_uid=motor.controller.device_uid,
                                payload={"command_id": str(stop_cmd.id), "status": "ACKNOWLEDGED"}
                            )
                            await process_ack_payload(
                                device_uid=motor.controller.device_uid,
                                payload={"command_id": str(stop_cmd.id), "status": "EXECUTED"}
                            )
                    except Exception as e:
                        reason = f"STOP_DISPATCH_FAILED: {str(e)}"

                    self.cancel_motor_timer(motor.id)

                    notif_title = "Scheduled Pump Stopped" if is_scheduled else "Pump Stopped (Timer Ended)"
                    notif_msg = (
                        f"Motor {motor.motor_code} has completed schedule '{sched_name}' and is now closed / stopped."
                        if sched_name else
                        f"Motor {motor.motor_code} has been automatically stopped because the scheduled duration ended."
                    )

                    try:
                        await notification_service.dispatch_notification(
                            title=notif_title,
                            message=notif_msg,
                            severity=NotificationSeverity.INFO,
                            channels=[NotificationChannel.IN_APP, NotificationChannel.EMAIL],
                            organization_id=org_id,
                            site_id=site_id,
                            station_id=station_id,
                            motor_id=motor.id,
                            event_type="SCHEDULE_STOPPED" if is_scheduled else "TIMER_EXPIRED",
                            metadata={
                                "runtime_seconds": eval_res.elapsed_seconds,
                                "configured_duration": duration,
                                "schedule_name": sched_name,
                            },
                            bypass_throttle=True,
                        )
                    except Exception as e:
                        logger.warning(f"Error dispatching timer expiry notification: {e}")

            results.append(
                TimerProcessingResult(
                    motor_id=motor.id,
                    motor_code=motor.motor_code,
                    status=motor.status,
                    duration_seconds=duration,
                    elapsed_seconds=eval_res.elapsed_seconds,
                    remaining_seconds=eval_res.remaining_seconds,
                    warning_triggered=warning_triggered,
                    stop_dispatched=stop_dispatched,
                    reason=reason,
                )
            )

        return results

    # Alias for background runner consistency
    process_active_timers = check_and_process_motor_timers

    async def check_and_execute_schedules(
        self,
        session: AsyncSession,
        current_time: Optional[datetime] = None,
    ) -> List[ScheduleExecutionResult]:
        """
        Evaluates active schedule definitions against current time in local timezone.
        When current time matches schedule start_time and day of week:
        - Verifies motor safety state (must be OFF/STANDBY, not in FAULT/EMERGENCY_STOP).
        - Dispatches authoritative CMD_START.
        - Emits in-app and WebSocket notification (SCHEDULE_STARTED).
        - Prevents duplicate executions in the same minute window.
        """
        now_utc = ensure_utc(current_time)
        results: List[ScheduleExecutionResult] = []

        stmt = (
            select(AutomationRule)
            .where(
                AutomationRule.rule_type == AutomationRuleType.TIMER,
                AutomationRule.status == AutomationRuleStatus.ACTIVE,
            )
            .options(
                selectinload(AutomationRule.motor),
                selectinload(AutomationRule.station).selectinload(Station.site),
            )
        )
        res = await session.execute(stmt)
        rules = res.scalars().all()

        day_aliases = {
            0: ["MON", "MONDAY", "0"],
            1: ["TUE", "TUESDAY", "1"],
            2: ["WED", "WEDNESDAY", "2"],
            3: ["THU", "THURSDAY", "3"],
            4: ["FRI", "FRIDAY", "4"],
            5: ["SAT", "SATURDAY", "5"],
            6: ["SUN", "SUNDAY", "6"],
        }

        for rule in rules:
            if not rule.motor_id:
                continue

            # Determine local timezone for schedule evaluation
            site_tz = "Asia/Kolkata"
            if rule.station and rule.station.site and rule.station.site.timezone:
                site_tz = rule.station.site.timezone

            local_dt = get_local_datetime(now_utc, site_tz)
            weekday_num = local_dt.weekday()
            valid_today_keys = set(day_aliases.get(weekday_num, []))
            current_time_str = local_dt.strftime("%H:%M")
            minute_key = local_dt.strftime("%Y-%m-%d-%H:%M")

            # Parse schedule metadata from description
            days = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
            start = "06:00"
            if rule.description:
                try:
                    data = json.loads(rule.description)
                    days = data.get("days_of_week", days)
                    start = data.get("start_time", start)
                except Exception:
                    pass

            # Normalize start time (e.g. "6:05" -> "06:05", "16:05:00" -> "16:05")
            start_clean = str(start).strip()
            if len(start_clean) == 4 and start_clean[1] == ':':
                start_clean = "0" + start_clean
            elif len(start_clean) > 5:
                start_clean = start_clean[:5]

            # Check if today and current minute match schedule
            rule_days_normalized = [str(d).strip().upper() for d in days]
            day_matches = any(k in rule_days_normalized for k in valid_today_keys)
            time_matches = (start_clean == current_time_str)

            logger.info(
                f"[SCHEDULER_CHECK] Schedule '{rule.name}' ({rule.id}) | Local {site_tz}: {current_time_str} | Scheduled: {start_clean} | "
                f"Today: {local_dt.strftime('%A')} (match={day_matches}) | TimeMatch: {time_matches}"
            )

            if not (day_matches and time_matches):
                continue

            # Deduplication: only trigger once per minute window
            if self._scheduled_triggers.get(rule.id) == minute_key:
                logger.debug(f"[SCHEDULER_DEDUP] Schedule '{rule.name}' already triggered for minute {minute_key}")
                continue

            self._scheduled_triggers[rule.id] = minute_key
            logger.info(f"[SCHEDULER_TRIGGER] Executing schedule '{rule.name}' ({rule.id}) for motor '{rule.motor_id}' at {current_time_str}")

            motor_stmt = (
                select(Motor)
                .options(
                    selectinload(Motor.controller)
                    .selectinload(Controller.station)
                    .selectinload(Station.site)
                )
                .where(Motor.id == rule.motor_id)
            )
            motor_res = await session.execute(motor_stmt)
            motor = motor_res.scalar_one_or_none()

            if motor is None:
                results.append(
                    ScheduleExecutionResult(
                        schedule_id=rule.id,
                        schedule_name=rule.name,
                        station_id=rule.station_id,
                        motor_id=rule.motor_id,
                        executed=False,
                        reason="MOTOR_NOT_FOUND",
                    )
                )
                continue

            # Safety checks: cannot start if motor is in FAULT, EMERGENCY_STOP, or already ON
            if motor.status in (MotorStatus.FAULT, MotorStatus.DISABLED, MotorStatus.MAINTENANCE):
                results.append(
                    ScheduleExecutionResult(
                        schedule_id=rule.id,
                        schedule_name=rule.name,
                        station_id=rule.station_id,
                        motor_id=rule.motor_id,
                        executed=False,
                        reason=f"SAFETY_OVERRIDE_MOTOR_STATUS_{motor.status.value}",
                    )
                )
                continue

            if motor.status in (MotorStatus.ON, MotorStatus.STARTING):
                results.append(
                    ScheduleExecutionResult(
                        schedule_id=rule.id,
                        schedule_name=rule.name,
                        station_id=rule.station_id,
                        motor_id=rule.motor_id,
                        executed=False,
                        reason="MOTOR_ALREADY_RUNNING",
                    )
                )
                continue

            # Dispatch authoritative START command
            try:
                cmd = await dispatch_motor_command(
                    session=session,
                    motor_id=motor.id,
                    command_type=CommandType.START,
                    user_id=rule.created_by,
                    payload={
                        "reason": "SCHEDULED_START",
                        "schedule_id": str(rule.id),
                        "schedule_name": rule.name,
                        "duration_seconds": rule.duration_seconds,
                    },
                    is_super_admin=True,
                )
                await session.commit()

                rule_id = rule.id
                rule_name = rule.name
                rule_station_id = rule.station_id
                rule_motor_id = rule.motor_id
                org_id = rule.station.site.organization_id if (rule.station and rule.station.site) else None
                site_id = rule.station.site_id if rule.station else None

                # Record active timer metadata for countdown synchronization
                self._active_timer_metadata[motor.id] = {
                    "schedule_id": str(rule_id),
                    "schedule_name": rule_name,
                    "duration_seconds": rule.duration_seconds,
                    "source": "SCHEDULED",
                }

                # In standalone software mode without active MQTT client, auto-acknowledge command
                if not mqtt_client_service.is_connected and motor.controller:
                    try:
                        await process_ack_payload(
                            device_uid=motor.controller.device_uid,
                            payload={"command_id": str(cmd.id), "status": "ACKNOWLEDGED"}
                        )
                        await process_ack_payload(
                            device_uid=motor.controller.device_uid,
                            payload={"command_id": str(cmd.id), "status": "EXECUTED"}
                        )
                    except Exception as ack_err:
                        logger.warning(f"Standalone ACK simulation notice: {ack_err}")

                # Append-only audit record
                try:
                    await log_audit_event(
                        session=session,
                        action=AuditAction.START,
                        resource_type="Motor",
                        resource_id=motor.id,
                        action_description=f"Auto-started motor {motor.motor_code} via schedule '{rule_name}'",
                        actor_type=AuditActorType.SYSTEM,
                        actor_user_id=rule.created_by,
                        organization_id=org_id,
                        audit_metadata={
                            "schedule_id": str(rule_id),
                            "schedule_name": rule_name,
                            "command_id": str(cmd.id),
                        },
                    )
                except Exception:
                    pass

                # Dispatch Schedule Started In-App Notification + Buzzer Trigger
                try:
                    await notification_service.dispatch_notification(
                        title="Scheduled Pump Started",
                        message=f"Motor {motor.motor_code} auto-started according to schedule '{rule_name}'.",
                        severity=NotificationSeverity.INFO,
                        channels=[NotificationChannel.IN_APP, NotificationChannel.EMAIL],
                        organization_id=org_id,
                        site_id=site_id,
                        station_id=rule_station_id,
                        motor_id=rule_motor_id,
                        event_type="SCHEDULE_STARTED",
                        metadata={
                            "schedule_id": str(rule_id),
                            "schedule_name": rule_name,
                            "duration_seconds": rule.duration_seconds,
                            "command_id": str(cmd.id),
                        },
                        bypass_throttle=True,
                    )
                except Exception as notif_err:
                    logger.warning(f"Error dispatching schedule start notification: {notif_err}")

                results.append(
                    ScheduleExecutionResult(
                        schedule_id=rule_id,
                        schedule_name=rule_name,
                        station_id=rule_station_id,
                        motor_id=rule_motor_id,
                        executed=True,
                        reason="SCHEDULED_START_DISPATCHED",
                        command_id=cmd.id,
                    )
                )
            except Exception as e:
                results.append(
                    ScheduleExecutionResult(
                        schedule_id=rule.id,
                        schedule_name=rule.name,
                        station_id=rule.station_id,
                        motor_id=rule.motor_id,
                        executed=False,
                        reason=f"DISPATCH_ERROR: {str(e)}",
                    )
                )

        return results


timer_scheduler = TimerSchedulerService()
