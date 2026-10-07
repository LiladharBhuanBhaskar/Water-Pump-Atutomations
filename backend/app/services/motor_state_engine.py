"""
HydraControl — Motor State Engine (Phase 10)
Deterministic, authoritative pure state-transition engine governing physical & logical
motor operational states with strict edge safety precedence.

Architectural Principles:
- "CLOUD CONTROLS, LOCAL CONTROLLER PROTECTS": Cloud transitions cannot override local safety latches.
- State Authoritativeness: ON is the authoritative operating state (database/wire contract).
- Separation of Concerns: Pure functional evaluation with structured results & explicit exception throwing.
"""

from dataclasses import dataclass
import enum
from typing import Optional, Dict, Any, Tuple, Union
from datetime import datetime, timezone, timedelta

try:
    from app.models.motor import MotorStatus
    from app.models.motor_event import MotorEventType
except ImportError:
    from backend.app.models.motor import MotorStatus
    from backend.app.models.motor_event import MotorEventType


class MotorStateEvent(str, enum.Enum):
    """Event triggers driving motor state transitions."""
    # Cloud Commands
    CMD_START = "CMD_START"
    CMD_STOP = "CMD_STOP"
    CMD_RESET = "CMD_RESET"
    CMD_EMERGENCY_STOP = "CMD_EMERGENCY_STOP"

    # Hardware Status Confirmations
    STATUS_STARTING = "STATUS_STARTING"
    STATUS_ON = "STATUS_ON"
    STATUS_STOPPING = "STATUS_STOPPING"
    STATUS_OFF = "STATUS_OFF"

    # Edge Safety & Faults
    SAFETY_TRIP = "SAFETY_TRIP"
    LOCAL_ESTOP = "LOCAL_ESTOP"
    STARTUP_FAILED = "STARTUP_FAILED"
    SHUTDOWN_FAILED = "SHUTDOWN_FAILED"

    # Connectivity / Heartbeat
    HEARTBEAT_TIMEOUT = "HEARTBEAT_TIMEOUT"
    HEARTBEAT_RESTORED = "HEARTBEAT_RESTORED"

    # Administrative Lockouts
    MAINTENANCE_LOCK = "MAINTENANCE_LOCK"
    MAINTENANCE_UNLOCK = "MAINTENANCE_UNLOCK"
    ADMIN_DISABLE = "ADMIN_DISABLE"
    ADMIN_ENABLE = "ADMIN_ENABLE"


class InvalidStateTransitionException(Exception):
    """Raised when an illegal or safety-violating state transition is attempted."""
    def __init__(self, current_state: MotorStatus, event: MotorStateEvent, reason: str):
        self.current_state = current_state
        self.event = event
        self.reason = reason
        super().__init__(
            f"Invalid motor transition from '{current_state.value}' via event '{event.value}': {reason}"
        )


@dataclass(frozen=True)
class TransitionResult:
    """Immutable result of a motor state transition evaluation."""
    current_state: MotorStatus
    next_state: MotorStatus
    event: MotorStateEvent
    reason: str
    event_type: Optional[MotorEventType]
    is_valid: bool
    error_message: Optional[str] = None


# Transition Precedence Order (Evaluation Priority):
# 1. EMERGENCY_STOP / LOCAL_ESTOP / SAFETY_TRIP (Edge Safety is absolute)
# 2. HEARTBEAT_TIMEOUT (Hardware unreachable)
# 3. MAINTENANCE_LOCK / ADMIN_DISABLE (Administrative Lockouts)
# 4. Normal Operational & Command Transitions


