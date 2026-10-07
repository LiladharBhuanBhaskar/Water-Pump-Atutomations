"""HydraControl — Inbound MQTT Telemetry Handler with Edge Safety Integration (Phase 12-15 - Wave 2C).

Validates device authenticity, sensor ownership, normalizes units, tags quality,
persists readings, streams real-time telemetry, and deterministically evaluates
edge safety conditions across Tank Level, Water Quality, Flow, and Electrical Load domains.
"""

import uuid
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import desc

from app.db.session import AsyncSessionLocal
from app.models.controller import Controller, ControllerStatus
from app.models.sensor import Sensor, SensorStatus, SensorType
from app.models.motor import Motor, MotorStatus
from app.models.motor_event import MotorEvent, MotorEventType, MotorEventSource
from app.models.station import Station
from app.models.settings import StationSettings
from app.models.site import Site
from app.models.telemetry import TelemetryReading
from app.mqtt.router import mqtt_router, ROOT_PREFIX, SHORT_PREFIX
from app.websocket.streamer import stream_telemetry, stream_safety_alert, stream_motor_state
from app.services.sensor_service import (
    validate_sensor_reading,
    ensure_utc_datetime,
    normalize_sensor_unit,
)
from app.services.motor_state_engine import (
    transition_motor_state,
    MotorStateEvent,
)
from app.services.tank_safety_service import (
    TankSafetyService,
    TankType,
    TankSafetyState,
)
from app.services.water_quality_service import (
    evaluate_turbidity,
    WaterQualityState,
)
from app.services.flow_protection_service import (
    evaluate_flow_safety,
    FlowSafetyState,
)
from app.services.electrical_protection_service import (
    ElectricalProtectionService,
    ElectricalSafetyStatus,
)

logger = logging.getLogger("hydracontrol.mqtt.handlers.telemetry")


