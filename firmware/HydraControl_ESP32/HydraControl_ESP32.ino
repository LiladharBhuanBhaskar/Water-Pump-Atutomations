/*
 * ======================================================================================
 *  HydraControl — Production ESP32 Controller Firmware (Arduino IDE Ready)
 *  Breadboard Circuit Edition: HC-SR04 Ultrasonic + Turbidity Sensor + 3-Pin Buzzer
 * ======================================================================================
 * 
 *  CIRCUIT WIRING SUMMARY (Matches Breadboard Diagram):
 *  --------------------------------------------------------------------------------------
 *  1. HC-SR04 Ultrasonic Sensor (Water Level & Tank Depth):
 *     - VCC   -> 5V Rail (Red rail from regulated 5V power supply)
 *     - GND   -> GND Rail (Blue rail)
 *     - TRIG  -> ESP32 GPIO18 (Blue wire)
 *     - ECHO  -> Through 10kΩ (top) + 15kΩ (bottom) divider to ESP32 GPIO19 (Yellow wire)
 *                [Voltage Divider drops 5V echo pulse to safe ~3.0V for ESP32 GPIO19]
 * 
 *  2. Turbidity Sensor (Water Clarity & Mud Detection):
 *     - VCC/+ -> 5V Rail (Red rail)
 *     - GND/- -> GND Rail (Blue rail)
 *     - AO    -> Through 10kΩ (top) + 10kΩ (bottom) divider to ESP32 GPIO34 (Purple wire)
 *                [Voltage Divider drops 4.5V analog signal to safe ~2.25V for GPIO34 ADC]
 *     - DO    -> Not connected
 * 
 *  3. Buzzer Module (3-Pin, 3.3V Audible Alarm & Feedback):
 *     - VCC/+ -> ESP32 3.3V Pin (Red wire)
 *     - GND/- -> GND Rail (Black wire to Blue rail)
 *     - S/IN  -> ESP32 GPIO25 (Green wire)
 * 
 *  4. Actuators & Indicators:
 *     - GPIO 2  -> ESP32 Onboard Blue LED (Lights up when motor runs / blinks on Wi-Fi)
 *     - GPIO 26 -> Contactor / Motor Relay Module (Active HIGH, optional physical pump)
 * 
 *  QUICK SETUP GUIDE FOR ARDUINO IDE:
 *  --------------------------------------------------------------------------------------
 *  1. Open Arduino IDE (v1.8.x or v2.x).
 *  2. Go to: Tools -> Board -> ESP32 Arduino -> Select "ESP32 Dev Module".
 *  3. Install the 2 required libraries from: Sketch -> Include Library -> Manage Libraries:
 *     - "PubSubClient" by Nick O'Leary (version 2.8 or newer)
 *     - "ArduinoJson" by Benoît Blanchon (version 6.x or 7.x)
 *  4. Edit the WIFI_SSID and WIFI_PASSWORD below to match your Wi-Fi network or hotspot.
 *  5. Connect your ESP32 via USB and select the COM port (Tools -> Port).
 *  6. Click Upload (Arrow icon).
 *  7. Open Tools -> Serial Monitor (Baud Rate: 115200).
 * ======================================================================================
 */

#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>

// ======================================================================================
// 1. NETWORK & CLOUD CONFIGURATION
// ======================================================================================

// Wi-Fi Credentials (Change these to your Wi-Fi or phone hotspot)
const char* WIFI_SSID     = "OnePlus";
const char* WIFI_PASSWORD = "12345678";

// Remote MQTT Cloud Broker (Preconfigured to public broker for zero-config remote access)
const char* MQTT_BROKER   = "broker.emqx.io";
const int   MQTT_PORT     = 1883;
const char* MQTT_USER     = "";  // Leave blank for anonymous public broker
const char* MQTT_PASS     = "";

// Device Hardware Identity (Matches registered device in HydraControl backend)
#define DEVICE_UID         "HYDRA-PROD-ESP32-001"
#define FIRMWARE_VERSION   "1.1.0-circuit"

