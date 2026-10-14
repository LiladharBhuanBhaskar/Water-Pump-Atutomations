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
    float distance_cm;
    float water_level_pct;
    float turbidity_ntu;
    float turbidity_volts;
    float current_amps;
    bool overflow_alert;
    bool dry_run_alert;
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
