"""
HydraControl — Tank Safety & Level Domain Service (Phase 12)
Provides deterministic evaluation for overhead and source tank levels,
geometry calculations (volume, height, percentage), and safety trip thresholds.
"""
from dataclasses import dataclass, field
from enum import Enum
import math
from typing import Optional, Dict, Any, Tuple


class TankType(str, Enum):
    OVERHEAD = "OVERHEAD"
    SUMP = "SUMP"
    SOURCE = "SOURCE"
    STORAGE = "STORAGE"


class TankGeometryShape(str, Enum):
    CYLINDRICAL_VERTICAL = "CYLINDRICAL_VERTICAL"
    RECTANGULAR = "RECTANGULAR"


class TankSafetyState(str, Enum):
    NORMAL = "NORMAL"
    HIGH_TRIP = "HIGH_TRIP"
    LOW_TRIP = "LOW_TRIP"
    INVALID = "INVALID"


class TankLevelUnit(str, Enum):
    PERCENT = "%"
    METER = "m"
    CENTIMETER = "cm"
    MILLIMETER = "mm"
    LITER = "L"
    CUBIC_METER = "m3"
    GALLON = "gal"


DEFAULT_OVERHEAD_FULL_THRESHOLD_PCT = 95.0
DEFAULT_SOURCE_DEPLETED_THRESHOLD_PCT = 10.0
LITERS_PER_CUBIC_METER = 1000.0
LITERS_PER_GALLON = 3.78541


@dataclass(frozen=True)
class TankGeometry:
    """Represents physical dimensions of a water tank."""
    shape: TankGeometryShape
    total_height_m: float
    # Cylindrical parameters
    radius_m: Optional[float] = None
    diameter_m: Optional[float] = None
    # Rectangular parameters
    length_m: Optional[float] = None
    width_m: Optional[float] = None

    def __post_init__(self):
        if self.total_height_m <= 0:
            raise ValueError("Tank total_height_m must be strictly greater than 0.")
        
        if self.shape == TankGeometryShape.CYLINDRICAL_VERTICAL:
            r = self.radius_m
            if r is None and self.diameter_m is not None:
                r = self.diameter_m / 2.0
            if r is None or r <= 0:
                raise ValueError("Cylindrical tank requires valid positive radius_m or diameter_m.")
            object.__setattr__(self, "radius_m", r)
        elif self.shape == TankGeometryShape.RECTANGULAR:
            if not self.length_m or self.length_m <= 0 or not self.width_m or self.width_m <= 0:
                raise ValueError("Rectangular tank requires valid positive length_m and width_m.")

    @property
    def total_capacity_liters(self) -> float:
        """Calculates total maximum volume in liters."""
        if self.shape == TankGeometryShape.CYLINDRICAL_VERTICAL:
            volume_m3 = math.pi * (self.radius_m ** 2) * self.total_height_m
        else:
            volume_m3 = self.length_m * self.width_m * self.total_height_m
        return volume_m3 * LITERS_PER_CUBIC_METER


@dataclass(frozen=True)
class TankSafetyEvaluation:
    """Result of evaluating a tank level measurement against safety criteria."""
    is_safe: bool
    safety_state: TankSafetyState
    percentage: float
    height_m: Optional[float]
    volume_liters: Optional[float]
    message: str
    trip_reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


def calculate_tank_percentage(
    raw_value: float,
    unit: str,
    geometry: Optional[TankGeometry] = None
) -> Tuple[bool, Optional[float], Optional[str]]:
    """
    Normalizes any supported tank measurement unit to percentage (0 - 100%).
    Returns (is_valid, percentage_value, error_message).
    """
    if raw_value is None or math.isnan(raw_value) or math.isinf(raw_value):
        return False, None, "Level reading must be a valid finite number."

    u = unit.strip().lower()

    if u in ("%", "percent", "pct"):
        if raw_value < 0 or raw_value > 100:
            return False, None, f"Percentage reading {raw_value}% out of valid [0, 100] bounds."
        return True, float(raw_value), None

    if geometry is None:
        return False, None, f"Geometry configuration is required to convert '{unit}' to percentage."

    height_m: Optional[float] = None
    if u in ("m", "meter", "meters"):
        height_m = raw_value
    elif u in ("cm", "centimeter", "centimeters"):
        height_m = raw_value / 100.0
    elif u in ("mm", "millimeter", "millimeters"):
        height_m = raw_value / 1000.0
    elif u in ("l", "liter", "liters", "litres"):
        if raw_value < 0:
            return False, None, f"Volume reading {raw_value} L cannot be negative."
        pct = (raw_value / geometry.total_capacity_liters) * 100.0
        return True, min(max(pct, 0.0), 100.0), None
    elif u in ("m3", "cubic_meter"):
        liters = raw_value * LITERS_PER_CUBIC_METER
        pct = (liters / geometry.total_capacity_liters) * 100.0
        return True, min(max(pct, 0.0), 100.0), None
    elif u in ("gal", "gallon", "gallons"):
        liters = raw_value * LITERS_PER_GALLON
        pct = (liters / geometry.total_capacity_liters) * 100.0
        return True, min(max(pct, 0.0), 100.0), None
    else:
        return False, None, f"Unsupported tank level unit '{unit}'."

    if height_m is not None:
        if height_m < 0:
            return False, None, f"Height reading {height_m}m cannot be negative."
        pct = (height_m / geometry.total_height_m) * 100.0
        return True, min(max(pct, 0.0), 100.0), None

    return False, None, f"Unable to calculate percentage for unit '{unit}'."


