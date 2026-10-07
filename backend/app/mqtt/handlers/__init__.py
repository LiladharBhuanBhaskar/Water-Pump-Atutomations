"""
HydraControl — Inbound MQTT Handlers Registration
"""

import logging
from app.mqtt.client import mqtt_client_service, MQTTClientService
from app.mqtt.router import mqtt_router, MQTTRouter

# Import all handler modules to register routes on mqtt_router
from app.mqtt.handlers.heartbeat_handler import handle_device_heartbeat
from app.mqtt.handlers.telemetry_handler import handle_device_telemetry
from app.mqtt.handlers.ack_handler import handle_device_ack
from app.mqtt.handlers.status_handler import handle_device_status
from app.mqtt.handlers.fault_handler import handle_device_fault

logger = logging.getLogger("hydracontrol.mqtt.handlers")


async def setup_mqtt_handlers(
    client: MQTTClientService = mqtt_client_service,
    router: MQTTRouter = mqtt_router
) -> None:
    """
    Connect the MQTT router to the MQTT client service and subscribe
    to all required MQTT topic wildcards.
    """
    # Connect router dispatcher to client callback
    client.add_message_callback(router.route_message)

    # Subscribe to required wildcard patterns
    wildcards = router.get_subscription_wildcards()
    for topic in wildcards:
        await client.subscribe(topic, qos=1)
        logger.info(f"MQTT handler auto-subscribed to wildcard: {topic}")


__all__ = [
    "setup_mqtt_handlers",
    "handle_device_heartbeat",
    "handle_device_telemetry",
    "handle_device_ack",
    "handle_device_status",
    "handle_device_fault",
]