async def process_telemetry_payload(device_uid: str, payload: Any) -> int:
    """
    Process incoming telemetry payload for a device.
    Supports single reading dict or list of reading dicts.
    Validates device authenticity, sensor ownership, data types, physical ranges,
    persists readings with quality metadata, evaluates edge safety rules,
    and broadcasts updates via WebSocket.
    """
    if isinstance(payload, dict):
        readings_list = [payload]
    elif isinstance(payload, list):
        readings_list = [item for item in payload if isinstance(item, dict)]
    else:
        logger.warning(f"Invalid telemetry payload format from device '{device_uid}': {type(payload)}")
        return 0

    if not readings_list:
        return 0

    saved_count = 0
    async with AsyncSessionLocal() as session:
        # Resolve controller with sensors, motors, station, settings, and site hierarchy
        stmt_ctrl = (
            select(Controller)
            .options(
                selectinload(Controller.sensors),
                selectinload(Controller.motors),
                selectinload(Controller.station).selectinload(Station.settings),
                selectinload(Controller.station).selectinload(Station.site),
            )
            .where(Controller.device_uid == device_uid)
        )
        res_ctrl = await session.execute(stmt_ctrl)
        controller = res_ctrl.scalar_one_or_none()

        if controller is None:
            logger.warning(f"Rejected telemetry: Unprovisioned or unknown device '{device_uid}'")
            return 0

        if controller.status == ControllerStatus.DECOMMISSIONED:
            logger.warning(f"Rejected telemetry: Device '{device_uid}' is decommissioned.")
            return 0

        # Extract hierarchy context for multi-tenant channel broadcasting
        station_id = controller.station_id if controller.station else None
        site_id = controller.station.site_id if (controller.station and controller.station.site) else None
        org_id = controller.station.site.organization_id if (controller.station and controller.station.site) else None
        station_settings = controller.station.settings if (controller.station and controller.station.settings) else None

        # Build lookup table of registered sensors on this physical controller
        sensors_by_code: Dict[str, Sensor] = {s.sensor_code.upper(): s for s in controller.sensors}

        now = datetime.now(timezone.utc)
        controller.last_seen_at = now
        if controller.status == ControllerStatus.OFFLINE:
            controller.status = ControllerStatus.ACTIVE
        session.add(controller)

        persisted_items = []
        safety_trips_to_evaluate = []

        for item in readings_list:
            sensor_code = str(item.get("sensor_code", "")).strip().upper()
            if not sensor_code:
                continue

            sensor = sensors_by_code.get(sensor_code)
            if sensor is None:
                logger.warning(f"Rejected telemetry: Unauthorized/unregistered sensor '{sensor_code}' on controller '{device_uid}'")
                continue

            if sensor.status == SensorStatus.DISABLED:
                logger.debug(f"Skipping telemetry for disabled sensor '{sensor_code}' on '{device_uid}'")
                continue

            raw_value = item.get("value")
            raw_unit = item.get("unit")

            is_valid, error_reason, val_float, normalized_unit, quality_meta = validate_sensor_reading(
                sensor_type=sensor.sensor_type,
                raw_value=raw_value,
                raw_unit=raw_unit,
            )

            if not is_valid:
                logger.warning(f"Invalid telemetry value for sensor '{sensor_code}' on '{device_uid}': {error_reason}")
                continue

            occurred_at_raw = item.get("occurred_at")
            occurred_at = ensure_utc_datetime(occurred_at_raw) if occurred_at_raw is not None else now

            metadata = item.get("metadata")
            if metadata is not None and not isinstance(metadata, dict):
                metadata = {"raw": metadata}
            else:
                metadata = dict(metadata) if metadata else {}

            metadata.update(quality_meta)

            reading = TelemetryReading(
                id=uuid.uuid4(),
                sensor_id=sensor.id,
                value=val_float,
                unit=normalized_unit,
                occurred_at=occurred_at,
                metadata_=metadata,
            )
            session.add(reading)
            saved_count += 1
            persisted_items.append({
                "sensor_id": sensor.id,
                "sensor_code": sensor.sensor_code,
                "sensor_type": sensor.sensor_type,
                "value": val_float,
                "unit": normalized_unit,
                "occurred_at": occurred_at,
                "metadata": metadata,
            })
            safety_trips_to_evaluate.append((sensor, val_float, normalized_unit, occurred_at))

        if saved_count > 0:
            await session.commit()
            logger.info(f"Persisted {saved_count} telemetry readings for controller '{device_uid}'")

            # 1. Real-time WebSocket broadcasting for telemetry
            for p in persisted_items:
                try:
                    await stream_telemetry(
                        device_uid=device_uid,
                        sensor_id=p["sensor_id"],
                        sensor_code=p["sensor_code"],
                        value=p["value"],
                        unit=p["unit"],
                        occurred_at=p["occurred_at"],
                        organization_id=org_id,
                        site_id=site_id,
                        station_id=station_id,
                        metadata=p["metadata"],
                    )
                except Exception as e:
                    logger.error(f"Error streaming telemetry for '{device_uid}': {e}")

            # 2. Edge Safety Rules Evaluation & Motor State Engine Integration
            for sensor, val, unit_str, reading_time in safety_trips_to_evaluate:
                for motor in controller.motors:
                    if motor.status != MotorStatus.ON:
                        continue

                    # Domain 1: Tank Level Safety (Phase 12 / P12-T02)
                    if sensor.sensor_type == SensorType.WATER_LEVEL:
                        tank_type = TankType.SUMP if "sump" in sensor.sensor_code.lower() or "source" in sensor.sensor_code.lower() else TankType.OVERHEAD
                        tank_eval = TankSafetyService.evaluate_tank_safety(
                            level_value=val,
                            unit=unit_str,
                            tank_type=tank_type,
                            high_threshold_pct=(float(station_settings.water_level_threshold) if (station_settings and station_settings.water_level_threshold is not None) else None),
                            auto_stop_enabled=(station_settings.auto_stop_on_tank_full if station_settings else False),
                        )
                        if tank_eval.safety_state == TankSafetyState.HIGH_TRIP:
                            # Auto-stop on full overhead tank
                            t_res = transition_motor_state(
                                current_state=motor.status,
                                event=MotorStateEvent.CMD_STOP,
                                context={"error_message": f"Auto-Stop: Tank reached full capacity ({val:.1f}%)"}
                            )
                            if t_res.is_valid:
                                motor.status = t_res.next_state
                                session.add(motor)
                                event_entry = MotorEvent(
                                    id=uuid.uuid4(),
                                    motor_id=motor.id,
                                    event_type=MotorEventType.STOPPED,
                                    source=MotorEventSource.AUTOMATION,
                                    occurred_at=reading_time,
                                    description=f"Auto-Stop on Tank Full ({val:.1f}%)",
                                    event_payload={"tank_level": val, "reason": "TANK_FULL"},
                                )
                                session.add(event_entry)
                                await session.commit()
                                await stream_motor_state(
                                    motor_id=motor.id,
                                    motor_code=motor.motor_code,
                                    device_uid=device_uid,
                                    status=motor.status,
                                    organization_id=org_id,
                                    site_id=site_id,
                                    station_id=station_id,
                                )
                                await stream_safety_alert(
                                    event_type="TANK_FULL",
                                    motor_id=motor.id,
                                    motor_code=motor.motor_code,
                                    device_uid=device_uid,
                                    description=f"Tank Full ({val:.1f}%): Pump stopped automatically.",
                                    payload={"tank_level": val},
                                    organization_id=org_id,
                                    site_id=site_id,
                                    station_id=station_id,
                                )
                        elif tank_eval.safety_state == TankSafetyState.LOW_TRIP:
                            # Sump / Source depleted dry-run trip
                            t_res = transition_motor_state(
                                current_state=motor.status,
                                event=MotorStateEvent.SAFETY_TRIP,
                                context={"error_message": f"Safety Trip: Source tank depleted ({val:.1f}% <= 10%)"}
                            )

                            if t_res.is_valid:
                                motor.status = t_res.next_state
                                session.add(motor)
                                event_entry = MotorEvent(
                                    id=uuid.uuid4(),
                                    motor_id=motor.id,
                                    event_type=MotorEventType.FAULT,
                                    source=MotorEventSource.SENSOR,
                                    occurred_at=reading_time,
                                    description=f"Source Tank Depleted ({val:.1f}%) Safety Trip",
                                    event_payload={"source_level": val, "reason": "SOURCE_DEPLETED"},
                                )
                                session.add(event_entry)
                                await session.commit()
                                await stream_motor_state(
                                    motor_id=motor.id,
                                    motor_code=motor.motor_code,
                                    device_uid=device_uid,
                                    status=motor.status,
                                    organization_id=org_id,
                                    site_id=site_id,
                                    station_id=station_id,
                                )
                                await stream_safety_alert(
                                    event_type="SOURCE_DEPLETED",
                                    motor_id=motor.id,
                                    motor_code=motor.motor_code,
                                    device_uid=device_uid,
                                    description=f"Source Depleted ({val:.1f}%): Pump tripped to prevent dry running.",
                                    payload={"source_level": val},
                                    organization_id=org_id,
                                    site_id=site_id,
                                    station_id=station_id,
                                )

                    # Domain 2: Water Quality & Turbidity Safety (Phase 13 / P13-T02)
                    elif sensor.sensor_type == SensorType.TURBIDITY:
                        cfg_limit = float(station_settings.turbidity_threshold) if (station_settings and station_settings.turbidity_threshold is not None) else None
                        turb_eval = evaluate_turbidity(turbidity_ntu=val, station_threshold_ntu=cfg_limit)
                        if not turb_eval.is_safe and turb_eval.hard_cutoff_exceeded:
                            t_res = transition_motor_state(
                                current_state=motor.status,
                                event=MotorStateEvent.SAFETY_TRIP,
                                context={"error_message": f"Turbidity Safety Trip: Water turbidity ({val:.1f} NTU) exceeds limit (25 NTU)"}
                            )
                            if t_res.is_valid:
                                motor.status = t_res.next_state
                                session.add(motor)
                                event_entry = MotorEvent(
                                    id=uuid.uuid4(),
                                    motor_id=motor.id,
                                    event_type=MotorEventType.FAULT,
                                    source=MotorEventSource.SENSOR,
                                    occurred_at=reading_time,
                                    description=f"Turbidity Contamination Trip ({val:.1f} NTU > 25 NTU)",
                                    event_payload={"turbidity_ntu": val, "reason": "TURBIDITY_TRIP"},
                                )
                                session.add(event_entry)
                                await session.commit()
                                await stream_motor_state(
                                    motor_id=motor.id,
                                    motor_code=motor.motor_code,
                                    device_uid=device_uid,
                                    status=motor.status,
                                    organization_id=org_id,
                                    site_id=site_id,
                                    station_id=station_id,
                                )
                                await stream_safety_alert(
                                    event_type="TURBIDITY_TRIP",
                                    motor_id=motor.id,
                                    motor_code=motor.motor_code,
                                    device_uid=device_uid,
                                    description=f"Severe Water Contamination ({val:.1f} NTU): Pump tripped instantly.",
                                    payload={"turbidity_ntu": val},
                                    organization_id=org_id,
                                    site_id=site_id,
                                    station_id=station_id,
                                )

                    # Domain 3: Flow Protection & Dry Run (Phase 14 / P14-T02)
                    elif sensor.sensor_type == SensorType.FLOW:
                        stmt_ev = (
                            select(MotorEvent)
                            .where(MotorEvent.motor_id == motor.id)
                            .where(MotorEvent.event_type == MotorEventType.STARTED)
                            .order_by(desc(MotorEvent.occurred_at))
                            .limit(1)
                        )
                        res_ev = await session.execute(stmt_ev)
                        ev = res_ev.scalar_one_or_none()
                        run_secs = 60.0
                        if ev is not None:
                            ev_time = ev.occurred_at if ev.occurred_at.tzinfo else ev.occurred_at.replace(tzinfo=timezone.utc)
                            run_secs = max(0.0, (now - ev_time).total_seconds())

                        flow_eval = evaluate_flow_safety(
                            flow_value=val,
                            unit=unit_str,
                            motor_is_running=True,
                            running_seconds=run_secs,
                        )
                        if not flow_eval.is_safe and flow_eval.state in (FlowSafetyState.DRY_RUN_TRIP, FlowSafetyState.PIPE_BURST_TRIP):
                            trip_type = "DRY_RUN_TRIP" if flow_eval.state == FlowSafetyState.DRY_RUN_TRIP else "PIPE_BURST"
                            t_res = transition_motor_state(
                                current_state=motor.status,
                                event=MotorStateEvent.SAFETY_TRIP,
                                context={"error_message": f"Flow Safety Trip: {flow_eval.message}"}
                            )
                            if t_res.is_valid:
                                motor.status = t_res.next_state
                                session.add(motor)
                                event_entry = MotorEvent(
                                    id=uuid.uuid4(),
                                    motor_id=motor.id,
                                    event_type=MotorEventType.FAULT,
                                    source=MotorEventSource.SENSOR,
                                    occurred_at=reading_time,
                                    description=f"Flow Fault Trip: {trip_type}",
                                    event_payload={"flow_value": val, "unit": unit_str, "reason": trip_type},
                                )
                                session.add(event_entry)
                                await session.commit()
                                await stream_motor_state(
                                    motor_id=motor.id,
                                    motor_code=motor.motor_code,
                                    device_uid=device_uid,
                                    status=motor.status,
                                    organization_id=org_id,
                                    site_id=site_id,
                                    station_id=station_id,
                                )
                                await stream_safety_alert(
                                    event_type=trip_type,
                                    motor_id=motor.id,
                                    motor_code=motor.motor_code,
                                    device_uid=device_uid,
                                    description=flow_eval.message,
                                    payload={"flow_value": val, "unit": unit_str},
                                    organization_id=org_id,
                                    site_id=site_id,
                                    station_id=station_id,
                                )

                    # Domain 4: Electrical Safety (Phase 15 / P15-T02)
                    elif sensor.sensor_type in (SensorType.CURRENT, SensorType.VOLTAGE):
                        curr_val = val if sensor.sensor_type == SensorType.CURRENT else None
                        volt_val = val if sensor.sensor_type == SensorType.VOLTAGE else 230.0
                        elec_eval = ElectricalProtectionService.evaluate_electrical_safety(
                            current_a=curr_val if curr_val is not None else 8.0,
                            voltage_v=volt_val,
                            motor_is_running=True,
                            rated_power_kw=float(motor.rated_power) if motor.rated_power else None,
                        )
                        if not elec_eval.is_safe and elec_eval.should_trip:
                            trip_type = (
                                "OVERLOAD_TRIP"
                                if elec_eval.status == ElectricalSafetyStatus.OVERCURRENT
                                else ("UNDERCURRENT_TRIP" if elec_eval.status == ElectricalSafetyStatus.UNDERCURRENT else "VOLTAGE_TRIP")
                            )
                            t_res = transition_motor_state(
                                current_state=motor.status,
                                event=MotorStateEvent.SAFETY_TRIP,
                                context={"error_message": f"Electrical Safety Trip: {elec_eval.trip_reason}"}
                            )
                            if t_res.is_valid:
                                motor.status = t_res.next_state
                                session.add(motor)
                                event_entry = MotorEvent(
                                    id=uuid.uuid4(),
                                    motor_id=motor.id,
                                    event_type=MotorEventType.FAULT,
                                    source=MotorEventSource.SENSOR,
                                    occurred_at=reading_time,
                                    description=f"Electrical Trip: {elec_eval.trip_reason}",
                                    event_payload={"value": val, "sensor_type": sensor.sensor_type.value, "reason": trip_type},
                                )
                                session.add(event_entry)
                                await session.commit()
                                await stream_motor_state(
                                    motor_id=motor.id,
                                    motor_code=motor.motor_code,
                                    device_uid=device_uid,
                                    status=motor.status,
                                    organization_id=org_id,
                                    site_id=site_id,
                                    station_id=station_id,
                                )
                                await stream_safety_alert(
                                    event_type=trip_type,
                                    motor_id=motor.id,
                                    motor_code=motor.motor_code,
                                    device_uid=device_uid,
                                    description=elec_eval.trip_reason or "Electrical fault",
                                    payload={"value": val, "sensor_type": sensor.sensor_type.value},
                                    organization_id=org_id,
                                    site_id=site_id,
                                    station_id=station_id,
                                )

    return saved_count


@mqtt_router.route(f"{ROOT_PREFIX}/{{device_uid}}/telemetry")
@mqtt_router.route(f"{SHORT_PREFIX}/{{device_uid}}/telemetry")
async def handle_device_telemetry(device_uid: str, payload: Any, **kwargs):
    """MQTT Route handler for sensor telemetry ingestion."""
    await process_telemetry_payload(device_uid, payload)
