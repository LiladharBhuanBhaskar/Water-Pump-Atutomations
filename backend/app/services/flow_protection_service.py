"""
HydraControl — Flow Protection Domain Service (Phase 14 / P14-T01)
Provides deterministic evaluation for pipe flow rates, startup grace-period priming,
dry-run no-flow detection, and pipe-burst / excessive flow protection.
"""
from dataclasses import dataclass, field
from enum import Enum
import math
from typing import Optional, Dict, Any, Tuple


DEFAULT_STARTUP_GRACE_PERIOD_SECONDS = 20.0
DEFAULT_MIN_FLOW_THRESHOLD_LPM = 1.0
DEFAULT_BURST_FLOW_THRESHOLD_LPM = 500.0

LPM_PER_M3_PER_HOUR = 1000.0 / 60.0 # 1 m3/h = 16.6667 L/min
LPM_PER_GPM = 3.78541               # 1 GPM = 3.78541 L/min


class FlowSafetyState(str, Enum):
    NORMAL = "NORMAL"
    STARTUP_PRIMING = "STARTUP_PRIMING"
    DRY_RUN_TRIP = "DRY_RUN_TRIP"
    PIPE_BURST_TRIP = "PIPE_BURST_TRIP"
    NO_FLOW_STANDBY = "NO_FLOW_STANDBY"
    INVALID = "INVALID"


FlowSafetyStatus = FlowSafetyState



@dataclass(frozen=True)
class FlowProtectionConfig:
    """Configurable flow protection thresholds for a motor / station."""
    startup_grace_period_seconds: float = DEFAULT_STARTUP_GRACE_PERIOD_SECONDS
    min_flow_threshold_lpm: float = DEFAULT_MIN_FLOW_THRESHOLD_LPM
    burst_flow_threshold_lpm: Optional[float] = DEFAULT_BURST_FLOW_THRESHOLD_LPM

    def __post_init__(self):
        if self.startup_grace_period_seconds < 0:
            raise ValueError("startup_grace_period_seconds cannot be negative.")
        if self.min_flow_threshold_lpm < 0:
            raise ValueError("min_flow_threshold_lpm cannot be negative.")
        if self.burst_flow_threshold_lpm is not None and self.burst_flow_threshold_lpm <= self.min_flow_threshold_lpm:
            raise ValueError("burst_flow_threshold_lpm must be greater than min_flow_threshold_lpm.")


@dataclass(frozen=True)
class FlowEvaluation:
    """Evaluation result of a flow rate reading."""
    is_safe: bool
    state: FlowSafetyState
    flow_lpm: float
    flow_m3_h: float
    flow_gpm: float
    message: str
    trip_reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


def normalize_flow_to_lpm(raw_value: float, unit: str) -> Tuple[bool, Optional[float], Optional[str]]:
    """
    Converts any supported flow unit into Liters per minute (L/min).
    Returns (is_valid, lpm_value, error_message).
    """
    if raw_value is None or math.isnan(raw_value) or math.isinf(raw_value):
        return False, None, "Flow reading must be a valid finite number."

    if raw_value < 0:
        return False, None, f"Flow reading {raw_value} cannot be negative."

    u = unit.strip().lower()
    val = float(raw_value)

    if u in ("l/min", "lpm", "liter/min", "liters/min", "litres/min"):
        return True, val, None
    elif u in ("m3/h", "m3/hr", "m3h", "cubic_meter_per_hour"):
        return True, val * LPM_PER_M3_PER_HOUR, None
    elif u in ("gpm", "gal/min", "gallons_per_minute"):
        return True, val * LPM_PER_GPM, None
    elif u in ("l/s", "lps", "liters_per_second"):
        return True, val * 60.0, None
    else:
        return False, None, f"Unsupported flow rate unit '{unit}'."


