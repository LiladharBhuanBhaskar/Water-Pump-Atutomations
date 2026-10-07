#ifndef HYDRA_SAFETY_ENGINE_H
#define HYDRA_SAFETY_ENGINE_H

#include <Arduino.h>
#include "config.h"

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
    bool float_high_triggered;
    bool float_low_triggered;
};

class SafetyEngine {
public:
    SafetyEngine();
    void init();
    bool requestStart(const char* command_id);
    void requestStop(const char* reason = "MANUAL_STOP");
    void triggerEmergencyStop();
    void tick(const SensorReadings& readings);
    
    MotorState getState() const;
    const char* getStateString() const;
    const char* getLastTripReason() const;
    bool isFaulted() const;
    void resetFault();

private:
    MotorState state;
    unsigned long motorStartTime;
    char lastTripReason[64];
    char lastCommandId[64];

    void setRelay(bool on);
    void trip(const char* reason);
};

extern SafetyEngine safetyEngine;

#endif // HYDRA_SAFETY_ENGINE_H