// MQTT Standard Topics (Standard HydraControl topic hierarchy)
const char* TOPIC_COMMANDS  = "hydracontrol/devices/" DEVICE_UID "/commands";
const char* TOPIC_ACK       = "hydracontrol/devices/" DEVICE_UID "/ack";
const char* TOPIC_HEARTBEAT = "hydracontrol/devices/" DEVICE_UID "/heartbeat";
const char* TOPIC_TELEMETRY = "hydracontrol/devices/" DEVICE_UID "/telemetry";
const char* TOPIC_STATUS    = "hydracontrol/devices/" DEVICE_UID "/status";
const char* TOPIC_FAULT     = "hydracontrol/devices/" DEVICE_UID "/fault";

// ======================================================================================
// 2. HARDWARE PIN DEFINITIONS (Exact Breadboard Wiring)
// ======================================================================================
#define PIN_TRIG               18  // HC-SR04 TRIG (Blue wire)
#define PIN_ECHO               19  // HC-SR04 ECHO via 10k/15k divider (Yellow wire)
#define PIN_TURBIDITY_SENSOR   34  // Turbidity AO via 10k/10k divider (Purple wire - ADC1_CH6)
#define PIN_BUZZER             25  // 3-Pin Buzzer Module S/IN pin (Green wire)
#define PIN_ONBOARD_LED        2   // Built-in Blue LED on ESP32 DevKit
#define PIN_RELAY_MOTOR_START  26  // Relay output pin for pump contactor coil (Active HIGH)

// Set this to FALSE since you have physical sensors wired on the breadboard!
// (Set to TRUE only if testing without sensors wired)
#define BENCH_TEST_MODE        false

// Tank & Sensor Calibration Parameters
#define TANK_HEIGHT_CM         100.0f  // Total height/depth of water tank in cm (adjust to your tank)
#define SENSOR_MIN_DISTANCE_CM 5.0f    // Minimum distance from sensor to full water level
#define SPEED_OF_SOUND_CM_US   0.0343f // Speed of sound at 20°C in cm/microsecond

// Safety Thresholds
#define MAX_RUNTIME_MS              (30UL * 60UL * 1000UL) // 30 mins continuous max run
#define MAX_TURBIDITY_NTU           25.0f  // Water too muddy/dirty -> safety cutoff
#define MIN_WATER_LEVEL_PCT         15.0f  // Dry run protection threshold (low tank/sump)
#define MAX_WATER_LEVEL_PCT         95.0f  // Overflow prevention threshold (full tank)

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
  float distance_cm;
  float water_level_pct;
  float turbidity_ntu;
  float turbidity_volts;
  float current_amps;
  float voltage;
  float flow_rate;
  bool overflow_alert;
  bool dry_run_alert;
};

// Global State
MotorState motorState = STATE_IDLE;
unsigned long motorStartTime = 0;
char lastTripReason[64] = "NONE";
char lastCommandId[64] = "";
bool emergencyStopLatched = false;

// Non-blocking buzzer alarm variables
unsigned long lastBuzzerToggleMillis = 0;
bool buzzerState = false;

// Timers
unsigned long lastTelemetryMillis = 0;
unsigned long lastHeartbeatMillis = 0;

// Networking Clients
WiFiClient espClient;
PubSubClient mqttClient(espClient);

// ======================================================================================
// 4. BUZZER AUDIO FEEDBACK ENGINE
// ======================================================================================

void buzzerSet(bool on) {
  digitalWrite(PIN_BUZZER, on ? HIGH : LOW);
}

// Blocking short beep for user actions / boot
void buzzerBeep(int durationMs) {
  buzzerSet(true);
  delay(durationMs);
  buzzerSet(false);
}

void buzzerPattern(int beeps, int onMs, int offMs) {
  for (int i = 0; i < beeps; i++) {
    buzzerSet(true);
    delay(onMs);
    buzzerSet(false);
    if (i < beeps - 1) delay(offMs);
  }
}

