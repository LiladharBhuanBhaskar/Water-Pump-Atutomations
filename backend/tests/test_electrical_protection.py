"""Unit tests for Electrical Protection & Load Domain Service (P15-T01)."""

import pytest
from app.services.electrical_protection_service import (
    ElectricalProtectionService,
    ElectricalSafetyStatus,
    ElectricalSafetyEvaluation,
    ElectricalMetrics,
)


def test_power_calculation():
    # 230V, 10A, default pf=0.85 -> 230 * 10 * 0.85 = 1955W = 1.955 kW
    power, is_estimated, pf = ElectricalProtectionService.calculate_power_kw(
        current_a=10.0,
        voltage_v=230.0,
        power_factor=None,
    )
    assert power == 1.955
    assert is_estimated is True
    assert pf == 0.85

    # With explicit pf=0.9
    power_explicit, is_est_2, pf_2 = ElectricalProtectionService.calculate_power_kw(
        current_a=10.0,
        voltage_v=230.0,
        power_factor=0.9,
    )
    assert power_explicit == 2.07
    assert is_est_2 is False
    assert pf_2 == 0.9

    # 3-phase calculation: sqrt(3) * 400 * 10 * 0.85 / 1000 = 5.889 kW
    power_3p, _, _ = ElectricalProtectionService.calculate_power_kw(
        current_a=10.0,
        voltage_v=400.0,
        power_factor=0.85,
        is_three_phase=True,
    )
    assert round(power_3p, 2) == 5.89


def test_load_percentage_calculation():
    # Based on rated current
    load = ElectricalProtectionService.calculate_load_percentage(
        current_a=7.5,
        rated_current_a=10.0,
    )
    assert load == 75.0

    # Based on power
    load_pwr = ElectricalProtectionService.calculate_load_percentage(
        current_a=5.0,
        power_kw=1.5,
        rated_power_kw=3.0,
    )
    assert load_pwr == 50.0


def test_evaluate_normal_operation():
    res = ElectricalProtectionService.evaluate_electrical_safety(
        current_a=7.5,
        voltage_v=230.0,
        motor_is_running=True,
        rated_current_a=10.0,
    )
    assert res.status == ElectricalSafetyStatus.NORMAL
    assert res.is_safe is True
    assert res.should_trip is False
    assert res.metrics is not None
    assert res.metrics.load_percentage == 75.0


def test_evaluate_overcurrent():
    # 13.5A > 12.0A threshold
    res = ElectricalProtectionService.evaluate_electrical_safety(
        current_a=13.5,
        voltage_v=225.0,
        motor_is_running=True,
        max_current_threshold_a=12.0,
    )
    assert res.status == ElectricalSafetyStatus.OVERCURRENT
    assert res.is_safe is False
    assert res.should_trip is True
    assert "Overcurrent" in (res.trip_reason or "")


def test_evaluate_undercurrent_while_running():
    # 1.2A < 2.0A threshold while running
    res = ElectricalProtectionService.evaluate_electrical_safety(
        current_a=1.2,
        voltage_v=230.0,
        motor_is_running=True,
        min_current_running_threshold_a=2.0,
    )
    assert res.status == ElectricalSafetyStatus.UNDERCURRENT
    assert res.is_safe is False
    assert res.should_trip is True
    assert "Undercurrent" in (res.trip_reason or "")


def test_evaluate_undercurrent_motor_off_is_normal():
    # 0.0A current while motor is off is completely normal
    res = ElectricalProtectionService.evaluate_electrical_safety(
        current_a=0.0,
        voltage_v=230.0,
        motor_is_running=False,
    )
    assert res.status == ElectricalSafetyStatus.NORMAL
    assert res.is_safe is True
    assert res.should_trip is False


def test_evaluate_voltage_anomalies():
    # Undervoltage 170V < 180V min
    res_under = ElectricalProtectionService.evaluate_electrical_safety(
        current_a=5.0,
        voltage_v=170.0,
        motor_is_running=True,
    )
    assert res_under.status == ElectricalSafetyStatus.UNDERVOLTAGE
    assert res_under.is_safe is False
    assert res_under.should_trip is True

    # Overvoltage 275V > 260V max
    res_over = ElectricalProtectionService.evaluate_electrical_safety(
        current_a=5.0,
        voltage_v=275.0,
        motor_is_running=True,
    )
    assert res_over.status == ElectricalSafetyStatus.OVERVOLTAGE
    assert res_over.is_safe is False
    assert res_over.should_trip is True


def test_invalid_telemetry():
    res_none = ElectricalProtectionService.evaluate_electrical_safety(
        current_a=None,
        voltage_v=230.0,
        motor_is_running=True,
    )
    assert res_none.status == ElectricalSafetyStatus.INVALID
    assert res_none.is_safe is False

    res_neg = ElectricalProtectionService.evaluate_electrical_safety(
        current_a=-5.0,
        voltage_v=230.0,
        motor_is_running=True,
    )
    assert res_neg.status == ElectricalSafetyStatus.INVALID
    assert res_neg.is_safe is False
