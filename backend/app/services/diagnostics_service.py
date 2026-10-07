"""Diagnostics service for Water Quality, Flow, and Electrical Metrics (Phase 12-15 - Wave 2B)."""

import uuid
from datetime import datetime, timezone
from typing import Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc, and_

from app.models.station import Station
from app.models.controller import Controller
from app.models.sensor import Sensor, SensorType
from app.models.telemetry import TelemetryReading
from app.models.motor import Motor, MotorStatus
from app.models.motor_event import MotorEvent, MotorEventType
from app.models.settings import StationSettings
from app.models.site import Site
from app.models.user import User, UserRole

from app.services.water_quality_service import WaterQualityService, WaterQualityStatus
from app.services.flow_protection_service import FlowProtectionService, FlowSafetyStatus
from app.services.electrical_protection_service import ElectricalProtectionService, ElectricalSafetyStatus
from app.schemas.diagnostics import (
    WaterQualityResponse,
    FlowDiagnosticsResponse,
    ElectricalMetricsResponse,
)


async def get_station_water_quality_diagnostics(
    session: AsyncSession,
    station_id: uuid.UUID,
) -> WaterQualityResponse:
    """Retrieves latest water quality (Turbidity & pH) for a station and evaluates safety."""
    # Find all sensors for controllers under this station
    stmt_sensors = (
        select(Sensor)
        .join(Controller, Sensor.controller_id == Controller.id)
        .where(Controller.station_id == station_id)
        .where(Sensor.sensor_type.in_([SensorType.TURBIDITY, SensorType.PH]))
    )
    res_sensors = await session.execute(stmt_sensors)
    sensors = res_sensors.scalars().all()

    turbidity_val: Optional[float] = None
    turbidity_quality: Optional[str] = None
    turbidity_time: Optional[datetime] = None

    ph_val: Optional[float] = None
    ph_quality: Optional[str] = None
    ph_time: Optional[datetime] = None

    for sensor in sensors:
        # Get latest reading
        stmt_reading = (
            select(TelemetryReading)
            .where(TelemetryReading.sensor_id == sensor.id)
            .order_by(desc(TelemetryReading.occurred_at))
            .limit(1)
        )
        res_reading = await session.execute(stmt_reading)
        reading = res_reading.scalar_one_or_none()
        if reading is not None:
            reading_meta = reading.metadata_ if hasattr(reading, "metadata_") and isinstance(reading.metadata_, dict) else {}
            if sensor.sensor_type == SensorType.TURBIDITY and (turbidity_time is None or reading.occurred_at > turbidity_time):
                turbidity_val = float(reading.value)
                turbidity_time = reading.occurred_at
                turbidity_quality = reading_meta.get("quality", "GOOD")
            elif sensor.sensor_type == SensorType.PH and (ph_time is None or reading.occurred_at > ph_time):
                ph_val = float(reading.value)
                ph_time = reading.occurred_at
                ph_quality = reading_meta.get("quality", "GOOD")

    # Get station settings threshold
    stmt_settings = select(StationSettings).where(StationSettings.station_id == station_id)
    res_settings = await session.execute(stmt_settings)
    settings = res_settings.scalar_one_or_none()
    configured_threshold = float(settings.turbidity_threshold) if (settings and settings.turbidity_threshold is not None) else None

    # Evaluate with domain service
    if turbidity_val is None:
        t_status = WaterQualityStatus.INVALID
        is_safe = False
        should_trip = False
        trip_reason = "No turbidity telemetry available"
        summary = "No turbidity reading available"
        threshold_used = configured_threshold
    else:
        evaluation = WaterQualityService.evaluate_water_quality(
            turbidity_ntu=turbidity_val,
            ph_value=ph_val,
            station_threshold_ntu=configured_threshold,
        )
        t_status = WaterQualityStatus(evaluation.turbidity_eval.state.value)
        is_safe = evaluation.is_overall_safe
        should_trip = not evaluation.turbidity_eval.is_safe and evaluation.turbidity_eval.state.value == WaterQualityStatus.UNSAFE.value
        trip_reason = evaluation.turbidity_eval.trip_reason
        summary = evaluation.summary_message
        threshold_used = configured_threshold or 25.0


    return WaterQualityResponse(
        station_id=station_id,
        turbidity_ntu=turbidity_val,
        turbidity_quality=turbidity_quality,
        turbidity_updated_at=turbidity_time,
        ph=ph_val,
        ph_quality=ph_quality,
        ph_updated_at=ph_time,
        status=t_status,
        is_safe=is_safe,
        should_trip=should_trip,
        trip_reason=trip_reason,
        threshold_used=threshold_used,
        details={"summary": summary},
    )