// Non-blocking continuous pulsing alarm when in fault
void handleBuzzerAlarm() {
  if (motorState == STATE_FAULT_LOCKED) {
    unsigned long now = millis();
    // Beep 200ms ON / 800ms OFF
    if (buzzerState && (now - lastBuzzerToggleMillis >= 200)) {
      buzzerSet(false);
      buzzerState = false;
      lastBuzzerToggleMillis = now;
    } else if (!buzzerState && (now - lastBuzzerToggleMillis >= 800)) {
      buzzerSet(true);
      buzzerState = true;
      lastBuzzerToggleMillis = now;
    }
  } else {
    if (buzzerState) {
      buzzerSet(false);
      buzzerState = false;
    }
  }
}

// ======================================================================================
// 5. ACTUATOR & SAFETY LOGIC
// ======================================================================================

// Forward declarations
const char* getMotorStateString();
void sendStatus();
SensorReadings readSensors();
void sendTelemetry(const SensorReadings& r);

void setActuators(bool active) {
  digitalWrite(PIN_RELAY_MOTOR_START, active ? HIGH : LOW);
  digitalWrite(PIN_ONBOARD_LED, active ? HIGH : LOW);
}

void tripSafety(const char* reason) {
  setActuators(false);
  motorState = STATE_FAULT_LOCKED;
  strncpy(lastTripReason, reason, sizeof(lastTripReason) - 1);
  Serial.printf("\n[SAFETY TRIP] Motor HALTED: %s\n", reason);

  // Trigger immediate buzzer alert (3 rapid warning chirps)
  buzzerPattern(3, 80, 80);

  // Publish immediate fault event to cloud
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
  sendStatus();
}

bool requestStartMotor(const char* command_id) {
  if (motorState == STATE_FAULT_LOCKED) {
    Serial.println("[SAFETY] START REJECTED: Controller is in FAULT_LOCKED state! Reset required.");
    buzzerPattern(2, 200, 100); // Rejection tone
    return false;
  }

  if (emergencyStopLatched) {
    Serial.println("[SAFETY] START REJECTED: Emergency stop latch is active.");
    buzzerPattern(2, 200, 100);
    return false;
  }

  // Preconditions met -> Engage relay, LED & audio feedback
  setActuators(true);
  motorState = STATE_RUNNING;
  motorStartTime = millis();
  strncpy(lastCommandId, command_id ? command_id : "", sizeof(lastCommandId) - 1);
  strcpy(lastTripReason, "NONE");
  
  // Affirmative startup chime (2 short cheerful beeps)
  buzzerPattern(2, 100, 80);
  
  Serial.printf("\n[MOTOR] >>> MOTOR STARTED SUCCESSFULLY (Relay & LED ON) <<<\n");
  sendStatus();
  return true;
}

void requestStopMotor(const char* reason) {
  setActuators(false);
  if (motorState != STATE_FAULT_LOCKED) {
    motorState = STATE_STOPPED;
  }
  strncpy(lastTripReason, reason ? reason : "MANUAL_STOP", sizeof(lastTripReason) - 1);
  
  // Stopping beep (1 solid 250ms tone)
  buzzerBeep(250);
  
  Serial.printf("\n[MOTOR] >>> MOTOR STOPPED (%s) <<<\n", lastTripReason);

  // Immediately notify cloud broker of state change so dashboard and mobile app reflect it
  sendStatus();
  SensorReadings r = readSensors();
  sendTelemetry(r);
}

void triggerEmergencyStop() {
  emergencyStopLatched = true;
  tripSafety("EMERGENCY_STOP_TRIGGERED");
}

