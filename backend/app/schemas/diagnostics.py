"""Pydantic schemas for Safety Diagnostics APIs (Phase 12-15 - Wave 2B)."""

import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, ConfigDict
from app.models.motor import MotorStatus
from app.services.water_quality_service import WaterQualityStatus
from app.services.flow_protection_service import FlowSafetyStatus
from app.services.electrical_protection_service import ElectricalSafetyStatus


class WaterQualityResponse(BaseModel):
    station_id: uuid.UUID
    turbidity_ntu: Optional[float] = None
    turbidity_quality: Optional[str] = None
    turbidity_updated_at: Optional[datetime] = None
    ph: Optional[float] = None
    ph_quality: Optional[str] = None
    ph_updated_at: Optional[datetime] = None
    status: WaterQualityStatus
    is_safe: bool
    should_trip: bool
    trip_reason: Optional[str] = None
    threshold_used: Optional[float] = None
    details: Dict[str, Any] = {}

    model_config = ConfigDict(from_attributes=True)


class FlowDiagnosticsResponse(BaseModel):
    motor_id: uuid.UUID
    motor_status: MotorStatus
    flow_rate_lpm: Optional[float] = None
    flow_rate_m3h: Optional[float] = None
    raw_flow_value: Optional[float] = None
    raw_flow_unit: Optional[str] = None
    flow_updated_at: Optional[datetime] = None
    is_startup_grace_period: bool
    status: FlowSafetyStatus
    is_safe: bool
    should_trip: bool
    trip_reason: Optional[str] = None
    details: Dict[str, Any] = {}

    model_config = ConfigDict(from_attributes=True)


class ElectricalMetricsResponse(BaseModel):
    motor_id: uuid.UUID
    motor_status: MotorStatus
    current_a: Optional[float] = None
    voltage_v: Optional[float] = None
    power_kw: Optional[float] = None
    rated_power_kw: Optional[float] = None
    load_percentage: Optional[float] = None
    power_factor: Optional[float] = None
    is_power_factor_estimated: bool = True
    current_updated_at: Optional[datetime] = None
    voltage_updated_at: Optional[datetime] = None
    status: ElectricalSafetyStatus
    is_safe: bool
    should_trip: bool
    trip_reason: Optional[str] = None
    details: Dict[str, Any] = {}

    model_config = ConfigDict(from_attributes=True)
