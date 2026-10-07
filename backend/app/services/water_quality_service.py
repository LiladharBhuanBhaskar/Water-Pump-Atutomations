"""
HydraControl — Water Quality Domain Service (Phase 13 / P13-T01)
Provides deterministic evaluation for water turbidity (NTU) and pH levels,
enforcing authoritative safety limits (Turbidity > 25 NTU, pH 6.5 - 8.5).
"""
from dataclasses import dataclass, field
from enum import Enum
import math
from typing import Optional, Dict, Any, Tuple


HARD_MAX_TURBIDITY_NTU = 25.0
DEFAULT_POTABLE_TURBIDITY_THRESHOLD_NTU = 5.0

PH_MIN_SAFE = 6.5
PH_MAX_SAFE = 8.5


class WaterQualityState(str, Enum):
    SAFE = "SAFE"
    WARNING = "WARNING"
    UNSAFE = "UNSAFE"
    INVALID = "INVALID"


WaterQualityStatus = WaterQualityState



class TurbidityClarityTier(str, Enum):
    CRYSTAL_CLEAR = "CRYSTAL_CLEAR"    # 0 - 1 NTU
    ACCEPTABLE = "ACCEPTABLE"          # 1 - 5 NTU
    SLIGHTLY_TURBID = "SLIGHTLY_TURBID"# 5 - 25 NTU (usable for non-potable / warning)
    HEAVILY_CONTAMINATED = "HEAVILY_CONTAMINATED" # > 25 NTU (HARD SAFETY TRIP)


class pHState(str, Enum):
    OPTIMAL = "OPTIMAL"      # 6.5 - 8.5
    ACIDIC = "ACIDIC"        # < 6.5
    ALKALINE = "ALKALINE"    # > 8.5
    INVALID = "INVALID"


@dataclass(frozen=True)
class TurbidityEvaluation:
    """Evaluation result for a water turbidity reading."""
    is_safe: bool
    state: WaterQualityState
    clarity_tier: TurbidityClarityTier
    ntu_value: float
    hard_cutoff_exceeded: bool
    station_threshold_exceeded: bool
    message: str
    trip_reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class pHEvaluation:
    """Evaluation result for a water pH reading."""
    is_safe: bool
    state: pHState
    ph_value: float
    message: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WaterQualityEvaluation:
    """Combined evaluation for multi-parameter water quality analysis."""
    is_overall_safe: bool
    turbidity_eval: TurbidityEvaluation
    ph_eval: Optional[pHEvaluation] = None
    summary_message: str = ""


def evaluate_turbidity(
    turbidity_ntu: float,
    station_threshold_ntu: Optional[float] = None
) -> TurbidityEvaluation:
    """
    Evaluates turbidity against authoritative hard safety limit (25 NTU)
    and optional station-configured threshold (e.g. 5 NTU).
    """
    if turbidity_ntu is None or math.isnan(turbidity_ntu) or math.isinf(turbidity_ntu):
        return TurbidityEvaluation(
            is_safe=False,
            state=WaterQualityState.INVALID,
            clarity_tier=TurbidityClarityTier.HEAVILY_CONTAMINATED,
            ntu_value=0.0,
            hard_cutoff_exceeded=True,
            station_threshold_exceeded=True,
            message="Invalid turbidity reading: value must be a valid finite number.",
            trip_reason="INVALID_VALUE"
        )

    if turbidity_ntu < 0:
        return TurbidityEvaluation(
            is_safe=False,
            state=WaterQualityState.INVALID,
            clarity_tier=TurbidityClarityTier.HEAVILY_CONTAMINATED,
            ntu_value=float(turbidity_ntu),
            hard_cutoff_exceeded=True,
            station_threshold_exceeded=True,
            message=f"Invalid turbidity reading: {turbidity_ntu} NTU cannot be negative.",
            trip_reason="NEGATIVE_VALUE"
        )

    ntu = float(turbidity_ntu)
    station_limit = station_threshold_ntu if station_threshold_ntu is not None else DEFAULT_POTABLE_TURBIDITY_THRESHOLD_NTU

    # Determine clarity tier
    if ntu <= 1.0:
        tier = TurbidityClarityTier.CRYSTAL_CLEAR
    elif ntu <= 5.0:
        tier = TurbidityClarityTier.ACCEPTABLE
    elif ntu <= HARD_MAX_TURBIDITY_NTU:
        tier = TurbidityClarityTier.SLIGHTLY_TURBID
    else:
        tier = TurbidityClarityTier.HEAVILY_CONTAMINATED

    # Check Hard Safety Threshold (> 25 NTU)
    if ntu > HARD_MAX_TURBIDITY_NTU:
        return TurbidityEvaluation(
            is_safe=False,
            state=WaterQualityState.UNSAFE,
            clarity_tier=tier,
            ntu_value=ntu,
            hard_cutoff_exceeded=True,
            station_threshold_exceeded=True,
            message=f"CRITICAL CONTAMINATION: Turbidity ({ntu:.2f} NTU) exceeds hard safety cutoff limit ({HARD_MAX_TURBIDITY_NTU:.1f} NTU).",
            trip_reason="HARD_TURBIDITY_CUTOFF",
            metadata={"hard_limit_ntu": HARD_MAX_TURBIDITY_NTU, "station_limit_ntu": station_limit}
        )

    # Check Station Desired Threshold (e.g. > 5 NTU)
    if ntu > station_limit:
        return TurbidityEvaluation(
            is_safe=True,  # Safe from hardware damage / emergency lockout, but triggers warning
            state=WaterQualityState.WARNING,
            clarity_tier=tier,
            ntu_value=ntu,
            hard_cutoff_exceeded=False,
            station_threshold_exceeded=True,
            message=f"Turbidity ({ntu:.2f} NTU) exceeds station quality threshold ({station_limit:.1f} NTU).",
            trip_reason=None,
            metadata={"hard_limit_ntu": HARD_MAX_TURBIDITY_NTU, "station_limit_ntu": station_limit}
        )

    return TurbidityEvaluation(
        is_safe=True,
        state=WaterQualityState.SAFE,
        clarity_tier=tier,
        ntu_value=ntu,
        hard_cutoff_exceeded=False,
        station_threshold_exceeded=False,
        message=f"Water turbidity ({ntu:.2f} NTU) is clean and within acceptable quality limits.",
        trip_reason=None,
        metadata={"hard_limit_ntu": HARD_MAX_TURBIDITY_NTU, "station_limit_ntu": station_limit}
    )


