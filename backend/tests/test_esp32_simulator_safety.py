"""
HydraControl — P7-T02 Local Safety Interlocks & Offline Autonomous Protection Tests
Verifies on-device edge safety rules (turbidity limit cutoff, tank full auto-stop, emergency stop latching),
autonomous offline operation without broker/cloud, safe-state preservation, and reconnect event flushing.
"""

import sys
import os
import pytest
import uuid
from typing import Dict, Any, List

# Ensure device_simulator is importable
simulator_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "device_simulator"))
if simulator_dir not in sys.path:
    sys.path.insert(0, simulator_dir)
from esp32_simulator import ESP32Simulator


class MockMQTTCollector:
    """Captures published messages and tracks online/offline state."""

    def __init__(self):
        self.messages: List[Dict[str, Any]] = []

    def publish(self, topic: str, payload: Any, qos: int = 1) -> bool:
        self.messages.append({
            "topic": topic,
            "payload": payload,
            "qos": qos
        })
        return True

    def get_messages_by_topic_suffix(self, suffix: str) -> List[Dict[str, Any]]:
        return [m for m in self.messages if m["topic"].endswith(suffix)]


@pytest.fixture
def collector():
    return MockMQTTCollector()


@pytest.fixture
def simulator(collector):
    sim = ESP32Simulator(
        device_uid="ESP32-SAFETY-01",
        motor_code="PUMP_01",
        transition_delay=0.0,
        mqtt_publisher=collector.publish
    )
    sim.is_connected = True
    return sim


def test_turbidity_threshold_boundary_allowed(simulator, collector):
    """START is permitted when turbidity is exactly 25.0 NTU (at boundary limit)."""
    simulator.turbidity = 25.0
    cmd_id = str(uuid.uuid4())
    payload = {"command_id": cmd_id, "command_type": "START", "motor_code": "PUMP_01"}

    success = simulator.process_command(payload)
    assert success is True
    assert simulator.motor_status == "ON"

    acks = collector.get_messages_by_topic_suffix("/ack")
    assert any(a["payload"]["status"] == "EXECUTED" for a in acks)


def test_turbidity_threshold_exceeded_rejects_start(simulator, collector):
    """START is rejected when turbidity > 25.0 NTU (e.g. 26.5 NTU), emitting FAILED ACK and FAULT."""
    simulator.turbidity = 26.5
    cmd_id = str(uuid.uuid4())
    payload = {"command_id": cmd_id, "command_type": "START", "motor_code": "PUMP_01"}

    success = simulator.process_command(payload)
    assert success is False
    assert simulator.motor_status == "OFF"

    acks = collector.get_messages_by_topic_suffix("/ack")
    assert len(acks) == 1
    assert acks[0]["payload"]["status"] == "FAILED"
    assert "Turbidity" in acks[0]["payload"]["error_message"]

    # Verify FAULT message emitted
    faults = collector.get_messages_by_topic_suffix("/fault")
    assert len(faults) >= 1
    assert "Turbidity" in faults[0]["payload"]["description"]


def test_tank_full_auto_stop_at_boundary(simulator, collector):
    """Motor automatically stops when tank level reaches exactly 95.0% while running."""
    # Put motor in running state at 80% tank level
    simulator.motor_status = "ON"
    simulator.flow_rate = 45.0
    simulator.current = 6.5
    simulator.tank_level = 80.0

    # Sensor updates to 95.0%
    simulator.set_sensor_values(tank_level=95.0)

    # Motor must be stopped immediately by local interlock
    assert simulator.motor_status == "OFF"
    assert simulator.flow_rate == 0.0
    assert simulator.current == 0.0

    faults = collector.get_messages_by_topic_suffix("/fault")
    assert len(faults) >= 1
    assert "Tank level" in faults[-1]["payload"]["description"]


def test_tank_full_auto_stop_above_boundary(simulator, collector):
    """Motor automatically stops when tank level exceeds 95.0% (e.g. 98.2%)."""
    simulator.motor_status = "ON"
    simulator.tank_level = 75.0

    simulator.set_sensor_values(tank_level=98.2)
    assert simulator.motor_status == "OFF"


def test_tank_full_rejects_new_start_command(simulator, collector):
    """START command is rejected when tank is full (>=95%)."""
    simulator.tank_level = 96.0
    cmd_id = str(uuid.uuid4())
    payload = {"command_id": cmd_id, "command_type": "START", "motor_code": "PUMP_01"}

    success = simulator.process_command(payload)
    assert success is False
    assert simulator.motor_status == "OFF"

    acks = collector.get_messages_by_topic_suffix("/ack")
    assert len(acks) == 1
    assert acks[0]["payload"]["status"] == "FAILED"
    assert "Tank is FULL" in acks[0]["payload"]["error_message"]