async def get_motor_flow_diagnostics(
    session: AsyncSession,
    motor: Motor,
) -> FlowDiagnosticsResponse:
    """Retrieves latest flow telemetry for a motor's controller and evaluates dry-run/flow safety."""
    # Find FLOW sensors on the controller
    stmt_sensors = (
        select(Sensor)
        .where(Sensor.controller_id == motor.controller_id)
        .where(Sensor.sensor_type == SensorType.FLOW)
    )

    res_sensors = await session.execute(stmt_sensors)
    flow_sensor = res_sensors.scalars().first()

    raw_val: Optional[float] = None
    raw_unit: Optional[str] = None
    flow_time: Optional[datetime] = None

    if flow_sensor is not None:
        stmt_reading = (
            select(TelemetryReading)
            .where(TelemetryReading.sensor_id == flow_sensor.id)
            .order_by(desc(TelemetryReading.occurred_at))
            .limit(1)
        )
        res_reading = await session.execute(stmt_reading)
        reading = res_reading.scalar_one_or_none()
        if reading is not None:
            raw_val = float(reading.value)
            raw_unit = reading.unit
            flow_time = reading.occurred_at

    # Check motor run duration since transition to ON / STARTING
    elapsed_seconds = 0.0
    if motor.status in [MotorStatus.ON, MotorStatus.STARTING]:
        stmt_event = (
            select(MotorEvent)
            .where(MotorEvent.motor_id == motor.id)
            .where(MotorEvent.event_type == MotorEventType.STARTED)
            .order_by(desc(MotorEvent.occurred_at))
            .limit(1)
        )

        res_event = await session.execute(stmt_event)
        event = res_event.scalar_one_or_none()
        if event is not None:
            now_utc = datetime.now(timezone.utc)
            event_time = event.occurred_at if event.occurred_at.tzinfo else event.occurred_at.replace(tzinfo=timezone.utc)
            elapsed_seconds = max(0.0, (now_utc - event_time).total_seconds())
        else:
            elapsed_seconds = 60.0  # fallback assumption if running without event record

    if raw_val is None:
        flow_eval_state = FlowSafetyStatus.NO_FLOW_STANDBY if motor.status == MotorStatus.OFF else FlowSafetyStatus.INVALID
        flow_is_safe = (motor.status == MotorStatus.OFF)
        flow_should_trip = False
        flow_trip_reason = None
        flow_lpm = None
        flow_m3h = None
        is_grace = False
        flow_details = {"message": "No flow reading available"}
    else:
        evaluation = FlowProtectionService.evaluate_flow_safety(
            flow_value=raw_val,
            unit=raw_unit or "L/min",
            motor_is_running=(motor.status == MotorStatus.ON),
            running_seconds=elapsed_seconds,
        )
        flow_eval_state = FlowSafetyStatus(evaluation.state.value)
        flow_is_safe = evaluation.is_safe
        flow_should_trip = not evaluation.is_safe
        flow_trip_reason = evaluation.trip_reason
        flow_lpm = evaluation.flow_lpm
        flow_m3h = evaluation.flow_m3_h
        is_grace = (evaluation.state.value == "STARTUP_PRIMING")
        flow_details = evaluation.metadata
        flow_details["message"] = evaluation.message

    return FlowDiagnosticsResponse(
        motor_id=motor.id,
        motor_status=motor.status,
        flow_rate_lpm=flow_lpm,
        flow_rate_m3h=flow_m3h,
        raw_flow_value=raw_val,
        raw_flow_unit=raw_unit,
        flow_updated_at=flow_time,
        is_startup_grace_period=is_grace,
        status=flow_eval_state,
        is_safe=flow_is_safe,
        should_trip=flow_should_trip,
        trip_reason=flow_trip_reason,
        details=flow_details,
    )



