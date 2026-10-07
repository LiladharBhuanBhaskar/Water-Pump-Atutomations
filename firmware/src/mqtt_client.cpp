#include "mqtt_client.h"
#include <ArduinoJson.h>

HydraMqttClient hydraMqtt;

HydraMqttClient::HydraMqttClient()
    : mqttClient(wifiClient), lastHeartbeatTime(0), lastTelemetryTime(0) {}

void HydraMqttClient::init() {
    mqttClient.setServer(MQTT_BROKER, MQTT_PORT);
    mqttClient.setCallback(HydraMqttClient::messageCallback);
}

void HydraMqttClient::reconnect() {
    while (!mqttClient.connected()) {
        Serial.print("[MQTT] Attempting connection to broker...");
        if (mqttClient.connect(DEVICE_UID, MQTT_USER, MQTT_PASS)) {
            Serial.println(" connected.");
            mqttClient.subscribe(TOPIC_COMMANDS);
            Serial.printf("[MQTT] Subscribed to %s\n", TOPIC_COMMANDS);
        } else {
            Serial.printf(" failed, rc=%d. Retrying in 5 seconds...\n", mqttClient.state());
            delay(5000);
        }
    }
}

void HydraMqttClient::loop() {
    if (WiFi.status() != WL_CONNECTED) {
        return;
    }
    if (!mqttClient.connected()) {
        reconnect();
    }
    mqttClient.loop();
}

void HydraMqttClient::sendTelemetry(const SensorReadings& readings) {
    if (!mqttClient.connected()) return;

    StaticJsonDocument<384> doc;
    doc["device_uid"] = DEVICE_UID;
    doc["timestamp"] = millis() / 1000;
    doc["motor_state"] = safetyEngine.getStateString();
    
    JsonObject sensors = doc.createNestedObject("sensors");
    sensors["water_level_pct"] = readings.water_level_pct;
    sensors["turbidity_ntu"] = readings.turbidity_ntu;
    sensors["current_amps"] = readings.current_amps;
    sensors["float_high"] = readings.float_high_triggered;
    sensors["float_low"] = readings.float_low_triggered;

    if (safetyEngine.isFaulted()) {
        doc["fault_reason"] = safetyEngine.getLastTripReason();
    }

    char buffer[512];
    serializeJson(doc, buffer);
    mqttClient.publish(TOPIC_TELEMETRY, buffer);
}

void HydraMqttClient::sendHeartbeat() {
    if (!mqttClient.connected()) return;

    StaticJsonDocument<256> doc;
    doc["device_uid"] = DEVICE_UID;
    doc["firmware_version"] = FIRMWARE_VERSION;
    doc["uptime_sec"] = millis() / 1000;
    doc["rssi"] = WiFi.RSSI();
    doc["motor_state"] = safetyEngine.getStateString();
    doc["status"] = "ONLINE";

    char buffer[256];
    serializeJson(doc, buffer);
    mqttClient.publish(TOPIC_HEARTBEAT, buffer);
}

void HydraMqttClient::sendAck(const char* command_id, const char* status, const char* message) {
    if (!mqttClient.connected()) return;

    StaticJsonDocument<256> doc;
    doc["device_uid"] = DEVICE_UID;
    doc["command_id"] = command_id;
    doc["status"] = status;
    doc["motor_state"] = safetyEngine.getStateString();
    doc["message"] = message;
    doc["timestamp"] = millis() / 1000;

    char buffer[256];
    serializeJson(doc, buffer);
    mqttClient.publish(TOPIC_ACK, buffer);
}

void HydraMqttClient::messageCallback(char* topic, byte* payload, unsigned int length) {
    char payloadStr[length + 1];
    memcpy(payloadStr, payload, length);
    payloadStr[length] = '\0';

    Serial.printf("[MQTT] Received command on %s: %s\n", topic, payloadStr);

    StaticJsonDocument<384> doc;
    DeserializationError error = deserializeJson(doc, payloadStr);
    if (error) {
        Serial.printf("[MQTT] JSON parse error: %s\n", error.c_str());
        return;
    }

    const char* command_id = doc["command_id"];
    const char* action = doc["action"];

    if (!action) return;

    if (strcmp(action, "START") == 0) {
        bool started = safetyEngine.requestStart(command_id);
        if (started) {
            hydraMqtt.sendAck(command_id, "EXECUTED", "Motor started successfully");
        } else {
            hydraMqtt.sendAck(command_id, "REJECTED", safetyEngine.getLastTripReason());
        }
    } else if (strcmp(action, "STOP") == 0) {
        safetyEngine.requestStop("MANUAL_REMOTE_STOP");
        hydraMqtt.sendAck(command_id, "EXECUTED", "Motor stopped");
    } else if (strcmp(action, "EMERGENCY_STOP") == 0) {
        safetyEngine.triggerEmergencyStop();
        hydraMqtt.sendAck(command_id, "EXECUTED", "Emergency stop triggered");
    } else if (strcmp(action, "RESET_FAULT") == 0) {
        safetyEngine.resetFault();
        hydraMqtt.sendAck(command_id, "EXECUTED", "Fault cleared");
    }
}
