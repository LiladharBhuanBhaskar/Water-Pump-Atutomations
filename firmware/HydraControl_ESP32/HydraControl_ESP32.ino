/*
 * ======================================================================================
 *  HydraControl — Production ESP32 Controller Firmware (Arduino IDE Ready)
 *  Commercial Water Pump Automation & IoT Monitoring Platform
 * ======================================================================================
 * 
 *  QUICK SETUP GUIDE FOR ARDUINO IDE:
 *  --------------------------------------------------------------------------------------
 *  1. Open Arduino IDE (v1.8.x or v2.x).
 *  2. Go to: Tools -> Board -> ESP32 Arduino -> Select "ESP32 Dev Module" (or your ESP32 board).
 *  3. Install the 2 required libraries from: Sketch -> Include Library -> Manage Libraries:
 *     - "PubSubClient" by Nick O'Leary (version 2.8 or newer)
 *     - "ArduinoJson" by Benoît Blanchon (version 6.x or 7.x)
 *  4. Edit the WIFI_SSID and WIFI_PASSWORD below to match your Wi-Fi network or mobile hotspot.
 *  5. Connect your ESP32 via USB and select the correct COM port (Tools -> Port).
 *  6. Click the Upload button (Arrow icon).
 *  7. Open Tools -> Serial Monitor (set Baud Rate to 115200).
 * ======================================================================================
 */

#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>

// ======================================================================================
// 1. NETWORK & CLOUD CONFIGURATION
// ======================================================================================

// Wi-Fi Credentials (Change these to your Wi-Fi or phone hotspot)
const char* WIFI_SSID     = "Your_WiFi_Name";
const char* WIFI_PASSWORD = "Your_WiFi_Password";

// Remote MQTT Cloud Broker (Preconfigured to public broker for zero-config remote access)
const char* MQTT_BROKER   = "broker.emqx.io";
const int   MQTT_PORT     = 1883;
const char* MQTT_USER     = "";  // Leave blank for anonymous public broker
const char* MQTT_PASS     = "";

// Device Hardware Identity (Matches registered device in HydraControl backend)
#define DEVICE_UID         "HYDRA-PROD-ESP32-001"
#define FIRMWARE_VERSION   "1.0.0-prod"

// MQTT Standard Topics (Standard HydraControl topic hierarchy)
const char* TOPIC_COMMANDS  = "hydracontrol/devices/" DEVICE_UID "/commands";
const char* TOPIC_ACK       = "hydracontrol/devices/" DEVICE_UID "/ack";
const char* TOPIC_HEARTBEAT = "hydracontrol/devices/" DEVICE_UID "/heartbeat";
const char* TOPIC_TELEMETRY = "hydracontrol/devices/" DEVICE_UID "/telemetry";
const char* TOPIC_STATUS    = "hydracontrol/devices/" DEVICE_UID "/status";
const char* TOPIC_FAULT     = "hydracontrol/devices/" DEVICE_UID "/fault";

// ======================================================================================
// 2. HARDWARE PIN DEFINITIONS
// ======================================================================================
#define PIN_ONBOARD_LED        2   // Blue LED on ESP32 Dev Board (lights up when motor runs)
#define PIN_RELAY_MOTOR_START  25  // Drives Contactor / Relay Module (Active HIGH)
#define PIN_EMERGENCY_STOP_BTN 4   // Physical E-STOP Button (Active LOW with internal pullup)
#define PIN_FLOAT_HIGH         18  // Overhead Tank Full Float Switch (Active LOW)
#define PIN_FLOAT_LOW          19  // Source / Sump Low Float Switch (Active LOW)
#define PIN_CURRENT_SENSOR     36  // Analog Current Sensor (ACS712 / CT on GPIO 36 / VP)
#define PIN_TURBIDITY_SENSOR   39  // Analog Turbidity Sensor (GPIO 39 / VN)
#define PIN_WATER_LEVEL_ADC    33  // Analog Water Level Sensor (GPIO 33)

// Set this to TRUE if testing ESP32 on your desk without physical sensors wired yet.
// Set to FALSE when connected to physical sensors and relays.
#define BENCH_TEST_MODE        true

// Safety Thresholds
#define MAX_RUNTIME_MS              (30UL * 60UL * 1000UL) // 30 mins continuous max run
#define OVERCURRENT_THRESHOLD_AMPS  15.0f
#define MAX_TURBIDITY_NTU           25.0f
#define MIN_WATER_LEVEL_PCT         10.0f
#define MAX_WATER_LEVEL_PCT         95.0f

