"""
Unit tests for Tank Safety & Level Domain Service (Phase 12 / P12-T01).
Tests overhead full cutoff, source tank depletion dry-run protection,
geometry calculations, unit conversions, and validation boundaries.
"""
import pytest
import math
from app.services.tank_safety_service import (
    TankType,
    TankGeometryShape,
    TankGeometry,
    TankSafetyState,
    calculate_tank_percentage,
    evaluate_tank_safety,
    DEFAULT_OVERHEAD_FULL_THRESHOLD_PCT,
    DEFAULT_SOURCE_DEPLETED_THRESHOLD_PCT
)


def test_tank_geometry_creation_and_capacity():
    # Cylindrical tank: radius 1m, height 2m -> V = pi * 1^2 * 2 = 2pi m3 ~ 6283.185 L
    cyl = TankGeometry(
        shape=TankGeometryShape.CYLINDRICAL_VERTICAL,
        total_height_m=2.0,
        radius_m=1.0
    )
    expected_liters = math.pi * 1.0 * 2.0 * 1000.0
    assert cyl.total_capacity_liters == pytest.approx(expected_liters, 0.01)

    # Diameter test
    cyl_diam = TankGeometry(
        shape=TankGeometryShape.CYLINDRICAL_VERTICAL,
        total_height_m=2.0,
        diameter_m=2.0
    )
    assert cyl_diam.radius_m == 1.0
    assert cyl_diam.total_capacity_liters == pytest.approx(expected_liters, 0.01)

    # Rectangular tank: length 2m, width 1.5m, height 3m -> V = 9 m3 -> 9000 L
    rect = TankGeometry(
        shape=TankGeometryShape.RECTANGULAR,
        total_height_m=3.0,
        length_m=2.0,
        width_m=1.5
    )
    assert rect.total_capacity_liters == pytest.approx(9000.0, 0.01)


def test_tank_geometry_invalid_dimensions():
    with pytest.raises(ValueError, match="total_height_m must be strictly greater than 0"):
        TankGeometry(shape=TankGeometryShape.CYLINDRICAL_VERTICAL, total_height_m=0.0, radius_m=1.0)

    with pytest.raises(ValueError, match="requires valid positive radius_m or diameter_m"):
        TankGeometry(shape=TankGeometryShape.CYLINDRICAL_VERTICAL, total_height_m=2.0, radius_m=-1.0)

    with pytest.raises(ValueError, match="requires valid positive length_m and width_m"):
        TankGeometry(shape=TankGeometryShape.RECTANGULAR, total_height_m=2.0, length_m=0.0, width_m=1.0)


def test_calculate_tank_percentage_direct_percent():
    # Valid percentages
    assert calculate_tank_percentage(0.0, "%") == (True, 0.0, None)
    assert calculate_tank_percentage(50.0, "percent") == (True, 50.0, None)
    assert calculate_tank_percentage(100.0, "pct") == (True, 100.0, None)

    # Out of bounds percentages
    is_valid, val, err = calculate_tank_percentage(-5.0, "%")
    assert not is_valid
    assert "out of valid [0, 100] bounds" in err

    is_valid, val, err = calculate_tank_percentage(105.0, "%")
    assert not is_valid
    assert "out of valid [0, 100] bounds" in err


def test_calculate_tank_percentage_unit_conversions():
    # 2.0m high tank, 2000L capacity
    rect = TankGeometry(shape=TankGeometryShape.RECTANGULAR, total_height_m=2.0, length_m=1.0, width_m=1.0)
    # Total capacity = 1 * 1 * 2 * 1000 = 2000 L

    # Height in meters: 1.0m / 2.0m = 50.0%
    is_valid, pct, _ = calculate_tank_percentage(1.0, "m", rect)
    assert is_valid
    assert pct == pytest.approx(50.0, 0.01)

    # Height in cm: 150cm / 2.0m = 75.0%
    is_valid, pct, _ = calculate_tank_percentage(150.0, "cm", rect)
    assert is_valid
    assert pct == pytest.approx(75.0, 0.01)

    # Height in mm: 500mm / 2.0m = 25.0%
    is_valid, pct, _ = calculate_tank_percentage(500.0, "mm", rect)
    assert is_valid
    assert pct == pytest.approx(25.0, 0.01)

    # Volume in Liters: 1000 L / 2000 L = 50.0%
    is_valid, pct, _ = calculate_tank_percentage(1000.0, "L", rect)
    assert is_valid
    assert pct == pytest.approx(50.0, 0.01)

    # Volume in m3: 1.5 m3 / 2.0 m3 = 75.0%
    is_valid, pct, _ = calculate_tank_percentage(1.5, "m3", rect)
    assert is_valid
    assert pct == pytest.approx(75.0, 0.01)

    # Missing geometry with unit
    is_valid, pct, err = calculate_tank_percentage(1.5, "m", None)
    assert not is_valid
    assert "Geometry configuration is required" in err


def test_evaluate_tank_safety_overhead_full_trip():
    # Overhead tank: >= 95% triggers HIGH_TRIP
    eval_94 = evaluate_tank_safety(94.9, "%", TankType.OVERHEAD)
    assert eval_94.is_safe is True
    assert eval_94.safety_state == TankSafetyState.NORMAL

    eval_95 = evaluate_tank_safety(95.0, "%", TankType.OVERHEAD)
    assert eval_95.is_safe is False
    assert eval_95.safety_state == TankSafetyState.HIGH_TRIP
    assert eval_95.trip_reason == "TANK_FULL"

    eval_98 = evaluate_tank_safety(98.5, "%", TankType.OVERHEAD)
    assert eval_98.is_safe is False
    assert eval_98.safety_state == TankSafetyState.HIGH_TRIP

    # Custom threshold (e.g. 90%)
    eval_custom = evaluate_tank_safety(91.0, "%", TankType.OVERHEAD, high_threshold_pct=90.0)
    assert eval_custom.is_safe is False
    assert eval_custom.safety_state == TankSafetyState.HIGH_TRIP


def test_evaluate_tank_safety_source_depleted_low_trip():
    # Source / Sump tank: <= 10% triggers LOW_TRIP
    eval_15 = evaluate_tank_safety(15.0, "%", TankType.SUMP)
    assert eval_15.is_safe is True
    assert eval_15.safety_state == TankSafetyState.NORMAL

    eval_10 = evaluate_tank_safety(10.0, "%", TankType.SUMP)
    assert eval_10.is_safe is False
    assert eval_10.safety_state == TankSafetyState.LOW_TRIP
    assert eval_10.trip_reason == "SOURCE_DEPLETED"

    eval_5 = evaluate_tank_safety(5.0, "%", TankType.SOURCE)
    assert eval_5.is_safe is False
    assert eval_5.safety_state == TankSafetyState.LOW_TRIP

    eval_0 = evaluate_tank_safety(0.0, "%", TankType.SOURCE)
    assert eval_0.is_safe is False
    assert eval_0.safety_state == TankSafetyState.LOW_TRIP


def test_evaluate_tank_safety_invalid_inputs():
    eval_nan = evaluate_tank_safety(float("nan"), "%", TankType.OVERHEAD)
    assert eval_nan.is_safe is False
    assert eval_nan.safety_state == TankSafetyState.INVALID

    eval_neg = evaluate_tank_safety(-10.0, "%", TankType.OVERHEAD)
    assert eval_neg.is_safe is False
    assert eval_neg.safety_state == TankSafetyState.INVALID
