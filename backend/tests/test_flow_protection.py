"""
Unit tests for Flow Protection & Dry-Run Domain Service (Phase 14 / P14-T01).
Tests normal flow, startup priming grace period, grace period expiry dry-run trip,
flow recovery, pipe burst excessive flow, and unit conversions.
"""
import pytest
from app.services.flow_protection_service import (
    FlowSafetyState,
    FlowProtectionConfig,
    normalize_flow_to_lpm,
    evaluate_flow_safety
)


def test_normalize_flow_units():
    # Direct L/min
    assert normalize_flow_to_lpm(120.0, "L/min") == (True, 120.0, None)
    assert normalize_flow_to_lpm(50.5, "lpm") == (True, 50.5, None)

    # m3/h: 6 m3/h = 6 * (1000 / 60) = 100 L/min
    is_valid, lpm, _ = normalize_flow_to_lpm(6.0, "m3/h")
    assert is_valid
    assert lpm == pytest.approx(100.0, 0.01)

    # GPM: 10 GPM = 10 * 3.78541 = 37.8541 L/min
    is_valid, lpm, _ = normalize_flow_to_lpm(10.0, "GPM")
    assert is_valid
    assert lpm == pytest.approx(37.8541, 0.01)

    # Negative flow
    is_valid, _, err = normalize_flow_to_lpm(-10.0, "L/min")
    assert not is_valid
    assert "cannot be negative" in err


def test_evaluate_flow_safety_motor_off_standby():
    # 0 flow when motor is off -> NO_FLOW_STANDBY (Safe)
    res_standby = evaluate_flow_safety(0.0, "L/min", motor_is_running=False)
    assert res_standby.is_safe is True
    assert res_standby.state == FlowSafetyState.NO_FLOW_STANDBY

    # Flow when motor is off -> Gravity feed / auxiliary
    res_gravity = evaluate_flow_safety(15.0, "L/min", motor_is_running=False)
    assert res_gravity.is_safe is True
    assert res_gravity.state == FlowSafetyState.NORMAL


def test_evaluate_flow_safety_startup_grace_period():
    cfg = FlowProtectionConfig(startup_grace_period_seconds=20.0, min_flow_threshold_lpm=1.0)

    # Motor ON for 5s (under 20s grace period) with 0 flow -> STARTUP_PRIMING (Safe)
    res_priming = evaluate_flow_safety(0.0, "L/min", motor_is_running=True, running_seconds=5.0, config=cfg)
    assert res_priming.is_safe is True
    assert res_priming.state == FlowSafetyState.STARTUP_PRIMING
    assert res_priming.trip_reason is None

    # Motor ON for 19.9s with 0.2 L/min -> Still within priming
    res_priming_late = evaluate_flow_safety(0.2, "L/min", motor_is_running=True, running_seconds=19.9, config=cfg)
    assert res_priming_late.is_safe is True
    assert res_priming_late.state == FlowSafetyState.STARTUP_PRIMING


def test_evaluate_flow_safety_dry_run_trip():
    cfg = FlowProtectionConfig(startup_grace_period_seconds=20.0, min_flow_threshold_lpm=1.0)

    # Motor ON for 25s (grace period elapsed) with 0.0 L/min -> DRY_RUN_TRIP (Unsafe)
    res_dry = evaluate_flow_safety(0.0, "L/min", motor_is_running=True, running_seconds=25.0, config=cfg)
    assert res_dry.is_safe is False
    assert res_dry.state == FlowSafetyState.DRY_RUN_TRIP
    assert res_dry.trip_reason == "DRY_RUN"

    # Motor ON for 60s with 0.5 L/min (< 1.0 threshold) -> DRY_RUN_TRIP
    res_low = evaluate_flow_safety(0.5, "L/min", motor_is_running=True, running_seconds=60.0, config=cfg)
    assert res_low.is_safe is False
    assert res_low.state == FlowSafetyState.DRY_RUN_TRIP


def test_evaluate_flow_safety_normal_pumping():
    cfg = FlowProtectionConfig(startup_grace_period_seconds=20.0, min_flow_threshold_lpm=1.0)

    # Motor ON for 30s with 85.0 L/min -> Normal pumping
    res_normal = evaluate_flow_safety(85.0, "L/min", motor_is_running=True, running_seconds=30.0, config=cfg)
    assert res_normal.is_safe is True
    assert res_normal.state == FlowSafetyState.NORMAL
    assert res_normal.flow_lpm == pytest.approx(85.0, 0.01)


def test_evaluate_flow_safety_pipe_burst():
    cfg = FlowProtectionConfig(burst_flow_threshold_lpm=300.0)

    # Flow reaches 350.0 L/min (exceeds 300 burst limit) -> PIPE_BURST_TRIP
    res_burst = evaluate_flow_safety(350.0, "L/min", motor_is_running=True, running_seconds=40.0, config=cfg)
    assert res_burst.is_safe is False
    assert res_burst.state == FlowSafetyState.PIPE_BURST_TRIP
    assert res_burst.trip_reason == "PIPE_BURST"