// ======================================================================================
// 3. MOTOR STATE & SENSOR STRUCTS
// ======================================================================================
enum MotorState {
  STATE_IDLE,
  STATE_RUNNING,
  STATE_STOPPED,
  STATE_FAULT_LOCKED
};

struct SensorReadings {
  float water_level_pct;
  float turbidity_ntu;
  float current_amps;
  float voltage;
  float flow_rate;
  bool float_high_triggered;
  bool float_low_triggered;
};

// Global State
MotorState motorState = STATE_IDLE;
unsigned long motorStartTime = 0;
char lastTripReason[64] = "NONE";
char lastCommandId[64] = "";
bool emergencyStopLatched = false;

// Simulated physical values when BENCH_TEST_MODE is true
float simWaterLevel = 75.0f;
float simTurbidity = 8.5f;

// Timers
unsigned long lastTelemetryMillis = 0;
unsigned long lastHeartbeatMillis = 0;

// Networking Clients
WiFiClient espClient;
PubSubClient mqttClient(espClient);

// ======================================================================================
// 4. ACTUATOR & SAFETY LOGIC
// ======================================================================================

void setRelayAndLed(bool active) {
  digitalWrite(PIN_RELAY_MOTOR_START, active ? HIGH : LOW);
  digitalWrite(PIN_ONBOARD_LED, active ? HIGH : LOW);
}

void tripSafety(const char* reason) {
  setRelayAndLed(false);
  motorState = STATE_FAULT_LOCKED;
  strncpy(lastTripReason, reason, sizeof(lastTripReason) - 1);
  Serial.printf("\n[SAFETY TRIP] Motor HALTED: %s\n", reason);

  // Publish immediate fault event
  #if ARDUINOJSON_VERSION_MAJOR >= 7
    JsonDocument doc;
  #else
    StaticJsonDocument<256> doc;
  #endif
  doc["device_uid"] = DEVICE_UID;
  doc["motor_code"] = "PUMP_01";
  doc["fault_type"] = "FAULT";
  doc["description"] = reason;
  doc["timestamp"] = millis() / 1000;

  char buf[256];
  serializeJson(doc, buf);
  mqttClient.publish(TOPIC_FAULT, buf);
}

bool requestStartMotor(const char* command_id) {
  if (motorState == STATE_FAULT_LOCKED) {
    Serial.println("[SAFETY] START REJECTED: Controller is in FAULT_LOCKED state! Reset required.");
    return false;
  }

  if (emergencyStopLatched) {
    Serial.println("[SAFETY] START REJECTED: Emergency stop latch is active.");
    return false;
  }

  // Check hardware float switches (only if not bench testing)
  if (!BENCH_TEST_MODE) {
    if (digitalRead(PIN_EMERGENCY_STOP_BTN) == LOW) {
      tripSafety("HARDWARE_ESTOP_PRESSED");
      return false;
    }
    if (digitalRead(PIN_FLOAT_LOW) == LOW) {
      tripSafety("SOURCE_SUMP_DRY_FLOAT_TRIPPED");
      return false;
    }
    if (digitalRead(PIN_FLOAT_HIGH) == LOW) {
      tripSafety("OVERHEAD_TANK_FULL_FLOAT_TRIPPED");
      return false;
    }
  }

  // Preconditions met -> Engage contactor relay & LED
  setRelayAndLed(true);
  motorState = STATE_RUNNING;
  motorStartTime = millis();
  strncpy(lastCommandId, command_id ? command_id : "", sizeof(lastCommandId) - 1);
  Serial.printf("\n[MOTOR] >>> MOTOR STARTED SUCCESSFULY (Relay & LED ON) <<<\n");
  return true;
}

void requestStopMotor(const char* reason) {
  setRelayAndLed(false);
  if (motorState != STATE_FAULT_LOCKED) {
    motorState = STATE_STOPPED;
  }
  strncpy(lastTripReason, reason ? reason : "MANUAL_STOP", sizeof(lastTripReason) - 1);
  Serial.printf("\n[MOTOR] >>> MOTOR STOPPED (%s) <<<\n", lastTripReason);
}

void triggerEmergencyStop() {
  emergencyStopLatched = true;
  tripSafety("EMERGENCY_STOP_TRIGGERED");
}

