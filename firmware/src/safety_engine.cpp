#include "safety_engine.h"
#include <string.h>

SafetyEngine safetyEngine;

SafetyEngine::SafetyEngine()
    : state(STATE_IDLE), motorStartTime(0) {
    memset(lastTripReason, 0, sizeof(lastTripReason));
    memset(lastCommandId, 0, sizeof(lastCommandId));
}

void SafetyEngine::init() {
    pinMode(PIN_RELAY_MOTOR_START, OUTPUT);
    pinMode(PIN_EMERGENCY_STOP_BTN, INPUT_PULLUP);
    pinMode(PIN_FLOAT_HIGH, INPUT_PULLUP);
    pinMode(PIN_FLOAT_LOW, INPUT_PULLUP);

    // Default safe power-on state: relay strictly OFF
    setRelay(false);
    state = STATE_IDLE;
}

void SafetyEngine::setRelay(bool on) {
    digitalWrite(PIN_RELAY_MOTOR_START, on ? HIGH : LOW);
}

void SafetyEngine::trip(const char* reason) {
    setRelay(false);
    state = STATE_FAULT_LOCKED;
    strncpy(lastTripReason, reason, sizeof(lastTripReason) - 1);
    Serial.printf("[SAFETY TRIP] Motor stopped: %s\n", reason);
}

bool SafetyEngine::requestStart(const char* command_id) {
    // 1. Check if controller is in fault lock
    if (state == STATE_FAULT_LOCKED) {
        Serial.println("[SAFETY] Start rejected: Motor in FAULT_LOCKED state");
        return false;
    }

    // 2. Reject duplicate / stale command replay
    if (command_id && strlen(command_id) > 0 && strcmp(lastCommandId, command_id) == 0) {
        Serial.println("[SAFETY] Start rejected: Duplicate command replay detected");
        return false;
    }

    if (command_id) {
        strncpy(lastCommandId, command_id, sizeof(lastCommandId) - 1);
    }

    // 3. Hardware check: Is emergency stop button engaged?
    if (digitalRead(PIN_EMERGENCY_STOP_BTN) == LOW) {
        trip("EMERGENCY_STOP_ENGAGED");
        return false;
    }

    // 4. Check dry-run lower float switch
    if (digitalRead(PIN_FLOAT_LOW) == LOW) {
        trip("SOURCE_DRY_FLOAT_TRIP");
        return false;
    }

    // 5. Check overhead tank full float switch
    if (digitalRead(PIN_FLOAT_HIGH) == LOW) {
        trip("TANK_FULL_FLOAT_TRIP");
        return false;
    }

    // All safety preconditions verified -> Engage relay
    setRelay(true);
    state = STATE_RUNNING;
    motorStartTime = millis();
    Serial.println("[MOTOR] Started successfully");
    return true;
}

void SafetyEngine::requestStop(const char* reason) {
    setRelay(false);
    if (state != STATE_FAULT_LOCKED) {
        state = STATE_STOPPED;
    }
    strncpy(lastTripReason, reason ? reason : "MANUAL_STOP", sizeof(lastTripReason) - 1);
    Serial.printf("[MOTOR] Stopped: %s\n", lastTripReason);
}

void SafetyEngine::triggerEmergencyStop() {
    trip("HARDWARE_EMERGENCY_STOP");
}

void SafetyEngine::tick(const SensorReadings& readings) {
    // Check hardware E-Stop continuously
    if (digitalRead(PIN_EMERGENCY_STOP_BTN) == LOW) {
        if (state == STATE_RUNNING) {
            triggerEmergencyStop();
        }
        return;
    }

    if (state != STATE_RUNNING) {
        return;
    }

    // 1. Max continuous runtime watchdog
    if (millis() - motorStartTime > MAX_RUNTIME_MS) {
        trip("MAX_RUNTIME_EXCEEDED");
        return;
    }

    // 2. Overcurrent protection
    if (readings.current_amps > OVERCURRENT_THRESHOLD_AMPS) {
        trip("OVERCURRENT_DETECTED");
        return;
    }

    // 3. High Turbidity protection (sediment/mud defense)
    if (readings.turbidity_ntu > MAX_TURBIDITY_NTU) {
        trip("HIGH_TURBIDITY_TRIP");
        return;
    }

    // 4. Water level limits
    if (readings.water_level_pct >= MAX_WATER_LEVEL_PCT || readings.float_high_triggered) {
        trip("TANK_FULL_OVERFLOW_PREVENTION");
        return;
    }

    if (readings.water_level_pct <= MIN_WATER_LEVEL_PCT || readings.float_low_triggered) {
        trip("DRY_RUN_PROTECTION");
        return;
    }
}

MotorState SafetyEngine::getState() const {
    return state;
}

const char* SafetyEngine::getStateString() const {
    switch (state) {
        case STATE_IDLE: return "IDLE";
        case STATE_RUNNING: return "RUNNING";
        case STATE_STOPPED: return "STOPPED";
        case STATE_FAULT_LOCKED: return "FAULT_LOCKED";
        default: return "UNKNOWN";
    }
}

const char* SafetyEngine::getLastTripReason() const {
    return lastTripReason;
}

bool SafetyEngine::isFaulted() const {
    return state == STATE_FAULT_LOCKED;
}

void SafetyEngine::resetFault() {
    if (state == STATE_FAULT_LOCKED) {
        state = STATE_IDLE;
        memset(lastTripReason, 0, sizeof(lastTripReason));
        Serial.println("[SAFETY] Fault state reset to IDLE");
    }
}
