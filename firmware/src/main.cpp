#include <Arduino.h>
#include <WiFi.h>
#include "config.h"
#include "safety_engine.h"
#include "mqtt_client.h"

unsigned long lastTelemetryMillis = 0;
unsigned long lastHeartbeatMillis = 0;

void setupWifi() {
    delay(10);
    Serial.printf("[WIFI] Connecting to %s", WIFI_SSID);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    
    int attempts = 0;
    while (WiFi.status() != WL_CONNECTED && attempts < 20) {
        delay(500);
        Serial.print(".");
        digitalWrite(PIN_ONBOARD_LED, !digitalRead(PIN_ONBOARD_LED));
        attempts++;
    }
    if (WiFi.status() == WL_CONNECTED) {
        digitalWrite(PIN_ONBOARD_LED, LOW);
        Serial.printf("\n[WIFI] Connected! IP: %s\n", WiFi.localIP().toString().c_str());
    } else {
        digitalWrite(PIN_ONBOARD_LED, LOW);
        Serial.println("\n[WIFI] Connection failed. Operating in offline safety mode.");
    }
}

SensorReadings readSensors() {
    SensorReadings readings;
    
    // 1. HC-SR04 Ultrasonic Distance & Water Level Calculation
    digitalWrite(PIN_TRIG, LOW);
    delayMicroseconds(2);
    digitalWrite(PIN_TRIG, HIGH);
    delayMicroseconds(10);
    digitalWrite(PIN_TRIG, LOW);

    unsigned long duration = pulseIn(PIN_ECHO, HIGH, 30000);
    if (duration > 0) {
        float dist_cm = (duration * 0.0343f) / 2.0f;
        readings.distance_cm = dist_cm;
        float waterDepth = (TANK_HEIGHT_CM + SENSOR_MIN_DISTANCE_CM) - dist_cm;
        readings.water_level_pct = constrain((waterDepth / TANK_HEIGHT_CM) * 100.0f, 0.0f, 100.0f);
    } else {
        readings.distance_cm = -1.0f;
        readings.water_level_pct = 50.0f;
    }

    // 2. Turbidity Sensor on GPIO34 (via 10k/10k divider)
    int rawTurbidity = analogRead(PIN_TURBIDITY_SENSOR);
    float v_pin = (rawTurbidity / 4095.0f) * 3.3f;
    float v_sensor = v_pin * 2.0f; // Reconstructed sensor voltage
    readings.turbidity_volts = v_sensor;

    if (v_sensor >= 4.15f) {
        readings.turbidity_ntu = 0.5f;
    } else if (v_sensor <= 2.5f) {
        readings.turbidity_ntu = 100.0f;
    } else {
        readings.turbidity_ntu = (4.15f - v_sensor) * (50.0f / (4.15f - 2.5f));
        readings.turbidity_ntu = constrain(readings.turbidity_ntu, 0.0f, 100.0f);
    }

    // 3. Electrical & Alert Flags
    readings.current_amps = (safetyEngine.getState() == STATE_RUNNING) ? 5.8f : 0.0f;
    readings.overflow_alert = (readings.water_level_pct >= MAX_WATER_LEVEL_PCT);
    readings.dry_run_alert  = (readings.water_level_pct <= MIN_WATER_LEVEL_PCT);

    return readings;
}

void setup() {
    Serial.begin(115200);
    delay(1000);
    Serial.println("\n==============================================");
    Serial.println("  HydraControl ESP32 Firmware Starting...     ");
    Serial.println("  Breadboard Circuit: HC-SR04 + Turbidity + Buzzer");
    Serial.println("==============================================");

    // 1. Initialize authoritative local safety engine FIRST
    safetyEngine.init();

    // 2. Setup Wi-Fi & MQTT
    setupWifi();
    hydraMqtt.init();
}

void loop() {
    // 1. Read hardware sensors
    SensorReadings readings = readSensors();

    // 2. Continuous local safety evaluation (AUTHORITATIVE)
    safetyEngine.tick(readings);

    // 3. Maintain MQTT connection & loop
    hydraMqtt.loop();

    // 4. Periodic Heartbeat (every 10s)
    if (millis() - lastHeartbeatMillis > 10000) {
        lastHeartbeatMillis = millis();
        hydraMqtt.sendHeartbeat();
    }

    // 5. Periodic Telemetry (every 1s)
    if (millis() - lastTelemetryMillis > 1000) {
        lastTelemetryMillis = millis();
        hydraMqtt.sendTelemetry(readings);
        Serial.printf("[TELEMETRY] Dist: %.1f cm | Water: %.1f%% | Turbidity: %.1f NTU (%.2fV)\n",
                      readings.distance_cm, readings.water_level_pct, readings.turbidity_ntu, readings.turbidity_volts);
    }

    delay(10);
}