def evaluate_flow_safety(
    flow_value: float,
    unit: str = "L/min",
    motor_is_running: bool = False,
    running_seconds: float = 0.0,
    config: Optional[FlowProtectionConfig] = None
) -> FlowEvaluation:
    """
    Evaluates flow telemetry against dry-run and pipe-burst conditions.
    
    Rules:
    - If motor is OFF: Zero flow is normal (NO_FLOW_STANDBY).
    - If motor is ON and running_seconds < grace_period: Zero/low flow is allowed during priming (STARTUP_PRIMING).
    - If motor is ON and running_seconds >= grace_period and flow <= min_threshold: DRY_RUN_TRIP.
    - If motor is ON and burst_threshold configured and flow >= burst_threshold: PIPE_BURST_TRIP.
    """
    cfg = config or FlowProtectionConfig()
    is_valid, lpm, err = normalize_flow_to_lpm(flow_value, unit)

    if not is_valid or lpm is None:
        return FlowEvaluation(
            is_safe=False,
            state=FlowSafetyState.INVALID,
            flow_lpm=0.0,
            flow_m3_h=0.0,
            flow_gpm=0.0,
            message=f"Invalid flow rate measurement: {err}",
            trip_reason="INVALID_VALUE"
        )

    m3_h = lpm / LPM_PER_M3_PER_HOUR
    gpm = lpm / LPM_PER_GPM

    # Motor is OFF/Standby
    if not motor_is_running:
        if lpm > cfg.min_flow_threshold_lpm:
            # Gravity feed or backflow while stopped
            return FlowEvaluation(
                is_safe=True,
                state=FlowSafetyState.NORMAL,
                flow_lpm=lpm,
                flow_m3_h=m3_h,
                flow_gpm=gpm,
                message=f"Flow ({lpm:.1f} L/min) detected while motor is OFF (gravity / auxiliary feed).",
                metadata={"motor_running": False}
            )
        return FlowEvaluation(
            is_safe=True,
            state=FlowSafetyState.NO_FLOW_STANDBY,
            flow_lpm=lpm,
            flow_m3_h=m3_h,
            flow_gpm=gpm,
            message="No flow detected in standby state.",
            metadata={"motor_running": False}
        )

    # Motor is running
    # 1. Check Burst / Excessive Flow
    if cfg.burst_flow_threshold_lpm is not None and lpm >= cfg.burst_flow_threshold_lpm:
        return FlowEvaluation(
            is_safe=False,
            state=FlowSafetyState.PIPE_BURST_TRIP,
            flow_lpm=lpm,
            flow_m3_h=m3_h,
            flow_gpm=gpm,
            message=f"EXCESSIVE FLOW DETECTED: {lpm:.1f} L/min exceeds burst limit ({cfg.burst_flow_threshold_lpm:.1f} L/min). Potential pipe rupture.",
            trip_reason="PIPE_BURST",
            metadata={"burst_threshold_lpm": cfg.burst_flow_threshold_lpm}
        )

    # 2. Check Startup Grace Period
    if running_seconds < cfg.startup_grace_period_seconds:
        if lpm < cfg.min_flow_threshold_lpm:
            return FlowEvaluation(
                is_safe=True,
                state=FlowSafetyState.STARTUP_PRIMING,
                flow_lpm=lpm,
                flow_m3_h=m3_h,
                flow_gpm=gpm,
                message=f"Pump priming in progress ({running_seconds:.1f}s / {cfg.startup_grace_period_seconds:.1f}s grace period).",
                metadata={"running_seconds": running_seconds, "grace_period": cfg.startup_grace_period_seconds}
            )

    # 3. Check Dry Run (Grace period elapsed + Flow below minimum threshold)
    if lpm < cfg.min_flow_threshold_lpm:
        return FlowEvaluation(
            is_safe=False,
            state=FlowSafetyState.DRY_RUN_TRIP,
            flow_lpm=lpm,
            flow_m3_h=m3_h,
            flow_gpm=gpm,
            message=f"DRY RUN DETECTED: No water flow ({lpm:.2f} L/min) detected after {running_seconds:.1f}s runtime. Contactor trip required.",
            trip_reason="DRY_RUN",
            metadata={"running_seconds": running_seconds, "min_flow_lpm": cfg.min_flow_threshold_lpm}
        )

    # Normal pumping flow
    return FlowEvaluation(
        is_safe=True,
        state=FlowSafetyState.NORMAL,
        flow_lpm=lpm,
        flow_m3_h=m3_h,
        flow_gpm=gpm,
        message=f"Normal fluid delivery: {lpm:.1f} L/min ({m3_h:.2f} m³/h).",
        metadata={"motor_running": True, "running_seconds": running_seconds}
    )


class FlowProtectionService:
    """Domain service class wrapper for flow protection operations."""
    normalize_flow_to_lpm = staticmethod(normalize_flow_to_lpm)
    evaluate_flow_safety = staticmethod(evaluate_flow_safety)