void resetFault() {
  emergencyStopLatched = false;
  motorState = STATE_IDLE;
  strcpy(lastTripReason, "NONE");
  setRelayAndLed(false);
  Serial.println("\n[SAFETY] Fault latch cleared. System restored to IDLE standby.");
}

const char* getMotorStateString() {
  switch (motorState) {
    case STATE_IDLE: return "IDLE";
    case STATE_RUNNING: return "ON";
    case STATE_STOPPED: return "OFF";
    case STATE_FAULT_LOCKED: return "FAULT";
    default: return "OFF";
  }
}

// ======================================================================================
// 5. SENSOR READING ENGINE
// ======================================================================================

SensorReadings readSensors() {
  SensorReadings r;

  if (BENCH_TEST_MODE) {
    // Realistic bench-test values
    r.water_level_pct = simWaterLevel;
    r.turbidity_ntu   = simTurbidity;
    r.voltage         = 230.0f;
    r.current_amps    = (motorState == STATE_RUNNING) ? 5.8f : 0.0f;
    r.flow_rate       = (motorState == STATE_RUNNING) ? 42.5f : 0.0f;
    r.float_high_triggered = false;
    r.float_low_triggered  = false;
  } else {
    // Read physical analog pins (ESP32 12-bit ADC: 0 - 4095)
    int rawWater = analogRead(PIN_WATER_LEVEL_ADC);
    r.water_level_pct = map(rawWater, 0, 4095, 0, 100);

    int rawTurb = analogRead(PIN_TURBIDITY_SENSOR);
    r.turbidity_ntu = (rawTurb / 4095.0f) * 30.0f;

    int rawCurr = analogRead(PIN_CURRENT_SENSOR);
    r.current_amps = ((rawCurr - 2048) / 2048.0f) * 20.0f;
    if (r.current_amps < 0) r.current_amps = 0.0f;

    r.voltage   = 230.0f;
    r.flow_rate = (motorState == STATE_RUNNING) ? 45.0f : 0.0f;

    // Digital floats (Active LOW)
    r.float_high_triggered = (digitalRead(PIN_FLOAT_HIGH) == LOW);
    r.float_low_triggered  = (digitalRead(PIN_FLOAT_LOW) == LOW);
  }

  return r;
}

void evaluateContinuousSafety(const SensorReadings& r) {
  if (motorState != STATE_RUNNING) return;

  // 1. Max Continuous Runtime Watchdog
  if (millis() - motorStartTime > MAX_RUNTIME_MS) {
    tripSafety("MAX_CONTINUOUS_RUNTIME_EXCEEDED");
    return;
  }

  // 2. Overcurrent Protection
  if (r.current_amps > OVERCURRENT_THRESHOLD_AMPS) {
    tripSafety("MOTOR_OVERCURRENT_TRIP");
    return;
  }

  // 3. Turbidity / Mud Sediment Protection
  if (r.turbidity_ntu > MAX_TURBIDITY_NTU) {
    tripSafety("HIGH_TURBIDITY_SAFETY_TRIP");
    return;
  }

  // 4. Overhead Tank Full Auto-Cutoff
  if (r.water_level_pct >= MAX_WATER_LEVEL_PCT || r.float_high_triggered) {
    requestStopMotor("TANK_FULL_AUTO_CUTOFF");
    return;
  }

  // 5. Dry Run / Sump Empty Protection
  if (r.water_level_pct <= MIN_WATER_LEVEL_PCT || r.float_low_triggered) {
    tripSafety("DRY_RUN_PROTECTION_TRIP");
    return;
  }
}

// ======================================================================================
// 6. MQTT PUBLISHING & ACK DISPATCHING
// ======================================================================================

void sendAck(const char* command_id, const char* status, const char* message) {
  if (!mqttClient.connected()) return;

  #if ARDUINOJSON_VERSION_MAJOR >= 7
    JsonDocument doc;
  #else
    StaticJsonDocument<256> doc;
  #endif

  doc["command_id"]  = command_id ? command_id : "";
  doc["status"]      = status;
  doc["motor_code"]  = "PUMP_01";
  doc["motor_state"] = getMotorStateString();
  doc["message"]     = message;
  doc["timestamp"]   = millis() / 1000;

  char buffer[256];
  serializeJson(doc, buffer);
  mqttClient.publish(TOPIC_ACK, buffer);
  Serial.printf("[MQTT] Sent ACK -> %s [%s: %s]\n", TOPIC_ACK, status, message);
}

