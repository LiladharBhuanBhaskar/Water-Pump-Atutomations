#ifndef HYDRA_MQTT_CLIENT_H
#define HYDRA_MQTT_CLIENT_H

#include <Arduino.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include "config.h"
#include "safety_engine.h"

class HydraMqttClient {
public:
    HydraMqttClient();
    void init();
    void loop();
    void sendTelemetry(const SensorReadings& readings);
    void sendHeartbeat();
    void sendAck(const char* command_id, const char* status, const char* message = "");

private:
    WiFiClient wifiClient;
    PubSubClient mqttClient;
    unsigned long lastHeartbeatTime;
    unsigned long lastTelemetryTime;

    void reconnect();
    static void messageCallback(char* topic, byte* payload, unsigned int length);
};

extern HydraMqttClient hydraMqtt;

#endif // HYDRA_MQTT_CLIENT_H