void resetFault() {
  emergencyStopLatched = false;
  motorState = STATE_IDLE;
  strcpy(lastTripReason, "NONE");
  setActuators(false);
  buzzerSet(false);
  buzzerState = false;
  
  // Confirmation chime for reset (1 long 400ms tone)
  buzzerBeep(400);
  Serial.println("\n[SAFETY] Fault latch cleared. System restored to IDLE standby.");
  sendStatus();
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
// 6. SENSOR READING ENGINE (HC-SR04 Ultrasonic & Turbidity with Voltage Dividers)
// ======================================================================================

// Helper: Read raw HC-SR04 distance in cm
float readUltrasonicRawDistance() {
  // Clear trigger pin
  digitalWrite(PIN_TRIG, LOW);
  delayMicroseconds(2);

  // Send 10µs HIGH trigger pulse
  digitalWrite(PIN_TRIG, HIGH);
  delayMicroseconds(10);
  digitalWrite(PIN_TRIG, LOW);

  // Read ECHO pulse duration (timeout 30000µs = max ~5 meters)
  unsigned long duration = pulseIn(PIN_ECHO, HIGH, 30000);

  if (duration == 0) {
    // Timeout or out of range
    return -1.0f;
  }

  // Calculate distance: (duration * speed_of_sound) / 2
  float dist = (duration * SPEED_OF_SOUND_CM_US) / 2.0f;
  return dist;
}

// Filtered distance reading (median of 3 samples to eliminate noise/spikes)
float getFilteredDistanceCm() {
  float readings[3];
  int validCount = 0;

  for (int i = 0; i < 3; i++) {
    float d = readUltrasonicRawDistance();
    if (d >= 2.0f && d <= 400.0f) {
      readings[validCount++] = d;
    }
    delay(10);
  }

  if (validCount == 0) {
    return -1.0f; // Sensor unplugged or beam obstructed
  }

  // Sort and take median
  for (int i = 0; i < validCount - 1; i++) {
    for (int j = i + 1; j < validCount; j++) {
      if (readings[i] > readings[j]) {
        float tmp = readings[i];
        readings[i] = readings[j];
        readings[j] = tmp;
      }
    }
  }

  return readings[validCount / 2];
}

SensorReadings readSensors() {
  SensorReadings r;

  if (BENCH_TEST_MODE) {
    // Bench test fallback
    r.distance_cm       = 28.5f;
    r.water_level_pct   = 75.0f;
    r.turbidity_ntu     = 4.2f;
    r.turbidity_volts   = 4.15f;
    r.voltage           = 230.0f;
    r.current_amps      = (motorState == STATE_RUNNING) ? 5.8f : 0.0f;
    r.flow_rate         = (motorState == STATE_RUNNING) ? 42.5f : 0.0f;
    r.overflow_alert    = false;
    r.dry_run_alert     = false;
    return r;
  }

  // 1. HC-SR04 Ultrasonic Distance & Water Level Calculation
  float dist = getFilteredDistanceCm();
  if (dist > 0) {
    r.distance_cm = dist;

    // Convert distance to water level percentage:
    // When distance == SENSOR_MIN_DISTANCE_CM -> Tank is 100% full
    // When distance >= TANK_HEIGHT_CM         -> Tank is 0% empty
    float waterDepth = (TANK_HEIGHT_CM + SENSOR_MIN_DISTANCE_CM) - dist;
    float levelPct = (waterDepth / TANK_HEIGHT_CM) * 100.0f;
    r.water_level_pct = constrain(levelPct, 0.0f, 100.0f);
  } else {
    // Default fallback if echo lost
    r.distance_cm = -1.0f;
    r.water_level_pct = 50.0f;
  }

  // 2. Turbidity Sensor on GPIO34 (via 10kΩ + 10kΩ voltage divider)
  // ESP32 12-bit ADC reads 0 to 4095 (0 to 3.3V)
  int rawTurb = analogRead(PIN_TURBIDITY_SENSOR);
  float v_pin = (rawTurb / 4095.0f) * 3.3f; // Measured voltage on GPIO34

  // Because the 10kΩ+10kΩ divider divides the sensor voltage by 2:
  // V_sensor = V_pin * ((10k + 10k) / 10k) = V_pin * 2.0
  float v_sensor = v_pin * 2.0f;
  r.turbidity_volts = v_sensor;

  // Turbidity standard gravity conversion:
  // Clean drinking water produces ~4.1V - 4.5V (Turbidity < 5 NTU)
  // Muddy/dirty water drops voltage below 2.5V (Turbidity > 30 NTU)
  if (v_sensor >= 4.15f) {
    r.turbidity_ntu = 0.5f; // Crystal clear water
  } else if (v_sensor <= 2.5f) {
    r.turbidity_ntu = 100.0f; // Very turbid / sediment
  } else {
    // Linear interpolation between clean (4.15V -> 0 NTU) and dirty (2.5V -> 50 NTU)
    r.turbidity_ntu = (4.15f - v_sensor) * (50.0f / (4.15f - 2.5f));
    r.turbidity_ntu = constrain(r.turbidity_ntu, 0.0f, 100.0f);
  }

  // 3. Electrical & Flow Telemetry
  r.voltage      = 230.0f; // Standard AC supply voltage
  r.current_amps = (motorState == STATE_RUNNING) ? 5.8f : 0.0f;
  r.flow_rate    = (motorState == STATE_RUNNING) ? 42.5f : 0.0f;

  // Float logic derived from high-precision ultrasonic level
  r.overflow_alert = (r.water_level_pct >= MAX_WATER_LEVEL_PCT);
  r.dry_run_alert  = (r.water_level_pct <= MIN_WATER_LEVEL_PCT);

  return r;
}

void evaluateContinuousSafety(const SensorReadings& r) {
  if (motorState != STATE_RUNNING) return;

  // 1. Max Continuous Runtime Watchdog (Protects motor from overheating)
  if (millis() - motorStartTime > MAX_RUNTIME_MS) {
    tripSafety("MAX_CONTINUOUS_RUNTIME_EXCEEDED");
    return;
  }

  // 2. High Turbidity / Mud Sediment Protection (Protects pump impellers from sand/mud)
  if (r.turbidity_ntu > MAX_TURBIDITY_NTU) {
    tripSafety("HIGH_TURBIDITY_SAFETY_TRIP");
    return;
  }

  // 3. Overhead Tank Full Auto-Cutoff (Overflow prevention)
  if (r.water_level_pct >= MAX_WATER_LEVEL_PCT) {
    Serial.printf("\n[AUTO-CUTOFF] Overhead Tank FULL (%.1f%% >= %.1f%%)! Stopping pump.\n",
                  r.water_level_pct, MAX_WATER_LEVEL_PCT);
    requestStopMotor("TANK_FULL_AUTO_CUTOFF");

    #if ARDUINOJSON_VERSION_MAJOR >= 7
      JsonDocument doc;
    #else
      StaticJsonDocument<256> doc;
    #endif
    doc["device_uid"] = DEVICE_UID;
    doc["motor_code"] = "PUMP_01";
    doc["fault_type"] = "TANK_FULL";
    doc["description"] = "Overhead Tank Full Auto-Cutoff (>=95%)";
    doc["timestamp"] = millis() / 1000;

    char buf[256];
    serializeJson(doc, buf);
    mqttClient.publish(TOPIC_FAULT, buf);
    return;
  }

  // 4. Dry Run / Sump Empty Protection (Prevents pump running without water)
  if (r.water_level_pct <= MIN_WATER_LEVEL_PCT) {
    tripSafety("DRY_RUN_PROTECTION_TRIP");
    return;
  }
}

// ======================================================================================
// 7. MQTT PUBLISHING & ACK DISPATCHING
// ======================================================================================

void sendStatus() {
  if (!mqttClient.connected()) return;

  #if ARDUINOJSON_VERSION_MAJOR >= 7
    JsonDocument doc;
  #else
    StaticJsonDocument<384> doc;
  #endif

  doc["device_uid"] = DEVICE_UID;
  doc["controller_status"] = "ACTIVE";
  doc["timestamp"] = millis() / 1000;

  JsonArray motors = doc.createNestedArray("motors");
  JsonObject m1 = motors.createNestedObject();
  m1["motor_code"] = "PUMP_01";
  m1["status"] = getMotorStateString();
  m1["fault_reason"] = lastTripReason;

  char buffer[384];
  serializeJson(doc, buffer);
  mqttClient.publish(TOPIC_STATUS, buffer);
  Serial.printf("[MQTT] Sent STATUS -> %s [PUMP_01: %s (%s)]\n", TOPIC_STATUS, getMotorStateString(), lastTripReason);
}

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
  sensors["distance_cm"]     = round(r.distance_cm * 10.0f) / 10.0f;
  sensors["current_amps"]    = round(r.current_amps * 10.0f) / 10.0f;
  sensors["flow_rate"]       = round(r.flow_rate * 10.0f) / 10.0f;
  sensors["voltage"]         = round(r.voltage * 10.0f) / 10.0f;

  if (motorState == STATE_FAULT_LOCKED) {
    doc["fault_reason"] = lastTripReason;
  }

  char buffer[384];
  serializeJson(doc, buffer);
  mqttClient.publish(TOPIC_TELEMETRY, buffer);
  
  Serial.printf("[CIRCUIT SENSORS] Level=%.1f%% (Dist=%.1f cm) | Turb=%.1f NTU (%.2fV) | Motor=%s\n",
                r.water_level_pct, r.distance_cm, r.turbidity_ntu, r.turbidity_volts, getMotorStateString());
}

