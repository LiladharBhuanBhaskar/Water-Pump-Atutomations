#ifndef HYDRA_CONFIG_H
#define HYDRA_CONFIG_H

#include <Arduino.h>

// Device Identification
#define DEVICE_UID "HYDRA-PROD-ESP32-001"
#define FIRMWARE_VERSION "1.0.0-prod"

// Wi-Fi Configuration
#define WIFI_SSID "HydraNet_Secure"
#define WIFI_PASSWORD "HydraSecretKey"

// MQTT Configuration
#define MQTT_BROKER "mqtt.hydracontrol.local"
#define MQTT_PORT 1883 // 8883 for TLS
#define MQTT_USER "esp32_device_user"
#define MQTT_PASS "device_auth_token"

// MQTT Topics
#define TOPIC_TELEMETRY "hydracontrol/telemetry"
#define TOPIC_HEARTBEAT "hydracontrol/heartbeat"
#define TOPIC_COMMANDS  "hydracontrol/commands/" DEVICE_UID
#define TOPIC_ACK       "hydracontrol/ack"

// Hardware Pinout Mapping
#define PIN_RELAY_MOTOR_START  25  // Drives Contactor Coil Relay
#define PIN_EMERGENCY_STOP_BTN 34  // Active-low Emergency STOP interrupt
#define PIN_FLOAT_HIGH         35  // Upper Tank High Float Switch
#define PIN_FLOAT_LOW          32  // Lower Tank Dry Run Float Switch
#define PIN_CURRENT_SENSOR     36  // Analog Current Sensor (ACS712 / CT)
#define PIN_TURBIDITY_SENSOR   39  // Analog Turbidity Sensor
#define PIN_WATER_LEVEL_ADC    33  // Hydrostatic / Ultrasonic Level Sensor

// Safety Limits
#define MAX_RUNTIME_MS        (30 * 60 * 1000) // 30 Minutes Max Safe Continuous Run
#define OVERCURRENT_THRESHOLD_AMPS 15.0f
#define MAX_TURBIDITY_NTU     25.0f
#define MIN_WATER_LEVEL_PCT   15.0f
#define MAX_WATER_LEVEL_PCT   95.0f

#endif // HYDRA_CONFIG_H
