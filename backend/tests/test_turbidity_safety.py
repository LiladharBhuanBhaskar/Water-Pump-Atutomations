"""
Unit tests for Water Quality & Turbidity Domain Service (Phase 13 / P13-T01).
Tests hard turbidity cutoff (>25 NTU), station configurable thresholds (e.g. 5 NTU),
clarity tiers, pH safe range (6.5 - 8.5), and validation edge cases.
"""
import pytest
from app.services.water_quality_service import (
    WaterQualityState,
    TurbidityClarityTier,
    pHState,
    evaluate_turbidity,
    evaluate_ph,
    evaluate_water_quality,
    HARD_MAX_TURBIDITY_NTU,
    DEFAULT_POTABLE_TURBIDITY_THRESHOLD_NTU,
    PH_MIN_SAFE,
    PH_MAX_SAFE
)


def test_evaluate_turbidity_clean_and_acceptable():
    # 0.5 NTU -> Crystal Clear, Safe
    res_clean = evaluate_turbidity(0.5)
    assert res_clean.is_safe is True
    assert res_clean.state == WaterQualityState.SAFE
    assert res_clean.clarity_tier == TurbidityClarityTier.CRYSTAL_CLEAR
    assert res_clean.hard_cutoff_exceeded is False
    assert res_clean.station_threshold_exceeded is False

    # 4.2 NTU -> Acceptable, Safe
    res_acc = evaluate_turbidity(4.2)
    assert res_acc.is_safe is True
    assert res_acc.state == WaterQualityState.SAFE
    assert res_acc.clarity_tier == TurbidityClarityTier.ACCEPTABLE


def test_evaluate_turbidity_station_warning():
    # 12.0 NTU with default 5.0 station threshold -> Warning, but under 25 hard cutoff
    res_warn = evaluate_turbidity(12.0)
    assert res_warn.is_safe is True
    assert res_warn.state == WaterQualityState.WARNING
    assert res_warn.clarity_tier == TurbidityClarityTier.SLIGHTLY_TURBID
    assert res_warn.hard_cutoff_exceeded is False
    assert res_warn.station_threshold_exceeded is True


def test_evaluate_turbidity_hard_cutoff():
    # Exactly 25.0 NTU is the boundary limit
    res_25 = evaluate_turbidity(25.0)
    assert res_25.hard_cutoff_exceeded is False

    # 25.01 NTU -> Critical safety trip
    res_25_01 = evaluate_turbidity(25.01)
    assert res_25_01.is_safe is False
    assert res_25_01.state == WaterQualityState.UNSAFE
    assert res_25_01.clarity_tier == TurbidityClarityTier.HEAVILY_CONTAMINATED
    assert res_25_01.hard_cutoff_exceeded is True
    assert res_25_01.trip_reason == "HARD_TURBIDITY_CUTOFF"

    # 120.0 NTU -> Severe mud / silt contamination
    res_mud = evaluate_turbidity(120.0)
    assert res_mud.is_safe is False
    assert res_mud.state == WaterQualityState.UNSAFE
    assert res_mud.hard_cutoff_exceeded is True


def test_evaluate_turbidity_invalid_inputs():
    res_nan = evaluate_turbidity(float("nan"))
    assert res_nan.is_safe is False
    assert res_nan.state == WaterQualityState.INVALID

    res_neg = evaluate_turbidity(-5.0)
    assert res_neg.is_safe is False
    assert res_neg.state == WaterQualityState.INVALID


def test_evaluate_ph_ranges():
    # Optimal: 7.0, 6.5, 8.5
    assert evaluate_ph(7.0).state == pHState.OPTIMAL
    assert evaluate_ph(7.0).is_safe is True
    assert evaluate_ph(6.5).state == pHState.OPTIMAL
    assert evaluate_ph(8.5).state == pHState.OPTIMAL

    # Acidic: 6.2 (< 6.5)
    res_acid = evaluate_ph(6.2)
    assert res_acid.is_safe is False
    assert res_acid.state == pHState.ACIDIC

    # Alkaline: 9.1 (> 8.5)
    res_alk = evaluate_ph(9.1)
    assert res_alk.is_safe is False
    assert res_alk.state == pHState.ALKALINE

    # Invalid: -1.0 or 15.0
    assert evaluate_ph(-1.0).state == pHState.INVALID
    assert evaluate_ph(15.0).state == pHState.INVALID


def test_evaluate_water_quality_composite():
    # Safe turbidity + Safe pH
    res_safe = evaluate_water_quality(turbidity_ntu=2.0, ph_value=7.4)
    assert res_safe.is_overall_safe is True

    # Safe turbidity + Acidic pH -> Overall Unsafe
    res_acidic = evaluate_water_quality(turbidity_ntu=2.0, ph_value=5.8)
    assert res_acidic.is_overall_safe is False
    assert res_acidic.ph_eval.state == pHState.ACIDIC

    # Contaminated turbidity + Safe pH -> Overall Unsafe
    res_dirty = evaluate_water_quality(turbidity_ntu=35.0, ph_value=7.2)
    assert res_dirty.is_overall_safe is False
    assert res_dirty.turbidity_eval.state == WaterQualityState.UNSAFE
