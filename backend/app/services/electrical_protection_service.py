"""Electrical load and protection domain service for HydraControl (Phase 15 - Wave 1).

Provides pure, deterministic calculations for:
- Electrical load assessment (Current in A, Voltage in V, Power in kW, Load %)
- Overcurrent / locked-rotor detection
- Undercurrent / dry-run/uncoupled motor detection
- Undervoltage & overvoltage protection
- Power estimation with optional power factor
"""

import math
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, Any


class ElectricalSafetyStatus(str, Enum):
    NORMAL = "NORMAL"
    OVERCURRENT = "OVERCURRENT"
    UNDERCURRENT = "UNDERCURRENT"
    UNDERVOLTAGE = "UNDERVOLTAGE"
    OVERVOLTAGE = "OVERVOLTAGE"
    INVALID = "INVALID"


@dataclass(frozen=True)
class ElectricalMetrics:
    current_a: float
    voltage_v: float
    power_kw: float
    load_percentage: float
    is_power_factor_estimated: bool
    power_factor: float


@dataclass(frozen=True)
class ElectricalSafetyEvaluation:
    status: ElectricalSafetyStatus
    is_safe: bool
    should_trip: bool
    trip_reason: Optional[str]
    metrics: Optional[ElectricalMetrics]
    details: Dict[str, Any]