def test_local_emergency_stop_latches_and_blocks_remote_start(simulator, collector):
    """Local emergency stop immediately trips FAULT and blocks all subsequent remote START commands until reset."""
    simulator.motor_status = "ON"
    simulator.flow_rate = 40.0

    # 1. Trigger local physical emergency stop
    simulator.trigger_emergency_stop("Physical E-Stop switch activated")
    assert simulator.emergency_stop_latched is True
    assert simulator.motor_status == "FAULT"
    assert simulator.flow_rate == 0.0

    # 2. Remote START command attempted while latched
    cmd_id = str(uuid.uuid4())
    payload = {"command_id": cmd_id, "command_type": "START", "motor_code": "PUMP_01"}

    success = simulator.process_command(payload)
    assert success is False
    assert simulator.motor_status == "FAULT"

    acks = collector.get_messages_by_topic_suffix("/ack")
    assert len(acks) == 1
    assert acks[0]["payload"]["status"] == "FAILED"
    assert "Emergency stop is latched" in acks[0]["payload"]["error_message"]

    # 3. Explicit local reset clears latch
    simulator.reset_emergency_stop()
    assert simulator.emergency_stop_latched is False
    assert simulator.motor_status == "OFF"

    # 4. START command succeeds after reset
    cmd_id_2 = str(uuid.uuid4())
    success_after_reset = simulator.process_command({"command_id": cmd_id_2, "command_type": "START", "motor_code": "PUMP_01"})
    assert success_after_reset is True
    assert simulator.motor_status == "ON"


def test_offline_safety_enforcement_without_mqtt():
    """Edge safety interlocks trigger locally even when simulator is disconnected from MQTT broker."""
    # Standalone simulator without custom publisher (pure offline)
    sim = ESP32Simulator(
        device_uid="ESP32-OFFLINE-TEST",
        motor_code="PUMP_01",
        transition_delay=0.0
    )
    sim.is_connected = False
    sim.motor_status = "ON"
    sim.flow_rate = 45.0
    sim.current = 6.5

    # Trigger high turbidity while offline
    sim.set_sensor_values(turbidity=32.0)

    # Motor must trip locally to FAULT despite no MQTT connectivity
    assert sim.motor_status == "FAULT"
    assert sim.flow_rate == 0.0

    # Verify event buffered in offline buffer
    assert len(sim.offline_event_buffer) >= 1
    assert any("/fault" in e["topic"] for e in sim.offline_event_buffer)


def test_offline_tank_full_auto_stop():
    """Tank full cutoff activates locally while offline and buffers event for reconnect."""
    sim = ESP32Simulator(device_uid="ESP32-OFFLINE-TANK", transition_delay=0.0)
    sim.is_connected = False
    sim.motor_status = "ON"

    sim.set_sensor_values(tank_level=97.5)
    assert sim.motor_status == "OFF"
    assert len(sim.offline_event_buffer) >= 1


def test_reconnection_flushes_buffered_safety_events(collector):
    """When MQTT reconnects, all offline safety events are flushed across MQTT and buffer cleared."""
    sim = ESP32Simulator(
        device_uid="ESP32-RECONNECT-01",
        transition_delay=0.0,
        mqtt_publisher=collector.publish
    )
    sim.is_connected = False
    sim.motor_status = "ON"

    # Trip while offline
    sim.set_sensor_values(tank_level=96.0)
    assert len(sim.offline_event_buffer) >= 1

    # Simulate reconnect
    sim.is_connected = True
    flushed_count = sim.flush_offline_events()
    assert flushed_count >= 1
    assert len(sim.offline_event_buffer) == 0

    fault_msgs = collector.get_messages_by_topic_suffix("/fault")
    assert len(fault_msgs) >= 1


def test_multiple_simultaneous_interlocks(simulator, collector):
    """START is safely rejected when both turbidity and tank level violations occur simultaneously."""
    simulator.turbidity = 30.0
    simulator.tank_level = 98.0

    cmd_id = str(uuid.uuid4())
    payload = {"command_id": cmd_id, "command_type": "START", "motor_code": "PUMP_01"}

    success = simulator.process_command(payload)
    assert success is False
    assert simulator.motor_status == "OFF"

    acks = collector.get_messages_by_topic_suffix("/ack")
    assert len(acks) == 1
    assert acks[0]["payload"]["status"] == "FAILED"