def evaluate_ph(ph_value: float) -> pHEvaluation:
    """
    Evaluates water pH value against standard safe potable band [6.5, 8.5].
    """
    if ph_value is None or math.isnan(ph_value) or math.isinf(ph_value):
        return pHEvaluation(
            is_safe=False,
            state=pHState.INVALID,
            ph_value=0.0,
            message="Invalid pH reading: value must be a valid finite number."
        )

    if ph_value < 0 or ph_value > 14:
        return pHEvaluation(
            is_safe=False,
            state=pHState.INVALID,
            ph_value=float(ph_value),
            message=f"Invalid pH reading: {ph_value} is outside pH scale [0, 14]."
        )

    ph = float(ph_value)
    if ph < PH_MIN_SAFE:
        return pHEvaluation(
            is_safe=False,
            state=pHState.ACIDIC,
            ph_value=ph,
            message=f"Water is acidic (pH {ph:.2f} < {PH_MIN_SAFE}). May cause pipe corrosion.",
            metadata={"safe_range": [PH_MIN_SAFE, PH_MAX_SAFE]}
        )
    elif ph > PH_MAX_SAFE:
        return pHEvaluation(
            is_safe=False,
            state=pHState.ALKALINE,
            ph_value=ph,
            message=f"Water is alkaline (pH {ph:.2f} > {PH_MAX_SAFE}). Potential scaling risk.",
            metadata={"safe_range": [PH_MIN_SAFE, PH_MAX_SAFE]}
        )

    return pHEvaluation(
        is_safe=True,
        state=pHState.OPTIMAL,
        ph_value=ph,
        message=f"Water pH ({ph:.2f}) is in optimal neutral range [{PH_MIN_SAFE}, {PH_MAX_SAFE}].",
        metadata={"safe_range": [PH_MIN_SAFE, PH_MAX_SAFE]}
    )


def evaluate_water_quality(
    turbidity_ntu: float,
    ph_value: Optional[float] = None,
    station_threshold_ntu: Optional[float] = None
) -> WaterQualityEvaluation:
    """
    Unified multi-parameter water quality evaluation.
    """
    t_eval = evaluate_turbidity(turbidity_ntu, station_threshold_ntu)
    p_eval = evaluate_ph(ph_value) if ph_value is not None else None

    is_overall_safe = t_eval.is_safe and (p_eval.is_safe if p_eval else True)

    messages = [t_eval.message]
    if p_eval:
        messages.append(p_eval.message)

    return WaterQualityEvaluation(
        is_overall_safe=is_overall_safe,
        turbidity_eval=t_eval,
        ph_eval=p_eval,
        summary_message=" | ".join(messages)
    )


class WaterQualityService:
    """Domain service class wrapper for water quality operations."""
    evaluate_turbidity = staticmethod(evaluate_turbidity)
    evaluate_ph = staticmethod(evaluate_ph)
    evaluate_water_quality = staticmethod(evaluate_water_quality)

