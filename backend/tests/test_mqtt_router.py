import pytest
from app.mqtt.client import MQTTMessage
from app.mqtt.router import (
    MQTTRouter,
    match_topic,
    compile_topic_pattern,
    build_device_heartbeat_topic,
    build_device_telemetry_topic,
    build_device_status_topic,
    build_device_event_topic,
    build_device_ack_topic,
    build_device_fault_topic,
    build_device_command_topic,
    build_device_config_topic,
    ROOT_PREFIX,
    SHORT_PREFIX
)


def test_topic_builders():
    uid = "ESP32-UNIT-01"
    assert build_device_heartbeat_topic(uid) == "hydracontrol/devices/ESP32-UNIT-01/heartbeat"
    assert build_device_telemetry_topic(uid) == "hydracontrol/devices/ESP32-UNIT-01/telemetry"
    assert build_device_status_topic(uid) == "hydracontrol/devices/ESP32-UNIT-01/status"
    assert build_device_event_topic(uid) == "hydracontrol/devices/ESP32-UNIT-01/events"
    assert build_device_ack_topic(uid) == "hydracontrol/devices/ESP32-UNIT-01/ack"
    assert build_device_fault_topic(uid) == "hydracontrol/devices/ESP32-UNIT-01/fault"
    assert build_device_command_topic(uid) == "hydracontrol/devices/ESP32-UNIT-01/commands"
    assert build_device_config_topic(uid) == "hydracontrol/devices/ESP32-UNIT-01/config"

    # Short prefix override
    assert build_device_heartbeat_topic(uid, prefix=SHORT_PREFIX) == "devices/ESP32-UNIT-01/heartbeat"


def test_match_topic_patterns():
    pattern = "hydracontrol/devices/{device_uid}/telemetry"
    matched = match_topic(pattern, "hydracontrol/devices/ESP32-HW-100/telemetry")
    assert matched is not None
    assert matched["device_uid"] == "ESP32-HW-100"

    # Non matching
    assert match_topic(pattern, "hydracontrol/devices/ESP32-HW-100/status") is None
    assert match_topic(pattern, "other/devices/ESP32-HW-100/telemetry") is None


def test_match_topic_wildcards():
    # Single level wildcard '+'
    pattern_plus = "devices/+/status"
    assert match_topic(pattern_plus, "devices/ESP-01/status") == {}
    assert match_topic(pattern_plus, "devices/ESP-01/deep/status") is None

    # Multi level wildcard '#'
    pattern_hash = "hydracontrol/#"
    assert match_topic(pattern_hash, "hydracontrol/devices/ESP-01/telemetry") == {}


@pytest.mark.asyncio
async def test_mqtt_router_route_registration_and_dispatch():
    router = MQTTRouter()
    dispatched_data = []

    @router.route("hydracontrol/devices/{device_uid}/telemetry")
    async def handle_telemetry(device_uid: str, payload: dict, **kwargs):
        dispatched_data.append({"device_uid": device_uid, "payload": payload})

    # Derive subscription wildcards
    wildcards = router.get_subscription_wildcards()
    assert "hydracontrol/devices/+/telemetry" in wildcards

    # Send matching message
    msg = MQTTMessage(
        topic="hydracontrol/devices/ESP32-ALPHA/telemetry",
        payload=b'{"level": 82.5}'
    )
    result = await router.route_message(msg)
    assert result is True
    assert len(dispatched_data) == 1
    assert dispatched_data[0]["device_uid"] == "ESP32-ALPHA"
    assert dispatched_data[0]["payload"] == {"level": 82.5}

    # Send non-matching message
    unmatched_msg = MQTTMessage(
        topic="hydracontrol/devices/ESP32-ALPHA/heartbeat",
        payload=b'{"status": "OK"}'
    )
    unmatched_result = await router.route_message(unmatched_msg)
    assert unmatched_result is False
    assert len(dispatched_data) == 1
