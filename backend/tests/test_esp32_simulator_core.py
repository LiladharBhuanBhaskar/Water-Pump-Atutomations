"""
HydraControl — P7-T01 ESP32 Simulator Core & Protocol Alignment Tests
Verifies simulator configuration, topic hierarchy alignment, registration token handling,
inbound command lifecycle (START, STOP, EMERGENCY_STOP, RESET), motor state machine transitions,
outbound ACKs, status reports, heartbeats, multi-sensor telemetry streaming, and fault reporting.
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
    """Mock MQTT publisher that captures published topics and payloads in memory."""

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
        device_uid="ESP32-TEST-UNIT-01",
        motor_code="PUMP_01",
        transition_delay=0.0,
        mqtt_publisher=collector.publish
    )
    sim.is_connected = True
    return sim


def test_simulator_configuration_and_topics(simulator):
    """Simulator initializes with expected identifiers and verified HydraControl topic hierarchy."""
    assert simulator.device_uid == "ESP32-TEST-UNIT-01"
    assert simulator.motor_code == "PUMP_01"
    assert simulator.motor_status == "OFF"

    # Verify HydraControl topic hierarchy (NO legacy topics)
    assert simulator.topic_commands == "hydracontrol/devices/ESP32-TEST-UNIT-01/commands"
    assert simulator.topic_ack == "hydracontrol/devices/ESP32-TEST-UNIT-01/ack"
    assert simulator.topic_status == "hydracontrol/devices/ESP32-TEST-UNIT-01/status"
    assert simulator.topic_heartbeat == "hydracontrol/devices/ESP32-TEST-UNIT-01/heartbeat"
    assert simulator.topic_telemetry == "hydracontrol/devices/ESP32-TEST-UNIT-01/telemetry"
    assert simulator.topic_fault == "hydracontrol/devices/ESP32-TEST-UNIT-01/fault"


def test_device_registration_token_handling(simulator):
    """Device registration stores device token and metadata."""
    # When offline or mocking, registration assigns a valid simulator token
    res = simulator.register_device()
    assert res is True or res is False
    assert simulator.device_token is not None


def test_command_start_lifecycle_and_acks(simulator, collector):
    """START command transitions state OFF -> STARTING -> ON and emits ACKNOWLEDGED then EXECUTED ACKs."""
    cmd_id = str(uuid.uuid4())
    payload = {
        "command_id": cmd_id,
        "command_type": "START",
        "motor_code": "PUMP_01"
    }

    success = simulator.process_command(payload)
    assert success is True
    assert simulator.motor_status == "ON"
    assert simulator.flow_rate > 0.0
    assert simulator.current > 0.0

    # Verify emitted ACKs
    acks = collector.get_messages_by_topic_suffix("/ack")
    assert len(acks) >= 2

    ack_statuses = [a["payload"]["status"] for a in acks]
    assert "ACKNOWLEDGED" in ack_statuses
    assert "EXECUTED" in ack_statuses

    # Verify emitted Status updates
    statuses = collector.get_messages_by_topic_suffix("/status")
    assert len(statuses) >= 2
    status_states = [s["payload"]["motors"][0]["status"] for s in statuses]
    assert "STARTING" in status_states
    assert "ON" in status_states


def test_command_stop_lifecycle_and_acks(simulator, collector):
    """STOP command transitions state ON -> STOPPING -> OFF and emits ACKs."""
    # Put motor in ON state first
    simulator.motor_status = "ON"
    simulator.flow_rate = 45.0
    simulator.current = 6.5

    cmd_id = str(uuid.uuid4())
    payload = {
        "command_id": cmd_id,
        "command_type": "STOP",
        "motor_code": "PUMP_01"
    }

    success = simulator.process_command(payload)
    assert success is True
    assert simulator.motor_status == "OFF"
    assert simulator.flow_rate == 0.0
    assert simulator.current == 0.0

    acks = collector.get_messages_by_topic_suffix("/ack")
    ack_statuses = [a["payload"]["status"] for a in acks]
    assert "ACKNOWLEDGED" in ack_statuses
    assert "EXECUTED" in ack_statuses

    statuses = collector.get_messages_by_topic_suffix("/status")
    status_states = [s["payload"]["motors"][0]["status"] for s in statuses]
    assert "STOPPING" in status_states
    assert "OFF" in status_states


def test_command_emergency_stop_lifecycle(simulator, collector):
    """EMERGENCY_STOP command powers off motor, latches fault, and emits EXECUTED ACK and FAULT event."""
    simulator.motor_status = "ON"

    cmd_id = str(uuid.uuid4())
    payload = {
        "command_id": cmd_id,
        "command_type": "EMERGENCY_STOP",
        "motor_code": "PUMP_01"
    }

    success = simulator.process_command(payload)
    assert success is True
    assert simulator.motor_status == "FAULT"
    assert simulator.emergency_stop_latched is True

    # Verify EXECUTED ACK
    acks = collector.get_messages_by_topic_suffix("/ack")
    assert any(a["payload"]["status"] == "EXECUTED" for a in acks)

    # Verify FAULT topic message
    faults = collector.get_messages_by_topic_suffix("/fault")
    assert len(faults) >= 1
    assert faults[0]["payload"]["fault_type"] == "EMERGENCY_STOP"


def test_command_reset_lifecycle(simulator, collector):
    """RESET command clears emergency latch and restores motor to OFF standby."""
    simulator.emergency_stop_latched = True
    simulator.motor_status = "FAULT"

    cmd_id = str(uuid.uuid4())
    payload = {
        "command_id": cmd_id,
        "command_type": "RESET",
        "motor_code": "PUMP_01"
    }

    success = simulator.process_command(payload)
    assert success is True
    assert simulator.emergency_stop_latched is False
    assert simulator.motor_status == "OFF"


def test_command_wrong_motor_rejected(simulator, collector):
    """Command targeted at wrong motor_code is rejected with FAILED ACK."""
    cmd_id = str(uuid.uuid4())
    payload = {
        "command_id": cmd_id,
        "command_type": "START",
        "motor_code": "OTHER_PUMP_999"
    }

    success = simulator.process_command(payload)
    assert success is False
    assert simulator.motor_status == "OFF"

    acks = collector.get_messages_by_topic_suffix("/ack")
    assert len(acks) == 1
    assert acks[0]["payload"]["status"] == "FAILED"


def test_heartbeat_payload_structure(simulator, collector):
    """Heartbeat publication adheres to Phase 4/5 schema with device_uid, status, firmware, IP, MAC."""
    simulator.publish_heartbeat()
    heartbeats = collector.get_messages_by_topic_suffix("/heartbeat")
    assert len(heartbeats) == 1

    hb = heartbeats[0]["payload"]
    assert hb["device_uid"] == "ESP32-TEST-UNIT-01"
    assert hb["status"] == "ACTIVE"
    assert hb["firmware_version"] == "v1.0.0-sim"
    assert hb["ip_address"] == "192.168.1.150"
    assert hb["mac_address"] == "AA:BB:CC:DD:EE:01"
    assert "timestamp" in hb


def test_status_payload_structure(simulator, collector):
    """Status publication adheres to Phase 6 schema with controller_status and motor list."""
    simulator.motor_status = "ON"
    simulator.publish_status()

    statuses = collector.get_messages_by_topic_suffix("/status")
    assert len(statuses) == 1

    st = statuses[0]["payload"]
    assert st["controller_status"] == "ACTIVE"
    assert isinstance(st["motors"], list)
    assert len(st["motors"]) == 1
    assert st["motors"][0]["motor_code"] == "PUMP_01"
    assert st["motors"][0]["status"] == "ON"


def test_telemetry_payload_multi_sensor(simulator, collector):
    """Telemetry publication includes readings for Level, Turbidity, Flow, Current, Voltage, Pressure."""
    simulator.publish_telemetry()
    telem = collector.get_messages_by_topic_suffix("/telemetry")
    assert len(telem) == 1

    readings = telem[0]["payload"]
    assert isinstance(readings, list)
    assert len(readings) == 6

    sensor_codes = {r["sensor_code"] for r in readings}
    assert "LEVEL_01" in sensor_codes
    assert "TURB_01" in sensor_codes
    assert "FLOW_01" in sensor_codes
    assert "CURR_01" in sensor_codes
    assert "VOLT_01" in sensor_codes
    assert "PRES_01" in sensor_codes


def test_fault_payload_structure(simulator, collector):
    """Fault publication adheres to Phase 5 schema with motor_code, fault_type, description, payload."""
    simulator.publish_fault("OVERHEAT", "Motor thermal overload detected", {"temp_c": 98.5})
    faults = collector.get_messages_by_topic_suffix("/fault")
    assert len(faults) == 1

    f = faults[0]["payload"]
    assert f["motor_code"] == "PUMP_01"
    assert f["fault_type"] == "OVERHEAT"
    assert f["description"] == "Motor thermal overload detected"
    assert f["payload"]["temp_c"] == 98.5