def transition_motor_state(
    current_state: Union[MotorStatus, str],
    event: Union[MotorStateEvent, str],
    context: Optional[Dict[str, Any]] = None
) -> TransitionResult:
    """
    Pure deterministic state-transition evaluation function.
    
    Evaluates current state against the event and operational context.
    Returns a TransitionResult describing next state, reason, domain MotorEventType, and validity.
    Does NOT raise exceptions — caller inspects result.is_valid or calls validate_and_transition().
    
    Context keys supported:
    - safety_latched (bool): Whether hardware/software safety trip remains latched.
    - active_safety_trip (bool): Whether a physical condition (turbidity, level, etc.) currently trips safety.
    - hardware_state (MotorStatus/str): Confirmed physical state during reconnect reconciliation.
    - is_reconciliation (bool): True if syncing after reconnect/cold-start.
    - error_message (str): Additional fault or failure context.
    """
    # Normalize inputs
    if isinstance(current_state, str):
        current_state = MotorStatus(current_state.upper())
    if isinstance(event, str):
        event = MotorStateEvent(event.upper())

    ctx = context or {}
    safety_latched = bool(ctx.get("safety_latched", False))
    active_safety_trip = bool(ctx.get("active_safety_trip", False))
    is_reconciliation = bool(ctx.get("is_reconciliation", False))

    # -------------------------------------------------------------------------
    # LEVEL 1 PRECEDENCE: EMERGENCY STOP & SAFETY TRIPS (Unconditional Fault)
    # -------------------------------------------------------------------------
    if event in (MotorStateEvent.CMD_EMERGENCY_STOP, MotorStateEvent.LOCAL_ESTOP):
        return TransitionResult(
            current_state=current_state,
            next_state=MotorStatus.FAULT,
            event=event,
            reason="Emergency stop triggered. Power de-energized and safety latched.",
            event_type=MotorEventType.EMERGENCY_STOP,
            is_valid=True
        )

    if event == MotorStateEvent.SAFETY_TRIP:
        reason = ctx.get("error_message") or "Edge safety trip interlock triggered."
        return TransitionResult(
            current_state=current_state,
            next_state=MotorStatus.FAULT,
            event=event,
            reason=reason,
            event_type=MotorEventType.FAULT,
            is_valid=True
        )

    # -------------------------------------------------------------------------
    # LEVEL 2 PRECEDENCE: HEARTBEAT TIMEOUT / OFFLINE
    # -------------------------------------------------------------------------
    if event == MotorStateEvent.HEARTBEAT_TIMEOUT:
        if current_state == MotorStatus.OFFLINE:
            return TransitionResult(
                current_state=current_state,
                next_state=MotorStatus.OFFLINE,
                event=event,
                reason="Controller already offline.",
                event_type=None,
                is_valid=True
            )
        return TransitionResult(
            current_state=current_state,
            next_state=MotorStatus.OFFLINE,
            event=event,
            reason="Controller heartbeat lost. Motor marked OFFLINE.",
            event_type=MotorEventType.OFFLINE,
            is_valid=True
        )

    # -------------------------------------------------------------------------
    # LEVEL 3 PRECEDENCE: ADMINISTRATIVE LOCKOUTS (MAINTENANCE & DISABLED)
    # -------------------------------------------------------------------------
    if event == MotorStateEvent.MAINTENANCE_LOCK:
        return TransitionResult(
            current_state=current_state,
            next_state=MotorStatus.MAINTENANCE,
            event=event,
            reason="Motor placed under maintenance lockout.",
            event_type=None,
            is_valid=True
        )

    if event == MotorStateEvent.ADMIN_DISABLE:
        return TransitionResult(
            current_state=current_state,
            next_state=MotorStatus.DISABLED,
            event=event,
            reason="Motor administratively disabled.",
            event_type=None,
            is_valid=True
        )

    # -------------------------------------------------------------------------
    # LEVEL 4: STATE-SPECIFIC TRANSITION RULES
    # -------------------------------------------------------------------------

    # --- STATE: OFF ---
    if current_state == MotorStatus.OFF:
        if event in (MotorStateEvent.CMD_START, MotorStateEvent.STATUS_STARTING):
            if active_safety_trip or safety_latched:
                return TransitionResult(
                    current_state=current_state,
                    next_state=current_state,
                    event=event,
                    reason="Cannot start: Active safety trip or latched safety interlock.",
                    event_type=None,
                    is_valid=False,
                    error_message="Active safety trip or latched safety interlock prevents startup."
                )
            return TransitionResult(
                current_state=current_state,
                next_state=MotorStatus.STARTING,
                event=event,
                reason="Start sequence initiated.",
                event_type=None,
                is_valid=True
            )
        if event == MotorStateEvent.STATUS_OFF:
            # Idempotent status confirmation
            return TransitionResult(
                current_state=current_state,
                next_state=MotorStatus.OFF,
                event=event,
                reason="Motor is confirmed OFF.",
                event_type=None,
                is_valid=True
            )
        if event == MotorStateEvent.STATUS_ON:
            if is_reconciliation:
                return TransitionResult(
                    current_state=current_state,
                    next_state=MotorStatus.ON,
                    event=event,
                    reason="Hardware state synchronized to ON during reconnect/audit.",
                    event_type=MotorEventType.STARTED,
                    is_valid=True
                )
            return TransitionResult(
                current_state=current_state,
                next_state=current_state,
                event=event,
                reason="Direct OFF -> ON transition without STARTING sequence is prohibited.",
                event_type=None,
                is_valid=False,
                error_message="Prohibited direct OFF -> ON transition without STARTING sequence."
            )
        if event == MotorStateEvent.CMD_STOP:
            # Idempotent stop request on already OFF motor
            return TransitionResult(
                current_state=current_state,
                next_state=MotorStatus.OFF,
                event=event,
                reason="Motor is already OFF.",
                event_type=None,
                is_valid=True
            )

    # --- STATE: STARTING ---
    elif current_state == MotorStatus.STARTING:
        if event == MotorStateEvent.STATUS_ON:
            return TransitionResult(
                current_state=current_state,
                next_state=MotorStatus.ON,
                event=event,
                reason="Hardware confirmed contactor closed and motor running.",
                event_type=MotorEventType.STARTED,
                is_valid=True
            )
        if event == MotorStateEvent.STARTUP_FAILED:
            return TransitionResult(
                current_state=current_state,
                next_state=MotorStatus.FAULT,
                event=event,
                reason=ctx.get("error_message") or "Motor startup sequence failed.",
                event_type=MotorEventType.FAULT,
                is_valid=True
            )
        if event in (MotorStateEvent.CMD_STOP, MotorStateEvent.STATUS_STOPPING):
            return TransitionResult(
                current_state=current_state,
                next_state=MotorStatus.STOPPING,
                event=event,
                reason="Stop requested during startup sequence.",
                event_type=None,
                is_valid=True
            )
        if event == MotorStateEvent.STATUS_OFF:
            # Hardware reported OFF during starting (e.g. startup aborted safely)
            return TransitionResult(
                current_state=current_state,
                next_state=MotorStatus.OFF,
                event=event,
                reason="Motor returned to OFF during startup.",
                event_type=MotorEventType.STOPPED,
                is_valid=True
            )
        if event == MotorStateEvent.STATUS_STARTING:
            # Idempotent in-flight startup
            return TransitionResult(
                current_state=current_state,
                next_state=MotorStatus.STARTING,
                event=event,
                reason="Startup sequence in progress.",
                event_type=None,
                is_valid=True
            )

    # --- STATE: ON ---
    elif current_state == MotorStatus.ON:
        if event in (MotorStateEvent.CMD_STOP, MotorStateEvent.STATUS_STOPPING):
            return TransitionResult(
                current_state=current_state,
                next_state=MotorStatus.STOPPING,
                event=event,
                reason="Stop sequence initiated.",
                event_type=None,
                is_valid=True
            )
        if event == MotorStateEvent.STATUS_ON:
            # Idempotent operating status
            return TransitionResult(
                current_state=current_state,
                next_state=MotorStatus.ON,
                event=event,
                reason="Motor operating normally.",
                event_type=None,
                is_valid=True
            )
        if event == MotorStateEvent.CMD_START:
            # Idempotent start request on already ON motor
            return TransitionResult(
                current_state=current_state,
                next_state=MotorStatus.ON,
                event=event,
                reason="Motor is already ON.",
                event_type=None,
                is_valid=True
            )
        if event == MotorStateEvent.STATUS_OFF:
            if is_reconciliation:
                return TransitionResult(
                    current_state=current_state,
                    next_state=MotorStatus.OFF,
                    event=event,
                    reason="Hardware state synchronized to OFF during reconnect/audit.",
                    event_type=MotorEventType.STOPPED,
                    is_valid=True
                )
            # Unexpected shutdown detected -> transition to OFF
            return TransitionResult(
                current_state=current_state,
                next_state=MotorStatus.OFF,
                event=event,
                reason="Contactor de-energized (hardware reported OFF).",
                event_type=MotorEventType.STOPPED,
                is_valid=True
            )

    # --- STATE: STOPPING ---
    elif current_state == MotorStatus.STOPPING:
        if event == MotorStateEvent.STATUS_OFF:
            return TransitionResult(
                current_state=current_state,
                next_state=MotorStatus.OFF,
                event=event,
                reason="Hardware confirmed contactor open and motor stopped.",
                event_type=MotorEventType.STOPPED,
                is_valid=True
            )
        if event == MotorStateEvent.SHUTDOWN_FAILED:
            return TransitionResult(
                current_state=current_state,
                next_state=MotorStatus.FAULT,
                event=event,
                reason=ctx.get("error_message") or "Motor shutdown sequence failed.",
                event_type=MotorEventType.FAULT,
                is_valid=True
            )
        if event == MotorStateEvent.STATUS_STOPPING:
            # Idempotent in-flight stopping
            return TransitionResult(
                current_state=current_state,
                next_state=MotorStatus.STOPPING,
                event=event,
                reason="Stop sequence in progress.",
                event_type=None,
                is_valid=True
            )

    # --- STATE: FAULT ---
    elif current_state == MotorStatus.FAULT:
        if event == MotorStateEvent.CMD_RESET:
            if active_safety_trip or safety_latched:
                return TransitionResult(
                    current_state=current_state,
                    next_state=MotorStatus.FAULT,
                    event=event,
                    reason="Cannot RESET: Safety condition is active or safety latch is not cleared locally.",
                    event_type=None,
                    is_valid=False,
                    error_message="Cannot RESET motor while physical safety condition is active or latch remains set."
                )
            return TransitionResult(
                current_state=current_state,
                next_state=MotorStatus.OFF,
                event=event,
                reason="Fault cleared and safety latch reset. Motor returned to ready standby (OFF).",
                event_type=MotorEventType.RESET,
                is_valid=True
            )
        if event == MotorStateEvent.STATUS_OFF and is_reconciliation:
            return TransitionResult(
                current_state=current_state,
                next_state=MotorStatus.OFF,
                event=event,
                reason="Hardware reported fault cleared locally and contactor de-energized (OFF).",
                event_type=MotorEventType.RESET,
                is_valid=True
            )
        if event in (MotorStateEvent.CMD_START, MotorStateEvent.STATUS_STARTING, MotorStateEvent.STATUS_ON):
            return TransitionResult(
                current_state=current_state,
                next_state=MotorStatus.FAULT,
                event=event,
                reason="Cannot START motor in FAULT state without an approved RESET sequence.",
                event_type=None,
                is_valid=False,
                error_message="Motor in FAULT state cannot be started without clearing safety interlocks."
            )

    # --- STATE: MAINTENANCE ---
    elif current_state == MotorStatus.MAINTENANCE:
        if event == MotorStateEvent.MAINTENANCE_UNLOCK:
            return TransitionResult(
                current_state=current_state,
                next_state=MotorStatus.OFF,
                event=event,
                reason="Maintenance lockout cleared. Motor returned to ready standby (OFF).",
                event_type=None,
                is_valid=True
            )
        if event in (MotorStateEvent.CMD_START, MotorStateEvent.STATUS_STARTING):
            return TransitionResult(
                current_state=current_state,
                next_state=MotorStatus.MAINTENANCE,
                event=event,
                reason="Cannot start motor under MAINTENANCE lockout.",
                event_type=None,
                is_valid=False,
                error_message="Motor is locked under MAINTENANCE."
            )

    # --- STATE: DISABLED ---
    elif current_state == MotorStatus.DISABLED:
        if event == MotorStateEvent.ADMIN_ENABLE:
            return TransitionResult(
                current_state=current_state,
                next_state=MotorStatus.OFF,
                event=event,
                reason="Motor administratively re-enabled into ready standby (OFF).",
                event_type=None,
                is_valid=True
            )
        if event in (MotorStateEvent.CMD_START, MotorStateEvent.STATUS_STARTING):
            return TransitionResult(
                current_state=current_state,
                next_state=MotorStatus.DISABLED,
                event=event,
                reason="Cannot start motor while administratively DISABLED.",
                event_type=None,
                is_valid=False,
                error_message="Motor is DISABLED."
            )

    # --- STATE: OFFLINE ---
    elif current_state == MotorStatus.OFFLINE:
        if event == MotorStateEvent.HEARTBEAT_RESTORED:
            # Reconcile with hardware reported state if provided, otherwise default to OFF
            hw_state = ctx.get("hardware_state")
            target_state = MotorStatus.OFF
            if hw_state is not None:
                if isinstance(hw_state, str):
                    hw_state = MotorStatus(hw_state.upper())
                if hw_state in (MotorStatus.OFF, MotorStatus.ON, MotorStatus.FAULT):
                    target_state = hw_state

            return TransitionResult(
                current_state=current_state,
                next_state=target_state,
                event=event,
                reason=f"Controller heartbeat restored. Motor synchronized to {target_state.value}.",
                event_type=MotorEventType.ONLINE,
                is_valid=True
            )
        if event in (MotorStateEvent.CMD_START, MotorStateEvent.STATUS_STARTING):
            return TransitionResult(
                current_state=current_state,
                next_state=MotorStatus.OFFLINE,
                event=event,
                reason="Cannot start OFFLINE motor. Hardware is unreachable.",
                event_type=None,
                is_valid=False,
                error_message="Motor is OFFLINE."
            )

    # Fallback: Undefined / Illegal transition
    return TransitionResult(
        current_state=current_state,
        next_state=current_state,
        event=event,
        reason=f"Transition from {current_state.value} via event {event.value} is not permitted.",
        event_type=None,
        is_valid=False,
        error_message=f"Illegal transition: {current_state.value} + {event.value}"
    )


