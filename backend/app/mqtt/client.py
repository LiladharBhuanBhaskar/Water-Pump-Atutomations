"""
HydraControl — MQTT Client Service
Provides an asynchronous, resilient MQTT client with automatic reconnection,
graceful lifecycle management, health reporting, and message dispatch.
"""

import asyncio
import json
import logging
from typing import Optional, Callable, Coroutine, Union, Any, List
import enum
import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion

try:
    from app.core.config import settings
except ImportError:
    from backend.app.core.config import settings

logger = logging.getLogger("hydracontrol.mqtt")


class MQTTConnectionStatus(str, enum.Enum):
    """MQTT connection state enumeration."""
    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    RECONNECTING = "RECONNECTING"
    ERROR = "ERROR"


class MQTTMessage:
    """Represents an inbound or outbound MQTT message."""
    def __init__(self, topic: str, payload: bytes, qos: int = 0, retain: bool = False):
        self.topic = topic
        self.payload = payload
        self.qos = qos
        self.retain = retain

    @property
    def text(self) -> str:
        """Decode payload as utf-8 string."""
        return self.payload.decode("utf-8", errors="replace")

    def json(self) -> Any:
        """Decode payload as JSON."""
        return json.loads(self.text)


class MQTTClientService:
    """
    Asynchronous MQTT Client Service managing connection lifecycle,
    threadsafe message dispatching, subscriptions, and auto-reconnection.
    """

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        client_id: Optional[str] = None,
        keepalive: Optional[int] = None,
    ):
        self.host = host or settings.MQTT_BROKER_HOST
        self.port = port or settings.MQTT_BROKER_PORT
        self.username = username if username is not None else settings.MQTT_USERNAME
        self.password = password if password is not None else settings.MQTT_PASSWORD
        self.client_id = client_id or settings.MQTT_CLIENT_ID
        self.keepalive = keepalive or settings.MQTT_KEEPALIVE

        self.status = MQTTConnectionStatus.DISCONNECTED
        self._client: Optional[mqtt.Client] = None
        self._is_running = False
        self._message_queue: Optional[asyncio.Queue[MQTTMessage]] = None
        self._dispatch_task: Optional[asyncio.Task] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._callbacks: List[Callable[[MQTTMessage], Coroutine[Any, Any, None]]] = []
        self._subscriptions: set[tuple[str, int]] = set()

    @property
    def is_connected(self) -> bool:
        """Return True if currently connected to MQTT broker."""
        return self.status == MQTTConnectionStatus.CONNECTED

    def add_message_callback(self, callback: Callable[[MQTTMessage], Coroutine[Any, Any, None]]) -> None:
        """Register an async callback invoked on every incoming message."""
        if callback not in self._callbacks:
            self._callbacks.append(callback)

    def remove_message_callback(self, callback: Callable[[MQTTMessage], Coroutine[Any, Any, None]]) -> None:
        """Remove a previously registered async callback."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    async def start(self) -> None:
        """Initialize the MQTT client, start network loop and message dispatcher."""
        if self._is_running:
            logger.warning("MQTT client service is already running.")
            return

        self._loop = asyncio.get_running_loop()
        self._message_queue = asyncio.Queue()
        self._is_running = True
        self.status = MQTTConnectionStatus.CONNECTING

        # Initialize Paho Client with Version 2 Callback API
        self._client = mqtt.Client(
            callback_api_version=CallbackAPIVersion.VERSION2,
            client_id=self.client_id,
            clean_session=True
        )

        if self.username:
            self._client.username_pw_set(self.username, self.password)

        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message
        self._client.on_subscribe = self._on_subscribe
        self._client.on_publish = self._on_publish

        # Start async worker for dispatching messages
        self._dispatch_task = asyncio.create_task(self._process_message_queue())

        try:
            logger.info(f"Connecting to MQTT Broker at {self.host}:{self.port} (Client ID: {self.client_id})...")
            self._client.connect_async(self.host, self.port, keepalive=self.keepalive)
            self._client.loop_start()
        except Exception as e:
            logger.error(f"Failed to initiate MQTT connection: {e}")
            self.status = MQTTConnectionStatus.ERROR

    async def stop(self) -> None:
        """Gracefully disconnect MQTT client and terminate worker tasks."""
        self._is_running = False
        self.status = MQTTConnectionStatus.DISCONNECTED

        if self._client is not None:
            try:
                self._client.loop_stop()
                self._client.disconnect()
            except Exception as e:
                logger.warning(f"Error during MQTT client disconnect: {e}")
            self._client = None

        if self._dispatch_task is not None:
            self._dispatch_task.cancel()
            try:
                await self._dispatch_task
            except asyncio.CancelledError:
                pass
            self._dispatch_task = None

        logger.info("MQTT client service stopped.")

    async def subscribe(self, topic: str, qos: int = 1) -> bool:
        """Subscribe to an MQTT topic pattern."""
        self._subscriptions.add((topic, qos))
        if self._client is not None and self.is_connected:
            res, _ = self._client.subscribe(topic, qos=qos)
            return res == mqtt.MQTT_ERR_SUCCESS
        return True

    async def unsubscribe(self, topic: str) -> bool:
        """Unsubscribe from an MQTT topic."""
        self._subscriptions = {(t, q) for (t, q) in self._subscriptions if t != topic}
        if self._client is not None and self.is_connected:
            res, _ = self._client.unsubscribe(topic)
            return res == mqtt.MQTT_ERR_SUCCESS
        return True

    async def publish(
        self,
        topic: str,
        payload: Union[str, bytes, dict, list],
        qos: int = 1,
        retain: bool = False
    ) -> bool:
        """Publish a payload to an MQTT topic."""
        if not self.is_connected or self._client is None:
            logger.warning(f"Cannot publish to '{topic}': MQTT client is not connected.")
            return False

        if isinstance(payload, (dict, list)):
            formatted_payload = json.dumps(payload).encode("utf-8")
        elif isinstance(payload, str):
            formatted_payload = payload.encode("utf-8")
        elif isinstance(payload, bytes):
            formatted_payload = payload
        else:
            formatted_payload = str(payload).encode("utf-8")

        try:
            info = self._client.publish(topic, formatted_payload, qos=qos, retain=retain)
            return info.rc == mqtt.MQTT_ERR_SUCCESS
        except Exception as e:
            logger.error(f"MQTT publish error on topic '{topic}': {e}")
            return False

    def get_health_status(self) -> dict[str, Any]:
        """Return diagnostic health info for probes and monitoring."""
        return {
            "status": self.status.value,
            "connected": self.is_connected,
            "broker_host": self.host,
            "broker_port": self.port,
            "client_id": self.client_id,
            "subscriptions_count": len(self._subscriptions)
        }

    # =========================================================================
    # Paho Internal Callbacks (Threadsafe async queue bridge)
    # =========================================================================

    def _on_connect(self, client: mqtt.Client, userdata: Any, flags: Any, reason_code: Any, properties: Any = None) -> None:
        if reason_code == 0:
            logger.info(f"MQTT Connected successfully to {self.host}:{self.port}")
            self.status = MQTTConnectionStatus.CONNECTED
            # Restore subscriptions upon connection or reconnection
            for topic, qos in self._subscriptions:
                client.subscribe(topic, qos=qos)
                logger.info(f"Subscribed to MQTT topic '{topic}' (QoS {qos})")
        else:
            logger.error(f"MQTT connection failed with reason code: {reason_code}")
            self.status = MQTTConnectionStatus.ERROR

    def _on_disconnect(self, client: mqtt.Client, userdata: Any, flags: Any, reason_code: Any, properties: Any = None) -> None:
        if self._is_running:
            logger.warning(f"MQTT disconnected unexpectedly (rc: {reason_code}). Reconnecting in background...")
            self.status = MQTTConnectionStatus.RECONNECTING
        else:
            logger.info("MQTT disconnected cleanly.")
            self.status = MQTTConnectionStatus.DISCONNECTED

    def _on_message(self, client: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage) -> None:
        if not self._is_running or self._loop is None or self._message_queue is None:
            return

        message = MQTTMessage(
            topic=msg.topic,
            payload=msg.payload,
            qos=msg.qos,
            retain=msg.retain
        )

        try:
            self._loop.call_soon_threadsafe(self._message_queue.put_nowait, message)
        except Exception as e:
            logger.error(f"Error enqueueing incoming MQTT message from '{msg.topic}': {e}")

    def _on_subscribe(self, client: mqtt.Client, userdata: Any, mid: int, reason_codes: Any, properties: Any = None) -> None:
        logger.debug(f"MQTT Subscription acknowledged (mid={mid}, codes={reason_codes})")

    def _on_publish(self, client: mqtt.Client, userdata: Any, mid: int, reason_code: Any = None, properties: Any = None) -> None:
        logger.debug(f"MQTT Publish acknowledged (mid={mid})")

    # =========================================================================
    # Async Message Queue Consumer
    # =========================================================================

    async def _process_message_queue(self) -> None:
        """Continuously consume incoming MQTT messages from queue and dispatch to callbacks."""
        logger.info("MQTT message queue processor started.")
        while self._is_running:
            try:
                msg = await self._message_queue.get()
                for cb in self._callbacks:
                    try:
                        await cb(msg)
                    except Exception as e:
                        logger.error(f"Unhandled error in MQTT message callback for topic '{msg.topic}': {e}", exc_info=True)
                self._message_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Unexpected error in MQTT message queue consumer: {e}")
                await asyncio.sleep(0.01)


# Global singleton instance
mqtt_client_service = MQTTClientService()
