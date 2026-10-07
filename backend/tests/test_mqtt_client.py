import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
import paho.mqtt.client as mqtt

from app.mqtt.client import MQTTClientService, MQTTConnectionStatus, MQTTMessage


@pytest.mark.asyncio
async def test_mqtt_client_initialization_defaults():
    service = MQTTClientService(
        host="testbroker.local",
        port=1883,
        client_id="test_client_01"
    )
    assert service.host == "testbroker.local"
    assert service.port == 1883
    assert service.client_id == "test_client_01"
    assert service.status == MQTTConnectionStatus.DISCONNECTED
    assert not service.is_connected
    health = service.get_health_status()
    assert health["status"] == "DISCONNECTED"
    assert health["connected"] is False
    assert health["broker_host"] == "testbroker.local"


@pytest.mark.asyncio
async def test_mqtt_message_properties():
    raw_payload = b'{"temperature": 25.4, "status": "ok"}'
    msg = MQTTMessage(topic="hydracontrol/devices/ESP32-001/telemetry", payload=raw_payload, qos=1)
    assert msg.topic == "hydracontrol/devices/ESP32-001/telemetry"
    assert msg.text == '{"temperature": 25.4, "status": "ok"}'
    assert msg.json() == {"temperature": 25.4, "status": "ok"}
    assert msg.qos == 1
    assert msg.retain is False


@pytest.mark.asyncio
async def test_mqtt_client_subscription_tracking():
    service = MQTTClientService()
    await service.subscribe("hydracontrol/devices/+/telemetry", qos=1)
    await service.subscribe("hydracontrol/devices/+/heartbeat", qos=0)
    assert len(service._subscriptions) == 2

    await service.unsubscribe("hydracontrol/devices/+/heartbeat")
    assert len(service._subscriptions) == 1
    assert ("hydracontrol/devices/+/telemetry", 1) in service._subscriptions


@pytest.mark.asyncio
async def test_mqtt_client_callbacks_and_queue_dispatch():
    service = MQTTClientService()
    service._loop = asyncio.get_running_loop()
    service._message_queue = asyncio.Queue()
    service._is_running = True

    received_messages = []

    async def sample_callback(msg: MQTTMessage):
        received_messages.append(msg)

    service.add_message_callback(sample_callback)

    # Start processor task
    processor_task = asyncio.create_task(service._process_message_queue())

    # Feed message directly to queue
    test_msg = MQTTMessage("devices/ESP32-TEST/status", b'{"status": "ONLINE"}')
    await service._message_queue.put(test_msg)

    # Allow async loop to process
    await asyncio.sleep(0.05)

    assert len(received_messages) == 1
    assert received_messages[0].topic == "devices/ESP32-TEST/status"
    assert received_messages[0].json()["status"] == "ONLINE"

    # Stop processor task
    service._is_running = False
    processor_task.cancel()
    try:
        await processor_task
    except asyncio.CancelledError:
        pass


@pytest.mark.asyncio
async def test_mqtt_client_publish_disconnected():
    service = MQTTClientService()
    result = await service.publish("test/topic", {"key": "val"})
    assert result is False


@pytest.mark.asyncio
async def test_mqtt_client_connect_and_disconnect_lifecycle():
    with patch("paho.mqtt.client.Client") as mock_client_cls:
        mock_paho = MagicMock()
        mock_client_cls.return_value = mock_paho

        service = MQTTClientService(host="127.0.0.1", port=1883)
        await service.start()

        assert service._is_running is True
        mock_paho.connect_async.assert_called_once()
        mock_paho.loop_start.assert_called_once()

        # Simulate on_connect callback
        service._on_connect(mock_paho, None, None, 0)
        assert service.status == MQTTConnectionStatus.CONNECTED
        assert service.is_connected is True

        # Simulate publish
        mock_publish_info = MagicMock()
        mock_publish_info.rc = mqtt.MQTT_ERR_SUCCESS
        mock_paho.publish.return_value = mock_publish_info

        pub_ok = await service.publish("hydracontrol/devices/ESP-01/commands", {"action": "START"})
        assert pub_ok is True
        mock_paho.publish.assert_called_once()

        # Disconnect cleanly
        await service.stop()
        assert service.status == MQTTConnectionStatus.DISCONNECTED
        assert not service.is_connected
        mock_paho.loop_stop.assert_called_once()
        mock_paho.disconnect.assert_called_once()
