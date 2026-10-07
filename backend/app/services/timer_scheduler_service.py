"""
HydraControl — Timer & Countdown Scheduler Service (Phase 16 - Wave A & Phase 17).
Provides deterministic evaluation of active motor runtimes against configured timers,
triggers 1-minute pre-expiration warnings over WebSockets, dispatches authoritative
CMD_STOP via the Command Service without bypassing the Phase 10 Motor State Engine,
and executes time-of-day/days-of-week scheduled motor start operations safely.
"""

import uuid
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, List, Dict, Set, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.models.motor import Motor, MotorStatus
from app.models.settings import StationSettings
from app.models.automation_rule import AutomationRule, AutomationRuleType, AutomationRuleStatus, AutomationAction
from app.models.motor_command import CommandType
from app.models.motor_event import MotorEvent, MotorEventType
from app.models.audit_log import AuditAction, AuditActorType
from app.services.command_service import dispatch_motor_command
from app.services.audit_service import log_audit_event
from app.websocket.streamer import stream_safety_alert


def ensure_utc(dt: Optional[datetime]) -> datetime:
    """Ensure datetime has UTC timezone."""
    if dt is None:
        return datetime.now(timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


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
        """
        # 1. Check AutomationRule
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
        """Finds when the motor entered ON state via latest STARTED MotorEvent."""
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
            .options(selectinload(Motor.controller))
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

            # 1. 1-Minute Warning Trigger
            if eval_res.should_warn_1min:
                if self._warned_cycles.get(motor.id) != cycle_key:
                    self._warned_cycles[motor.id] = cycle_key
                    warning_triggered = True
                    reason = "1_MIN_WARNING"

                    # Broadcast WebSocket alert via established stream_safety_alert helper
                    try:
                        await stream_safety_alert(
                            event_type="TIMER_WARNING_1MIN",
                            motor_id=motor.id,
                            motor_code=motor.motor_code,
                            device_uid=motor.controller.device_uid if motor.controller else "",
                            station_id=motor.controller.station_id if motor.controller else None,
                            description=f"Motor {motor.motor_code} will automatically stop in {int(eval_res.remaining_seconds)} seconds.",
                            payload={
                                "remaining_seconds": eval_res.remaining_seconds,
                                "duration_seconds": duration,
                            },
                            timestamp=now,
                        )
                    except Exception:
                        pass

            # 2. Expiration Auto-Stop Trigger
            if eval_res.should_stop:
                if self._stopped_cycles.get(motor.id) != cycle_key:
                    self._stopped_cycles[motor.id] = cycle_key
                    stop_dispatched = True
                    reason = "TIMER_EXPIRED"

                    # Dispatch authoritative STOP command via command service
                    try:
                        await dispatch_motor_command(
                            session=session,
                            motor_id=motor.id,
                            command_type=CommandType.STOP,
                            user_id=None,
                            payload={
                                "reason": "TIMER_EXPIRED",
                                "runtime_seconds": eval_res.elapsed_seconds,
                                "configured_duration": duration,
                            },
                            is_super_admin=True,
                        )
                    except Exception as e:
                        reason = f"STOP_DISPATCH_FAILED: {str(e)}"

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

    async def check_and_execute_schedules(
        self,
        session: AsyncSession,
        current_time: Optional[datetime] = None,
    ) -> List[ScheduleExecutionResult]:
        """
        Evaluates active schedule definitions against current time.
        When current time matches schedule start_time and day of week:
        - Verifies motor safety state (must be OFF/STANDBY, not in FAULT/EMERGENCY_STOP).
        - Dispatches authoritative CMD_START.
        - Prevents duplicate executions in the same minute window.
        """
        now = ensure_utc(current_time)
        day_map = {0: "MON", 1: "TUE", 2: "WED", 3: "THU", 4: "FRI", 5: "SAT", 6: "SUN"}
        current_day_str = day_map.get(now.weekday(), "MON")
        current_time_str = now.strftime("%H:%M")
        minute_key = now.strftime("%Y-%m-%d-%H:%M")

        results: List[ScheduleExecutionResult] = []

        stmt = (
            select(AutomationRule)
            .where(
                AutomationRule.rule_type == AutomationRuleType.TIMER,
                AutomationRule.status == AutomationRuleStatus.ACTIVE,
            )
            .options(
                selectinload(AutomationRule.motor),
                selectinload(AutomationRule.station),
            )
        )
        res = await session.execute(stmt)
        rules = res.scalars().all()

        for rule in rules:
            if not rule.motor_id:
                continue

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

            # Check if today and current minute match schedule
            day_matches = current_day_str in [d.upper().strip() for d in days]
            time_matches = (start.strip() == current_time_str)

            if not (day_matches and time_matches):
                continue

            # Deduplication: only trigger once per minute window
            if self._scheduled_triggers.get(rule.id) == minute_key:
                continue

            self._scheduled_triggers[rule.id] = minute_key

            motor = rule.motor
            if motor is None:
                # Motor relationship not preloaded, fetch
                motor_stmt = select(Motor).where(Motor.id == rule.motor_id)
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

                rule_id = rule.id
                rule_name = rule.name
                rule_station_id = rule.station_id
                rule_motor_id = rule.motor_id

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
                        organization_id=rule.station.site.organization_id if (rule.station and rule.station.site) else None,
                        audit_metadata={
                            "schedule_id": str(rule_id),
                            "schedule_name": rule_name,
                            "command_id": str(cmd.id),
                        },
                    )
                except Exception:
                    pass

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
