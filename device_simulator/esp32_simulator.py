"""
HydraControl — ESP32 Hardware Simulator (Phase 7)
Simulates a physical IoT controller with:
- Phase 4 Device Registration & Heartbeat integration
- Phase 5/6 Standard MQTT Topic Hierarchy (`hydracontrol/devices/{device_uid}/...`)
- Realistic motor state machine (OFF -> STARTING -> ON, ON -> STOPPING -> OFF, FAULT)
- Inbound Command Lifecycle processing (START, STOP, EMERGENCY_STOP) and ACK generation
- Real-time Telemetry streaming (Water Level, Turbidity, Flow Rate, Current, Voltage, Pressure)
- Local Edge Safety Interlocks (High Turbidity >25 NTU trip, Tank Full >=95% auto-stop, Local E-Stop latching)
- Offline autonomous protection & safe-state preservation with reconnect event flushing
"""

import os
import json
import time
import logging
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timezone

try:
    import paho.mqtt.client as mqtt
except ImportError:
    mqtt = None

try:
    import requests
except ImportError:
    requests = None

logging.basicConfig(level=logging.INFO, format="%(asctime)s [ESP32-SIM] %(levelname)s: %(message)s")
logger = logging.getLogger("esp32_simulator")


class ESP32Simulator:
    """
    ESP32 Edge Device Simulator for HydraControl.
    Emulates hardware sensors, motor contactors, on-device safety interlocks, and MQTT communications.
    """

    def __init__(
        self,
        device_uid: str = "ESP32-SIM-001",
        motor_code: str = "PUMP_01",
        broker: str = "localhost",
        port: int = 1883,
        api_base_url: str = "http://localhost:8000/api/v1",
        firmware_version: str = "v1.0.0-sim",
        ip_address: str = "192.168.1.150",
        mac_address: str = "AA:BB:CC:DD:EE:01",
        transition_delay: float = 0.0,
        mqtt_publisher: Optional[Callable[[str, Dict[str, Any], int], bool]] = None,
    ):
        self.device_uid = os.getenv("SIMULATOR_DEVICE_UID", device_uid)
        self.motor_code = os.getenv("SIMULATOR_MOTOR_CODE", motor_code)
        self.broker = os.getenv("MQTT_BROKER_HOST", broker)
        self.port = int(os.getenv("MQTT_BROKER_PORT", port))
        self.api_base_url = os.getenv("API_BASE_URL", api_base_url)
        self.firmware_version = firmware_version
        self.ip_address = ip_address
        self.mac_address = mac_address
        self.transition_delay = transition_delay

        # Authentication / Token
        self.device_token: Optional[str] = None
        self.station_id: Optional[str] = None
        self.controller_id: Optional[str] = None

        # Device Operational State
        self.controller_status: str = "ACTIVE"
        self.motor_status: str = "OFF"  # OFF, STARTING, ON, STOPPING, FAULT, OFFLINE
        self.emergency_stop_latched: bool = False
        self.is_connected: bool = False

        # Sensor readings (simulated physical values)
        self.tank_level: float = 65.0      # Water level %
        self.turbidity: float = 12.0       # NTU
        self.flow_rate: float = 0.0        # L/min
        self.voltage: float = 230.0        # Volts
        self.current: float = 0.0          # Amperes
        self.pressure: float = 0.0         # Bar

        # Configurable local safety thresholds
        self.max_turbidity_threshold: float = 25.0  # Turbidity > 25.0 NTU trips safety
        self.max_tank_level: float = 95.0          # Level >= 95.0% triggers auto-stop
        self.min_tank_level: float = 10.0          # Level <= 10.0% trips dry run

        # Offline event buffer (stores safety trips when disconnected from broker)
        self.offline_event_buffer: List[Dict[str, Any]] = []

        # Published messages tracking for testing/diagnostics
        self.published_history: List[Dict[str, Any]] = []
        self._custom_publisher = mqtt_publisher

        # MQTT Client initialization
        self.client = None
        if mqtt is not None:
            try:
                from paho.mqtt.enums import CallbackAPIVersion
                self.client = mqtt.Client(
                    callback_api_version=CallbackAPIVersion.VERSION2,
                    client_id=f"esp32_{self.device_uid}"
                )
            except (ImportError, AttributeError):
                self.client = mqtt.Client(
                    client_id=f"esp32_{self.device_uid}",
                    protocol=getattr(mqtt, "MQTTv311", 4)
                )
            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            self.client.on_message = self._on_message

    # =========================================================================
    # Phase 4 API Device Registration
    # =========================================================================

    def register_device(self, api_url: Optional[str] = None) -> bool:
        """
        Registers the simulator with the HydraControl backend via Phase 4 registration API.
        Retrieves and stores the signed device JWT token.
        """
        url = (api_url or self.api_base_url).rstrip("/") + "/devices/register"
        payload = {
            "device_uid": self.device_uid,
            "firmware_version": self.firmware_version,
            "ip_address": self.ip_address,
            "mac_address": self.mac_address,
            "controller_type": "ESP32"
        }

        if requests is None:
            logger.warning("Requests library not available; simulating offline registration.")
            self.device_token = f"sim-dev-token-{self.device_uid}"
            return True

        try:
            resp = requests.post(url, json=payload, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                self.device_token = data.get("device_token")
                self.controller_id = str(data.get("controller_id"))
                self.station_id = str(data.get("station_id"))
                logger.info(f"Successfully registered device '{self.device_uid}'. Token obtained.")
                return True
            else:
                logger.error(f"Registration failed ({resp.status_code}): {resp.text}")
                return False
        except Exception as e:
            logger.warning(f"Could not contact registration endpoint '{url}': {e}")
            self.device_token = f"sim-dev-token-{self.device_uid}"
            return False

    # =========================================================================
    # Phase 5 / Phase 6 MQTT Topic Handlers
    # =========================================================================

    @property
    def topic_commands(self) -> str:
        return f"hydracontrol/devices/{self.device_uid}/commands"

    @property
    def topic_ack(self) -> str:
        return f"hydracontrol/devices/{self.device_uid}/ack"

    @property
    def topic_status(self) -> str:
        return f"hydracontrol/devices/{self.device_uid}/status"

    @property
    def topic_heartbeat(self) -> str:
        return f"hydracontrol/devices/{self.device_uid}/heartbeat"

    @property
    def topic_telemetry(self) -> str:
        return f"hydracontrol/devices/{self.device_uid}/telemetry"

    @property
    def topic_fault(self) -> str:
        return f"hydracontrol/devices/{self.device_uid}/fault"

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        """Callback when connected to MQTT Broker."""
        # reason_code can be an int or ReasonCode object with value 0
        rc = getattr(reason_code, "value", reason_code)
        if rc == 0:
            self.is_connected = True
            logger.info(f"Connected to MQTT broker ({self.broker}:{self.port})")
            client.subscribe(self.topic_commands, qos=1)
            logger.info(f"Subscribed to verified topic: {self.topic_commands}")

            self.publish_heartbeat()
            self.publish_status()
            self.flush_offline_events()
        else:
            self.is_connected = False
            logger.warning(f"MQTT connection failed with return code {rc}")

    def _on_disconnect(self, client, userdata, flags, reason_code=None, properties=None):
        """Callback when disconnected from MQTT broker."""
        self.is_connected = False
        rc = getattr(reason_code, "value", reason_code)
        logger.warning(f"Disconnected from MQTT broker (rc={rc}). Local safety interlocks remain active.")

    def _on_message(self, client, userdata, msg):
        """Callback when incoming message arrives from MQTT."""
        try:
            if msg.topic != self.topic_commands:
                logger.warning(f"Ignoring message on unexpected topic '{msg.topic}'")
                return

            payload_raw = msg.payload.decode("utf-8")
            payload = json.loads(payload_raw)
            logger.info(f"Received command payload: {payload}")
            self.process_command(payload)
        except Exception as e:
            logger.error(f"Error parsing inbound command: {e}", exc_info=True)

    # =========================================================================
    # Command Processing & Motor State Machine
    # =========================================================================

    def process_command(self, payload: Dict[str, Any]) -> bool:
        """
        Processes an inbound motor command according to Phase 6 command lifecycle.
        Validates command payload, checks local safety interlocks, transitions state,
        and publishes ACKs (ACKNOWLEDGED -> EXECUTED or FAILED).
        """
        if not isinstance(payload, dict):
            logger.warning(f"Invalid non-dict command payload: {payload}")
            return False

        command_id = str(payload.get("command_id", "")).strip()
        command_type = str(payload.get("command_type") or payload.get("command", "")).strip().upper()
        target_motor_code = str(payload.get("motor_code", "")).strip().upper()

        if not command_id:
            logger.warning("Rejecting command with missing command_id")
            return False

        # Validate motor code if target specified
        if target_motor_code and target_motor_code != self.motor_code.upper():
            logger.warning(f"Command target motor '{target_motor_code}' does not match simulator motor '{self.motor_code}'")
            self.publish_ack(command_id, "FAILED", f"Motor '{target_motor_code}' not found on this device")
            return False

        if command_type == "START":
            return self._handle_start_command(command_id)
        elif command_type == "STOP":
            return self._handle_stop_command(command_id)
        elif command_type in ("EMERGENCY_STOP", "ESTOP"):
            return self._handle_emergency_stop_command(command_id)
        elif command_type == "RESET":
            return self._handle_reset_command(command_id)
        else:
            logger.warning(f"Unsupported command type '{command_type}'")
            self.publish_ack(command_id, "FAILED", f"Unknown command type '{command_type}'")
            return False

    def _handle_start_command(self, command_id: str) -> bool:
        """Processes a START command with local safety verification."""
        # 1. Emergency stop active check
        if self.emergency_stop_latched:
            logger.warning("START rejected: Emergency stop is active locally.")
            self.publish_ack(command_id, "FAILED", "START rejected: Emergency stop is latched locally")
            return False

        # 2. Local Safety Interlock: High Turbidity (>25 NTU)
        if self.turbidity > self.max_turbidity_threshold:
            msg = f"START rejected: Turbidity ({self.turbidity:.1f} NTU) exceeds limit ({self.max_turbidity_threshold:.1f} NTU)"
            logger.warning(msg)
            self.publish_ack(command_id, "FAILED", msg)
            self.publish_fault("FAULT", msg, {"turbidity": self.turbidity, "limit": self.max_turbidity_threshold})
            return False

        # 3. Local Safety Interlock: Tank Full (>=95%)
        if self.tank_level >= self.max_tank_level:
            msg = f"START rejected: Tank is FULL ({self.tank_level:.1f}% >= {self.max_tank_level:.1f}%)"
            logger.warning(msg)
            self.publish_ack(command_id, "FAILED", msg)
            self.publish_fault("FAULT", msg, {"tank_level": self.tank_level, "limit": self.max_tank_level})
            return False

        # 4. Local Safety Interlock: Tank Empty (<=10%)
        if self.tank_level <= self.min_tank_level:
            msg = f"START rejected: Source tank is EMPTY ({self.tank_level:.1f}% <= {self.min_tank_level:.1f}%)"
            logger.warning(msg)
            self.publish_ack(command_id, "FAILED", msg)
            return False

        # 5. Accept & Acknowledge
        self.publish_ack(command_id, "ACKNOWLEDGED", "Command received. Starting motor contactor sequence.")
        self.motor_status = "STARTING"
        self.publish_status()

        if self.transition_delay > 0:
            time.sleep(self.transition_delay)

        # 6. Complete transition to ON
        self.motor_status = "ON"
        self.flow_rate = 45.2
        self.current = 6.5
        self.pressure = 3.2
        self.publish_status()
        self.publish_ack(command_id, "EXECUTED", "Motor is now RUNNING")
        logger.info(f"Motor '{self.motor_code}' successfully started and is now ON.")
        return True

    def _handle_stop_command(self, command_id: str) -> bool:
        """Processes a STOP command."""
        self.publish_ack(command_id, "ACKNOWLEDGED", "Command received. Initiating motor stop sequence.")
        self.motor_status = "STOPPING"
        self.publish_status()

        if self.transition_delay > 0:
            time.sleep(self.transition_delay)

        self.motor_status = "OFF"
        self.flow_rate = 0.0
        self.current = 0.0
        self.pressure = 0.0
        self.publish_status()
        self.publish_ack(command_id, "EXECUTED", "Motor has STOPPED")
        logger.info(f"Motor '{self.motor_code}' successfully stopped and is now OFF.")
        return True

    def _handle_emergency_stop_command(self, command_id: str) -> bool:
        """Processes a remote EMERGENCY_STOP command."""
        self.trigger_emergency_stop("Remote emergency stop command received")
        self.publish_ack(command_id, "EXECUTED", "Emergency stop executed. Motor powered off and latched.")
        return True

    def _handle_reset_command(self, command_id: str) -> bool:
        """Processes a RESET command to clear latched faults."""
        self.reset_emergency_stop()
        self.publish_ack(command_id, "EXECUTED", "Faults reset. Motor in standby OFF state.")
        return True

    # =========================================================================
    # Edge Safety Interlocks & Offline Autonomous Protection (P7-T02)
    # =========================================================================

    def check_local_safety(self) -> None:
        """
        Continuous local safety monitor loop.
        Evaluates physical sensor readings against safety limits and trips contactors
        autonomously without requiring backend or MQTT connectivity.
        """
        # Tank Full Interlock (>=95% while running)
        if self.motor_status in ("ON", "STARTING") and self.tank_level >= self.max_tank_level:
            logger.warning(f"LOCAL SAFETY TRIP: Tank level ({self.tank_level:.1f}%) reached FULL threshold. Initiating auto-stop.")
            self.motor_status = "OFF"
            self.flow_rate = 0.0
            self.current = 0.0
            self.pressure = 0.0
            self.publish_status()
            self.publish_fault(
                "FAULT",
                f"Automatic cutoff: Tank level reached {self.tank_level:.1f}%",
                {"tank_level": self.tank_level, "trip_threshold": self.max_tank_level}
            )

        # High Turbidity Interlock (>25 NTU while running)
        if self.motor_status in ("ON", "STARTING") and self.turbidity > self.max_turbidity_threshold:
            logger.warning(f"LOCAL SAFETY TRIP: Turbidity ({self.turbidity:.1f} NTU) exceeded safety threshold. Tripping motor FAULT.")
            self.motor_status = "FAULT"
            self.flow_rate = 0.0
            self.current = 0.0
            self.pressure = 0.0
            self.publish_status()
            self.publish_fault(
                "FAULT",
                f"High turbidity trip: {self.turbidity:.1f} NTU",
                {"turbidity": self.turbidity, "limit": self.max_turbidity_threshold}
            )

    def trigger_emergency_stop(self, reason: str = "Local physical emergency stop button pressed") -> None:
        """
        Trips local emergency stop immediately.
        Latches device in FAULT state to prevent remote starts until explicitly reset.
        Works offline or online.
        """
        self.emergency_stop_latched = True
        self.motor_status = "FAULT"
        self.flow_rate = 0.0
        self.current = 0.0
        self.pressure = 0.0
        logger.warning(f"EMERGENCY STOP TRIGGERED: {reason}")
        self.publish_status()
        self.publish_fault("EMERGENCY_STOP", reason, {"latched": True})

    def reset_emergency_stop(self) -> None:
        """Clears the local emergency stop latch and returns motor to OFF standby."""
        self.emergency_stop_latched = False
        if self.motor_status == "FAULT":
            self.motor_status = "OFF"
        logger.info("Emergency stop latch cleared. Motor restored to OFF standby.")
        self.publish_status()
        self.publish_fault("RESET", "Local emergency stop reset", {"latched": False})

    def set_sensor_values(
        self,
        tank_level: Optional[float] = None,
        turbidity: Optional[float] = None,
        voltage: Optional[float] = None
    ) -> None:
        """Updates simulated physical sensor readings and triggers immediate local safety checks."""
        if tank_level is not None:
            self.tank_level = float(tank_level)
        if turbidity is not None:
            self.turbidity = float(turbidity)
        if voltage is not None:
            self.voltage = float(voltage)

        # Run immediate edge safety check
        self.check_local_safety()

    # =========================================================================
    # Outbound MQTT Publishing Methods
    # =========================================================================

    def _publish(self, topic: str, payload: Dict[str, Any], qos: int = 1) -> bool:
        """Internal helper to publish MQTT payload or buffer when offline."""
        record = {
            "topic": topic,
            "payload": payload,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "online": self.is_connected
        }
        self.published_history.append(record)

        if not self.is_connected:
            # Offline mode: buffer safety-critical events for reconnection
            if "/fault" in topic or "/status" in topic:
                self.offline_event_buffer.append({"topic": topic, "payload": payload})
            return False

        if self._custom_publisher is not None:
            return self._custom_publisher(topic, payload, qos)

        if self.client is not None and self.is_connected:
            try:
                msg_json = json.dumps(payload)
                self.client.publish(topic, msg_json, qos=qos)
                return True
            except Exception as e:
                logger.error(f"Failed to publish to '{topic}': {e}")
                return False
        return False

    def publish_ack(self, command_id: str, status: str, message: str = "") -> bool:
        """Publishes command execution ACK according to Phase 6 protocol."""
        payload = {
            "command_id": command_id,
            "status": status.upper(),
            "message": message,
            "error_message": message if status.upper() in ("FAILED", "REJECTED", "ERROR") else None,
            "motor_code": self.motor_code,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        logger.info(f"Publishing ACK: {payload['status']} for command '{command_id}'")
        return self._publish(self.topic_ack, payload, qos=1)

    def publish_status(self) -> bool:
        """Publishes controller & motor operational state to Phase 6 status handler."""
        payload = {
            "controller_status": self.controller_status,
            "motors": [
                {
                    "motor_code": self.motor_code,
                    "status": self.motor_status,
                    "flow_rate": self.flow_rate,
                    "current": self.current,
                    "voltage": self.voltage,
                    "pressure": self.pressure
                }
            ],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        return self._publish(self.topic_status, payload, qos=1)

    def publish_heartbeat(self) -> bool:
        """Publishes device liveness heartbeat to Phase 4/5 heartbeat handler."""
        payload = {
            "device_uid": self.device_uid,
            "status": self.controller_status,
            "firmware_version": self.firmware_version,
            "ip_address": self.ip_address,
            "mac_address": self.mac_address,
            "uptime_seconds": int(time.time()),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        return self._publish(self.topic_heartbeat, payload, qos=0)

    def publish_telemetry(self) -> bool:
        """Publishes multi-sensor readings to Phase 5 telemetry handler."""
        now_iso = datetime.now(timezone.utc).isoformat()
        readings = [
            {"sensor_code": "LEVEL_01", "value": round(self.tank_level, 2), "unit": "%", "occurred_at": now_iso},
            {"sensor_code": "TURB_01", "value": round(self.turbidity, 2), "unit": "NTU", "occurred_at": now_iso},
            {"sensor_code": "FLOW_01", "value": round(self.flow_rate, 2), "unit": "L/min", "occurred_at": now_iso},
            {"sensor_code": "CURR_01", "value": round(self.current, 2), "unit": "A", "occurred_at": now_iso},
            {"sensor_code": "VOLT_01", "value": round(self.voltage, 2), "unit": "V", "occurred_at": now_iso},
            {"sensor_code": "PRES_01", "value": round(self.pressure, 2), "unit": "bar", "occurred_at": now_iso},
        ]
        return self._publish(self.topic_telemetry, readings, qos=0)

    def publish_fault(self, fault_type: str, description: str, details: Optional[Dict[str, Any]] = None) -> bool:
        """Publishes safety fault or emergency event to Phase 5 fault handler."""
        payload = {
            "motor_code": self.motor_code,
            "fault_type": fault_type,
            "description": description,
            "payload": details or {},
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        logger.warning(f"Publishing FAULT event: {fault_type} — {description}")
        return self._publish(self.topic_fault, payload, qos=1)

    def flush_offline_events(self) -> int:
        """Flushes buffered offline safety events across MQTT upon successful reconnection."""
        if not self.offline_event_buffer:
            return 0

        flushed = 0
        events_to_send = list(self.offline_event_buffer)
        self.offline_event_buffer.clear()

        for item in events_to_send:
            if self._publish(item["topic"], item["payload"], qos=1):
                flushed += 1

        logger.info(f"Flushed {flushed} offline safety events after reconnection.")
        return flushed

    # =========================================================================
    # Simulator Execution Loop
    # =========================================================================

    def run(self, interval_seconds: float = 5.0, max_iterations: Optional[int] = None) -> None:
        """
        Starts the simulator loop.
        Connects to MQTT, registers device, streams telemetry, and handles commands.
        """
        logger.info(f"Starting ESP32 Simulator [{self.device_uid}] -> {self.broker}:{self.port}")
        self.register_device()

        if self.client is not None:
            try:
                self.client.connect(self.broker, self.port, keepalive=60)
                self.client.loop_start()
            except Exception as e:
                logger.warning(f"Could not connect to MQTT broker '{self.broker}:{self.port}': {e}. Operating in standalone mode.")

        iterations = 0
        try:
            while max_iterations is None or iterations < max_iterations:
                self.check_local_safety()
                self.publish_heartbeat()
                self.publish_status()
                self.publish_telemetry()
                time.sleep(interval_seconds)
                iterations += 1
        except KeyboardInterrupt:
            logger.info("Simulator stopped by user.")
        finally:
            if self.client is not None:
                self.client.loop_stop()
                self.client.disconnect()


if __name__ == "__main__":
    sim = ESP32Simulator()
    sim.run()