def validate_and_transition(
    current_state: Union[MotorStatus, str],
    event: Union[MotorStateEvent, str],
    context: Optional[Dict[str, Any]] = None
) -> TransitionResult:
    """
    Evaluates state transition and raises InvalidStateTransitionException if the transition is invalid.
    Use this helper in API and service layers where invalid transitions must halt execution.
    """
    result = transition_motor_state(current_state, event, context)
    if not result.is_valid:
        raise InvalidStateTransitionException(
            current_state=result.current_state,
            event=result.event,
            reason=result.error_message or result.reason
        )
    return result


def ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Ensures a datetime is timezone-aware in UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def parse_payload_timestamp(payload: Any, fallback: Optional[datetime] = None) -> datetime:
    """
    Extracts and parses UTC ISO timestamp or epoch from an incoming MQTT/event payload.
    Defaults to datetime.now(timezone.utc) if missing, None, or unparseable.
    """
    now = fallback or datetime.now(timezone.utc)
    if not isinstance(payload, dict):
        return now

    raw_ts = payload.get("timestamp") or payload.get("occurred_at") or payload.get("time")
    if not raw_ts:
        return now

    if isinstance(raw_ts, datetime):
        return ensure_utc(raw_ts)

    if isinstance(raw_ts, (int, float)):
        try:
            return datetime.fromtimestamp(raw_ts, tz=timezone.utc)
        except (ValueError, OSError):
            return now

    if isinstance(raw_ts, str):
        try:
            # Handle ISO string (e.g. 2026-10-06T08:30:00Z or +00:00)
            cleaned = raw_ts.replace("Z", "+00:00")
            dt = datetime.fromisoformat(cleaned)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except (ValueError, TypeError):
            return now

    return now


def is_stale_message(
    payload_timestamp: datetime,
    last_known_timestamp: Optional[datetime],
    tolerance_seconds: float = 2.0
) -> bool:
    """
    Determines if an incoming message timestamp is strictly older than the last known state timestamp.
    Applies a small tolerance for minor network jitter/clock skew.
    """
    if last_known_timestamp is None:
        return False

    if payload_timestamp.tzinfo is None:
        payload_timestamp = payload_timestamp.replace(tzinfo=timezone.utc)
    if last_known_timestamp.tzinfo is None:
        last_known_timestamp = last_known_timestamp.replace(tzinfo=timezone.utc)

    # If payload is older than last_known by more than tolerance_seconds, it is stale
    return (last_known_timestamp - payload_timestamp).total_seconds() > tolerance_seconds

