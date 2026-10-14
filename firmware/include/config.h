#ifndef HYDRA_CONFIG_H
#define HYDRA_CONFIG_H

#include <Arduino.h>

// Device Identification
#define DEVICE_UID "HYDRA-PROD-ESP32-001"
#define FIRMWARE_VERSION "1.1.0-circuit"

// Wi-Fi Configuration
#define WIFI_SSID "Your_WiFi_Name"
#define WIFI_PASSWORD "Your_WiFi_Password"

// Remote MQTT Configuration (Cloud / Public Broker for Remote Internet Access)
#define MQTT_BROKER "broker.emqx.io"
#define MQTT_PORT 1883 // 8883 for TLS
#define MQTT_USER ""
#define MQTT_PASS ""

// MQTT Standard Topics (Matches Backend MQTTRouter Hierarchy)
#define TOPIC_TELEMETRY "hydracontrol/devices/" DEVICE_UID "/telemetry"
#define TOPIC_HEARTBEAT "hydracontrol/devices/" DEVICE_UID "/heartbeat"
#define TOPIC_COMMANDS  "hydracontrol/devices/" DEVICE_UID "/commands"
#define TOPIC_ACK       "hydracontrol/devices/" DEVICE_UID "/ack"
#define TOPIC_STATUS    "hydracontrol/devices/" DEVICE_UID "/status"
#define TOPIC_FAULT     "hydracontrol/devices/" DEVICE_UID "/fault"

// Hardware Pinout Mapping (Matches Exact Breadboard Circuit Diagram)
#define PIN_TRIG               18  // HC-SR04 Ultrasonic Trigger (Blue wire)
#define PIN_ECHO               19  // HC-SR04 Ultrasonic Echo via 10k/15k divider (Yellow wire)
#define PIN_TURBIDITY_SENSOR   34  // Turbidity Sensor AO via 10k/10k divider (Purple wire - ADC1_CH6)
#define PIN_BUZZER             25  // 3-Pin Buzzer Module Control (Green wire to S pin)
#define PIN_ONBOARD_LED        2   // Blue Status LED on ESP32 DevKit
#define PIN_RELAY_MOTOR_START  26  // Drives Contactor Coil Relay (Active HIGH)

// Tank & Sensor Calibration Parameters
#define TANK_HEIGHT_CM         100.0f  // Total height of tank in cm
#define SENSOR_MIN_DISTANCE_CM 5.0f    // Minimum blind zone distance in cm

// Safety Limits
#define MAX_RUNTIME_MS        (30 * 60 * 1000) // 30 Minutes Max Safe Continuous Run
#define OVERCURRENT_THRESHOLD_AMPS 15.0f
#define MAX_TURBIDITY_NTU     25.0f
#define MIN_WATER_LEVEL_PCT   15.0f
#define MAX_WATER_LEVEL_PCT   95.0f

#endif // HYDRA_CONFIG_H