void sendHeartbeat() {
  if (!mqttClient.connected()) return;

  #if ARDUINOJSON_VERSION_MAJOR >= 7
    JsonDocument doc;
  #else
    StaticJsonDocument<256> doc;
  #endif

  doc["device_uid"]       = DEVICE_UID;
  doc["status"]           = "ACTIVE";
  doc["firmware_version"] = FIRMWARE_VERSION;
  doc["ip_address"]       = WiFi.localIP().toString();
  doc["mac_address"]      = WiFi.macAddress();
  doc["uptime_sec"]       = millis() / 1000;
  doc["rssi"]             = WiFi.RSSI();
  doc["motor_state"]      = getMotorStateString();

  char buffer[256];
  serializeJson(doc, buffer);
  mqttClient.publish(TOPIC_HEARTBEAT, buffer);
  Serial.printf("[MQTT] Heartbeat sent (Motor: %s, RSSI: %d dBm)\n", getMotorStateString(), WiFi.RSSI());
}

void sendTelemetry(const SensorReadings& r) {
  if (!mqttClient.connected()) return;

  #if ARDUINOJSON_VERSION_MAJOR >= 7
    JsonDocument doc;
  #else
    StaticJsonDocument<384> doc;
  #endif

  doc["device_uid"]   = DEVICE_UID;
  doc["timestamp"]    = millis() / 1000;
  doc["motor_state"]  = getMotorStateString();

  JsonObject sensors = doc.createNestedObject("sensors");
  sensors["water_level_pct"] = round(r.water_level_pct * 10.0f) / 10.0f;
  sensors["turbidity_ntu"]   = round(r.turbidity_ntu * 10.0f) / 10.0f;
  sensors["current_amps"]    = round(r.current_amps * 10.0f) / 10.0f;
  sensors["flow_rate"]       = round(r.flow_rate * 10.0f) / 10.0f;
  sensors["voltage"]         = round(r.voltage * 10.0f) / 10.0f;

  if (motorState == STATE_FAULT_LOCKED) {
    doc["fault_reason"] = lastTripReason;
  }

  char buffer[384];
  serializeJson(doc, buffer);
  mqttClient.publish(TOPIC_TELEMETRY, buffer);
  Serial.printf("[MQTT] Telemetry sent: Level=%.1f%%, Turb=%.1f NTU, Current=%.1f A\n",
                r.water_level_pct, r.turbidity_ntu, r.current_amps);
}

// ======================================================================================
// 7. INBOUND COMMAND CALLBACK
// ======================================================================================

void onMqttMessageReceived(char* topic, byte* payload, unsigned int length) {
  char messageStr[length + 1];
  memcpy(messageStr, payload, length);
  messageStr[length] = '\0';

  Serial.printf("\n[MQTT] Command Received on [%s]:\n%s\n", topic, messageStr);

  #if ARDUINOJSON_VERSION_MAJOR >= 7
    JsonDocument doc;
  #else
    StaticJsonDocument<384> doc;
  #endif

  DeserializationError err = deserializeJson(doc, messageStr);
  if (err) {
    Serial.printf("[MQTT] JSON parse error: %s\n", err.c_str());
    return;
  }

  const char* command_id = doc["command_id"];
  const char* cmd_type   = doc["command_type"];
  if (!cmd_type) {
    cmd_type = doc["action"];
  }

  if (!cmd_type) {
    Serial.println("[MQTT] Command ignored: Missing command_type or action.");
    return;
  }

  Serial.printf("[COMMAND] Action requested: %s (ID: %s)\n", cmd_type, command_id ? command_id : "N/A");

  if (strcasecmp(cmd_type, "START") == 0) {
    bool ok = requestStartMotor(command_id);
    if (ok) {
      sendAck(command_id, "EXECUTED", "Motor contactor engaged successfully");
    } else {
      sendAck(command_id, "REJECTED", lastTripReason);
    }
  } 
  else if (strcasecmp(cmd_type, "STOP") == 0) {
    requestStopMotor("REMOTE_DASHBOARD_STOP");
    sendAck(command_id, "EXECUTED", "Motor stopped normally");
  } 
  else if (strcasecmp(cmd_type, "EMERGENCY_STOP") == 0 || strcasecmp(cmd_type, "ESTOP") == 0) {
    triggerEmergencyStop();
    sendAck(command_id, "EXECUTED", "Emergency stop tripped and latched");
  } 
  else if (strcasecmp(cmd_type, "RESET") == 0 || strcasecmp(cmd_type, "RESET_FAULT") == 0) {
    resetFault();
    sendAck(command_id, "EXECUTED", "Fault cleared. Ready for operation");
  } 
  else {
    Serial.printf("[MQTT] Unrecognized command type: %s\n", cmd_type);
    sendAck(command_id, "FAILED", "Unsupported command");
  }
}

