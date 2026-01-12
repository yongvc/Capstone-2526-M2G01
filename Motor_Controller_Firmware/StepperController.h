#ifndef STEPPERCONTROLLER_H
#define STEPPERCONTROLLER_H

#include <Arduino.h>
#include <TMC2209.h>

enum Axis {
    AXIS_X = 0,
    AXIS_Y = 1,
    AXIS_Z = 2
};

// Motion state for non-blocking movement
struct MotionState {
    bool active;           // Is this axis currently moving?
    bool completed;        // Just finished (for notification)
    long targetSteps;      // Total steps to move
    long currentStep;      // Current step count
    float currentDelay;    // Current delay in microseconds
    float minDelay;        // Minimum delay (max speed)
    long accelSteps;       // Steps for acceleration phase
    bool direction;        // Direction of movement
    unsigned long lastStepTime;  // Timestamp of last step
};

class StepperController {
public:
    StepperController();
    void init();
    void enable();
    void disable();
    
    // Non-blocking motion control
    void startMove(Axis axis, float distanceMM, float maxSpeedMM_s, float accelMM_s2);
    void update();  // Call in main loop - processes all axis motion
    
    // Legacy blocking move (kept for compatibility)
    void moveMM(Axis axis, float distanceMM, float maxSpeedMM_s, float accelMM_s2);
    
    // Status queries
    bool isBusy(Axis axis);
    bool isAnyBusy();
    bool checkCompleted(Axis axis);  // Returns true once, then clears flag
    
    // Position tracking
    float getPositionMM(Axis axis);
    void setPositionMM(Axis axis, float pos);
    void homeAll();  // Reset all positions to 0
    
    // Soft limits
    void setLimits(Axis axis, float minMM, float maxMM);
    void enableLimits(bool enable);
    bool isAtLimit(Axis axis);
    float getLimitMax(Axis axis);  // Get axis max limit
    
    // Emergency stop
    void stopAll();
    void stopAxis(Axis axis);

    static constexpr float STEPS_PER_MM = 40.0;
    static constexpr float MAX_SPEED_MM_S = 500.0;
    static constexpr float MAX_ACCEL_MM_S2 = 6000.0;

private:
    TMC2209 _tmc[3];
    uint8_t _stepPins[3];
    uint8_t _dirPins[3];
    uint8_t _enPin;
    
    // Motion state per axis
    MotionState _motion[3];
    
    // Position tracking (in mm)
    float _positionMM[3];
    
    // Soft limits (in mm)
    float _limitMin[3];
    float _limitMax[3];
    bool _limitsEnabled;
    
    void setDirection(Axis axis, bool dir);
    void step(Axis axis);
    void setupDriver(Axis axis, uint8_t address);
    float calculateDelay(long stepNum, long accelSteps, long totalSteps, float minDelay, float accelMM_s2);
};

#endif
