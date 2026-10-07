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
        attempts++;
    }
    if (WiFi.status() == WL_CONNECTED) {
        Serial.printf("\n[WIFI] Connected! IP: %s\n", WiFi.localIP().toString().c_str());
    } else {
        Serial.println("\n[WIFI] Connection failed. Operating in offline safety mode.");
    }
}

SensorReadings readSensors() {
    SensorReadings readings;
    
    // Analog conversions
    int rawWater = analogRead(PIN_WATER_LEVEL_ADC);
    readings.water_level_pct = map(rawWater, 0, 4095, 0, 100);

    int rawTurbidity = analogRead(PIN_TURBIDITY_SENSOR);
    readings.turbidity_ntu = (rawTurbidity / 4095.0f) * 30.0f;

    int rawCurrent = analogRead(PIN_CURRENT_SENSOR);
    readings.current_amps = ((rawCurrent - 2048) / 2048.0f) * 20.0f;
    if (readings.current_amps < 0) readings.current_amps = 0.0f;

    // Digital floats (active-low)
    readings.float_high_triggered = (digitalRead(PIN_FLOAT_HIGH) == LOW);
    readings.float_low_triggered = (digitalRead(PIN_FLOAT_LOW) == LOW);

    return readings;
}

void setup() {
    Serial.begin(115200);
    Serial.println("\n==============================================");
    Serial.println("  HydraControl ESP32 Firmware Starting...     ");
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
    }

    delay(10);
}