class ElectricalProtectionService:
    """Domain service for electrical load and motor safety evaluation."""

    DEFAULT_MIN_VOLTAGE_V = 180.0  # Single-phase nominal 230V lower limit
    DEFAULT_MAX_VOLTAGE_V = 260.0  # Single-phase nominal 230V upper limit
    DEFAULT_POWER_FACTOR = 0.85
    DEFAULT_OVERCURRENT_THRESHOLD_A = 12.0
    DEFAULT_UNDERCURRENT_THRESHOLD_A = 2.0

    @staticmethod
    def calculate_power_kw(
        current_a: float,
        voltage_v: float,
        power_factor: Optional[float] = None,
        is_three_phase: bool = False,
    ) -> tuple[float, bool, float]:
        """Calculates electrical power in kW.
        
        Returns:
            (power_kw, is_power_factor_estimated, effective_pf)
        """
        if current_a < 0 or voltage_v < 0:
            raise ValueError(f"Current ({current_a}A) and voltage ({voltage_v}V) must be non-negative.")

        is_estimated = power_factor is None
        pf = power_factor if power_factor is not None else ElectricalProtectionService.DEFAULT_POWER_FACTOR

        if not (0.0 <= pf <= 1.0):
            raise ValueError(f"Power factor must be between 0.0 and 1.0, got {pf}")

        if is_three_phase:
            power_w = math.sqrt(3) * voltage_v * current_a * pf
        else:
            power_w = voltage_v * current_a * pf

        power_kw = round(power_w / 1000.0, 3)
        return power_kw, is_estimated, pf

    @staticmethod
    def calculate_load_percentage(
        current_a: float,
        rated_current_a: Optional[float] = None,
        power_kw: Optional[float] = None,
        rated_power_kw: Optional[float] = None,
    ) -> float:
        """Calculates motor load percentage based on rated current or rated power."""
        if current_a < 0:
            raise ValueError("Current cannot be negative")

        if rated_current_a is not None and rated_current_a > 0:
            return round((current_a / rated_current_a) * 100.0, 1)

        if power_kw is not None and rated_power_kw is not None and rated_power_kw > 0:
            return round((power_kw / rated_power_kw) * 100.0, 1)

        # Fallback approximation if 12A nominal reference
        return round((current_a / 10.0) * 100.0, 1)

    @classmethod
    def evaluate_electrical_safety(
        cls,
        current_a: Optional[float],
        voltage_v: Optional[float],
        motor_is_running: bool,
        rated_power_kw: Optional[float] = None,
        rated_current_a: Optional[float] = None,
        max_current_threshold_a: Optional[float] = None,
        min_current_running_threshold_a: Optional[float] = None,
        min_voltage_v: float = DEFAULT_MIN_VOLTAGE_V,
        max_voltage_v: float = DEFAULT_MAX_VOLTAGE_V,
        power_factor: Optional[float] = None,
        is_three_phase: bool = False,
    ) -> ElectricalSafetyEvaluation:
        """Evaluates electrical telemetry against safety thresholds."""
        # 1. Check for missing or invalid values
        if current_a is None or voltage_v is None:
            return ElectricalSafetyEvaluation(
                status=ElectricalSafetyStatus.INVALID,
                is_safe=False,
                should_trip=False,
                trip_reason="Missing electrical telemetry (current or voltage)",
                metrics=None,
                details={"error": "Missing current or voltage"},
            )

        if current_a < 0 or voltage_v < 0:
            return ElectricalSafetyEvaluation(
                status=ElectricalSafetyStatus.INVALID,
                is_safe=False,
                should_trip=False,
                trip_reason=f"Invalid negative electrical telemetry: {current_a}A, {voltage_v}V",
                metrics=None,
                details={"current_a": current_a, "voltage_v": voltage_v},
            )

        # 2. Derive metrics
        try:
            power_kw, is_pf_estimated, pf = cls.calculate_power_kw(
                current_a=current_a,
                voltage_v=voltage_v,
                power_factor=power_factor,
                is_three_phase=is_three_phase,
            )
            load_pct = cls.calculate_load_percentage(
                current_a=current_a,
                rated_current_a=rated_current_a,
                power_kw=power_kw,
                rated_power_kw=rated_power_kw,
            )
            metrics = ElectricalMetrics(
                current_a=current_a,
                voltage_v=voltage_v,
                power_kw=power_kw,
                load_percentage=load_pct,
                is_power_factor_estimated=is_pf_estimated,
                power_factor=pf,
            )
        except Exception as e:
            return ElectricalSafetyEvaluation(
                status=ElectricalSafetyStatus.INVALID,
                is_safe=False,
                should_trip=False,
                trip_reason=f"Error computing electrical metrics: {str(e)}",
                metrics=None,
                details={"error": str(e)},
            )

        # 3. Voltage Safety Checks (Applies whether motor is running or in standby)
        if voltage_v < min_voltage_v:
            return ElectricalSafetyEvaluation(
                status=ElectricalSafetyStatus.UNDERVOLTAGE,
                is_safe=False,
                should_trip=motor_is_running,
                trip_reason=f"Grid undervoltage detected: {voltage_v}V < {min_voltage_v}V min threshold",
                metrics=metrics,
                details={"voltage_v": voltage_v, "min_voltage_v": min_voltage_v},
            )

        if voltage_v > max_voltage_v:
            return ElectricalSafetyEvaluation(
                status=ElectricalSafetyStatus.OVERVOLTAGE,
                is_safe=False,
                should_trip=motor_is_running,
                trip_reason=f"Grid overvoltage detected: {voltage_v}V > {max_voltage_v}V max threshold",
                metrics=metrics,
                details={"voltage_v": voltage_v, "max_voltage_v": max_voltage_v},
            )

        # 4. Current Safety Checks (Only relevant when motor is running)
        if motor_is_running:
            overcurrent_limit = (
                max_current_threshold_a
                if max_current_threshold_a is not None
                else (rated_current_a * 1.25 if rated_current_a else cls.DEFAULT_OVERCURRENT_THRESHOLD_A)
            )

            undercurrent_limit = (
                min_current_running_threshold_a
                if min_current_running_threshold_a is not None
                else cls.DEFAULT_UNDERCURRENT_THRESHOLD_A
            )

            if current_a > overcurrent_limit:
                return ElectricalSafetyEvaluation(
                    status=ElectricalSafetyStatus.OVERCURRENT,
                    is_safe=False,
                    should_trip=True,
                    trip_reason=f"Overcurrent detected: {current_a}A exceeds limit {overcurrent_limit}A (Locked Rotor / Overload)",
                    metrics=metrics,
                    details={"current_a": current_a, "limit_a": overcurrent_limit},
                )

            if current_a < undercurrent_limit:
                return ElectricalSafetyEvaluation(
                    status=ElectricalSafetyStatus.UNDERCURRENT,
                    is_safe=False,
                    should_trip=True,
                    trip_reason=f"Undercurrent detected while running: {current_a}A below {undercurrent_limit}A (Dry-Run / Uncoupled)",
                    metrics=metrics,
                    details={"current_a": current_a, "limit_a": undercurrent_limit},
                )

        return ElectricalSafetyEvaluation(
            status=ElectricalSafetyStatus.NORMAL,
            is_safe=True,
            should_trip=False,
            trip_reason=None,
            metrics=metrics,
            details={"status": "Optimal electrical operation"},
        )