async def get_motor_electrical_metrics(
    session: AsyncSession,
    motor: Motor,
) -> ElectricalMetricsResponse:
    """Retrieves latest electrical (Current & Voltage) telemetry for a motor and evaluates electrical load."""
    stmt_sensors = (
        select(Sensor)
        .where(Sensor.controller_id == motor.controller_id)
        .where(Sensor.sensor_type.in_([SensorType.CURRENT, SensorType.VOLTAGE]))
    )
    res_sensors = await session.execute(stmt_sensors)
    sensors = res_sensors.scalars().all()

    current_a: Optional[float] = None
    current_time: Optional[datetime] = None
    voltage_v: Optional[float] = None
    voltage_time: Optional[datetime] = None

    for sensor in sensors:
        stmt_reading = (
            select(TelemetryReading)
            .where(TelemetryReading.sensor_id == sensor.id)
            .order_by(desc(TelemetryReading.occurred_at))
            .limit(1)
        )
        res_reading = await session.execute(stmt_reading)
        reading = res_reading.scalar_one_or_none()
        if reading is not None:
            if sensor.sensor_type == SensorType.CURRENT:
                current_a = float(reading.value)
                current_time = reading.occurred_at
            elif sensor.sensor_type == SensorType.VOLTAGE:
                voltage_v = float(reading.value)
                voltage_time = reading.occurred_at

    rated_power_kw = float(motor.rated_power) if motor.rated_power is not None else None

    evaluation = ElectricalProtectionService.evaluate_electrical_safety(
        current_a=current_a,
        voltage_v=voltage_v,
        motor_is_running=(motor.status == MotorStatus.ON),
        rated_power_kw=rated_power_kw,
    )

    metrics = evaluation.metrics

    return ElectricalMetricsResponse(
        motor_id=motor.id,
        motor_status=motor.status,
        current_a=current_a,
        voltage_v=voltage_v,
        power_kw=metrics.power_kw if metrics else None,
        rated_power_kw=rated_power_kw,
        load_percentage=metrics.load_percentage if metrics else None,
        power_factor=metrics.power_factor if metrics else None,
        is_power_factor_estimated=metrics.is_power_factor_estimated if metrics else True,
        current_updated_at=current_time,
        voltage_updated_at=voltage_time,
        status=evaluation.status,
        is_safe=evaluation.is_safe,
        should_trip=evaluation.should_trip,
        trip_reason=evaluation.trip_reason,
        details=evaluation.details,
    )


async def verify_motor_tenant_access(
    session: AsyncSession,
    motor_id: uuid.UUID,
    current_user: User,
) -> Optional[Motor]:
    """Verifies that the user has tenant access to the motor."""
    stmt = (
        select(Motor)
        .join(Controller, Motor.controller_id == Controller.id)
        .join(Station, Controller.station_id == Station.id)
        .join(Site, Station.site_id == Site.id)
        .where(Motor.id == motor_id)
    )
    if current_user.role != UserRole.SUPER_ADMIN:
        if current_user.organization_id is None:
            return None
        stmt = stmt.where(Site.organization_id == current_user.organization_id)

    res = await session.execute(stmt)
    return res.scalar_one_or_none()