// ======================================================================================
// 8. WI-FI & MQTT CONNECTION MANAGERS
// ======================================================================================

void connectWifi() {
  if (WiFi.status() == WL_CONNECTED) return;

  Serial.printf("\n[WIFI] Connecting to SSID: '%s'", WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 25) {
    delay(500);
    Serial.print(".");
    digitalWrite(PIN_ONBOARD_LED, !digitalRead(PIN_ONBOARD_LED)); // Blink while connecting
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    digitalWrite(PIN_ONBOARD_LED, LOW);
    Serial.printf("\n[WIFI] Connected! Local IP: %s (Signal: %d dBm)\n",
                  WiFi.localIP().toString().c_str(), WiFi.RSSI());
  } else {
    digitalWrite(PIN_ONBOARD_LED, LOW);
    Serial.println("\n[WIFI] Connection failed. Will retry in loop.");
  }
}

void connectMqtt() {
  if (WiFi.status() != WL_CONNECTED) return;
  if (mqttClient.connected()) return;

  Serial.printf("[MQTT] Connecting to remote broker '%s:%d'...", MQTT_BROKER, MQTT_PORT);

  // Generate unique client ID to prevent collisions on public broker
  String clientId = "HydraESP32-" + WiFi.macAddress();
  clientId.replace(":", "");

  bool connected = false;
  if (strlen(MQTT_USER) > 0) {
    connected = mqttClient.connect(clientId.c_str(), MQTT_USER, MQTT_PASS);
  } else {
    connected = mqttClient.connect(clientId.c_str());
  }

  if (connected) {
    Serial.println(" CONNECTED!");
    // Subscribe to commands topic
    mqttClient.subscribe(TOPIC_COMMANDS, 1);
    Serial.printf("[MQTT] Subscribed to commands topic: %s\n", TOPIC_COMMANDS);

    // Send instant online heartbeat
    sendHeartbeat();
  } else {
    Serial.printf(" FAILED (rc=%d). Will retry in next loop.\n", mqttClient.state());
  }
}

// ======================================================================================
// 9. ARDUINO SETUP & MAIN LOOP
// ======================================================================================

void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println("\n========================================================");
  Serial.println("   HydraControl ESP32 Production Controller Firmware     ");
  Serial.printf ("   Device UID: %s | Ver: %s \n", DEVICE_UID, FIRMWARE_VERSION);
  Serial.printf ("   Mode: %s\n", BENCH_TEST_MODE ? "BENCH TEST (Simulated Sensors)" : "LIVE HARDWARE");
  Serial.println("========================================================");

  // Initialize hardware pins
  pinMode(PIN_ONBOARD_LED, OUTPUT);
  pinMode(PIN_RELAY_MOTOR_START, OUTPUT);
  setRelayAndLed(false);

  pinMode(PIN_EMERGENCY_STOP_BTN, INPUT_PULLUP);
  pinMode(PIN_FLOAT_HIGH, INPUT_PULLUP);
  pinMode(PIN_FLOAT_LOW, INPUT_PULLUP);

  // Initialize MQTT
  mqttClient.setServer(MQTT_BROKER, MQTT_PORT);
  mqttClient.setCallback(onMqttMessageReceived);
  mqttClient.setBufferSize(512); // Ensure buffer fits JSON payloads

  // Connect Wi-Fi
  connectWifi();
}

void loop() {
  // 1. Maintain Wi-Fi and MQTT connectivity
  if (WiFi.status() != WL_CONNECTED) {
    connectWifi();
  } else {
    if (!mqttClient.connected()) {
      connectMqtt();
    }
  }

  mqttClient.loop();

  // 2. Read sensors
  SensorReadings readings = readSensors();

  // 3. Evaluate continuous safety rules
  evaluateContinuousSafety(readings);

  // 4. Periodic Heartbeat (every 10 seconds)
  if (millis() - lastHeartbeatMillis >= 10000) {
    lastHeartbeatMillis = millis();
    sendHeartbeat();
  }

  // 5. Periodic Sensor Telemetry (every 2 seconds)
  if (millis() - lastTelemetryMillis >= 2000) {
    lastTelemetryMillis = millis();
    sendTelemetry(readings);
  }

  delay(10);
}