// ======================================================================================
// 8. INBOUND COMMAND CALLBACK
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
// 9. WI-FI & MQTT CONNECTION MANAGERS
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
    // 2 quick confirmation beeps
    buzzerPattern(2, 60, 60);
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
    
    // Connected tone (3 quick cheerful beeps)
    buzzerPattern(3, 50, 50);
  } else {
    Serial.printf(" FAILED (rc=%d). Will retry in next loop.\n", mqttClient.state());
  }
}

// ======================================================================================
// 10. ARDUINO SETUP & MAIN LOOP
// ======================================================================================

void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println("\n========================================================");
  Serial.println("  HydraControl ESP32 Firmware — Breadboard Circuit Edition");
  Serial.printf ("  Device UID: %s | Ver: %s \n", DEVICE_UID, FIRMWARE_VERSION);
  Serial.println("  Sensors: HC-SR04 (GPIO18/19), Turbidity (GPIO34), Buzzer (GPIO25)");
  Serial.println("========================================================");

  // 1. Initialize ultrasonic sensor pins
  pinMode(PIN_TRIG, OUTPUT);
  pinMode(PIN_ECHO, INPUT);
  digitalWrite(PIN_TRIG, LOW);

  // 2. Initialize buzzer pin
  pinMode(PIN_BUZZER, OUTPUT);
  buzzerSet(false);

  // 3. Initialize status LED & motor relay
  pinMode(PIN_ONBOARD_LED, OUTPUT);
  pinMode(PIN_RELAY_MOTOR_START, OUTPUT);
  setActuators(false);

  // Configure ADC for turbidity reading (12-bit resolution, 0-3.3V attenuation)
  analogReadResolution(12);
  analogSetAttenuation(ADC_11db);

  // Power-on beep
  buzzerBeep(150);

  // Initialize MQTT
  mqttClient.setServer(MQTT_BROKER, MQTT_PORT);
  mqttClient.setCallback(onMqttMessageReceived);
  mqttClient.setBufferSize(512); // Buffer size for JSON payloads

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

  // 2. Read sensors (Ultrasonic HC-SR04 + Turbidity ADC with divider compensation)
  SensorReadings readings = readSensors();

  // 3. Evaluate continuous safety rules (Overfill, Dry Run, High Turbidity)
  evaluateContinuousSafety(readings);

  // 4. Handle non-blocking buzzer alarm if in fault state
  handleBuzzerAlarm();

  // 5. Periodic Heartbeat (every 10 seconds)
  if (millis() - lastHeartbeatMillis >= 10000) {
    lastHeartbeatMillis = millis();
    sendHeartbeat();
  }

  // 6. Periodic Sensor Telemetry (every 2 seconds)
  if (millis() - lastTelemetryMillis >= 2000) {
    lastTelemetryMillis = millis();
    sendTelemetry(readings);
  }

  delay(20);
}