def evaluate_tank_safety(
    level_value: float,
    unit: str = "%",
    tank_type: TankType = TankType.OVERHEAD,
    geometry: Optional[TankGeometry] = None,
    high_threshold_pct: Optional[float] = None,
    low_threshold_pct: Optional[float] = None,
    auto_stop_enabled: bool = True
) -> TankSafetyEvaluation:
    """
    Evaluates whether a tank level measurement is within safe operational limits.
    
    Standard Rules:
    - Overhead Tank: High Level Cutoff (>= 95% or station threshold) triggers HIGH_TRIP.
    - Sump / Source Tank: Low Level Cutoff (<= 10% or station threshold) triggers LOW_TRIP (Dry-run protection).
    """
    is_valid, pct, err = calculate_tank_percentage(level_value, unit, geometry)
    if not is_valid or pct is None:
        return TankSafetyEvaluation(
            is_safe=False,
            safety_state=TankSafetyState.INVALID,
            percentage=0.0,
            height_m=None,
            volume_liters=None,
            message=f"Invalid tank level measurement: {err}",
            trip_reason=err
        )

    # Calculate height and volume if geometry provided
    height_m = (pct / 100.0) * geometry.total_height_m if geometry else None
    liters = (pct / 100.0) * geometry.total_capacity_liters if geometry else None

    high_limit = high_threshold_pct if high_threshold_pct is not None else DEFAULT_OVERHEAD_FULL_THRESHOLD_PCT
    low_limit = low_threshold_pct if low_threshold_pct is not None else DEFAULT_SOURCE_DEPLETED_THRESHOLD_PCT

    # Overhead / Delivery Tank Evaluation
    if tank_type in (TankType.OVERHEAD, TankType.STORAGE):
        if auto_stop_enabled and pct >= high_limit:
            return TankSafetyEvaluation(
                is_safe=False,
                safety_state=TankSafetyState.HIGH_TRIP,
                percentage=pct,
                height_m=height_m,
                volume_liters=liters,
                message=f"Overhead tank level ({pct:.1f}%) reached or exceeded full cutoff threshold ({high_limit:.1f}%).",
                trip_reason="TANK_FULL",
                metadata={"high_threshold_pct": high_limit, "auto_stop_enabled": auto_stop_enabled}
            )

    # Sump / Source Tank Evaluation (Dry Run Source Protection)
    if tank_type in (TankType.SUMP, TankType.SOURCE):
        if pct <= low_limit:
            return TankSafetyEvaluation(
                is_safe=False,
                safety_state=TankSafetyState.LOW_TRIP,
                percentage=pct,
                height_m=height_m,
                volume_liters=liters,
                message=f"Source tank level ({pct:.1f}%) is at or below depletion dry-run threshold ({low_limit:.1f}%).",
                trip_reason="SOURCE_DEPLETED",
                metadata={"low_threshold_pct": low_limit}
            )

    return TankSafetyEvaluation(
        is_safe=True,
        safety_state=TankSafetyState.NORMAL,
        percentage=pct,
        height_m=height_m,
        volume_liters=liters,
        message=f"Tank level ({pct:.1f}%) within safe operating limits.",
        trip_reason=None,
        metadata={"tank_type": tank_type.value}
    )


TankSafetyStatus = TankSafetyState


class TankSafetyService:
    """Domain service class wrapper for tank safety operations."""
    evaluate_tank_safety = staticmethod(evaluate_tank_safety)
    calculate_tank_percentage = staticmethod(calculate_tank_percentage)


