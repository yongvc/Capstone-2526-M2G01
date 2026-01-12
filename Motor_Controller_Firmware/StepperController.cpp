#include "StepperController.h"
#include "PinMap.h"
#include "Config.h"
#include <stdlib.h>
#include <math.h>

#define TMC_SERIAL Serial2 

StepperController::StepperController() {
    _stepPins[AXIS_X] = PIN_STEP_X;
    _dirPins[AXIS_X] = PIN_DIR_X;

    _stepPins[AXIS_Y] = PIN_STEP_Y;
    _dirPins[AXIS_Y] = PIN_DIR_Y;

    _stepPins[AXIS_Z] = PIN_STEP_Z;
    _dirPins[AXIS_Z] = PIN_DIR_Z;
    
    _enPin = PIN_EN;
    
    // Initialize position tracking and limits
    _limitsEnabled = true;
    for(int i = 0; i < 3; i++) {
        _positionMM[i] = 0.0;
        _motion[i].active = false;
        _motion[i].completed = false;
    }
    
    // Default soft limits per axis (adjust to your machine dimensions)
    _limitMin[AXIS_X] = 0.0;    _limitMax[AXIS_X] = 130.0;  // X: 0 to 300mm
    _limitMin[AXIS_Y] = 0.0;    _limitMax[AXIS_Y] = 230.0;  // Y: 0 to 300mm  
    _limitMin[AXIS_Z] = 0.0;    _limitMax[AXIS_Z] = 130.0;  // Z: 0 to 100mm (shorter)
}

void StepperController::init() {
    pinMode(_enPin, OUTPUT);
    digitalWrite(_enPin, LOW); // Enable by default
    
    for(int i = 0; i < 3; i++) {
        pinMode(_stepPins[i], OUTPUT);
        pinMode(_dirPins[i], OUTPUT);
    }
}

void StepperController::enable() {
    digitalWrite(_enPin, LOW);
}

void StepperController::disable() {
    digitalWrite(_enPin, HIGH);
}

void StepperController::setDirection(Axis axis, bool dir) {
    digitalWrite(_dirPins[axis], dir ? HIGH : LOW);
}

void StepperController::step(Axis axis) {
    digitalWrite(_stepPins[axis], HIGH);
    delayMicroseconds(2);
    digitalWrite(_stepPins[axis], LOW);
}

// Calculate delay based on acceleration profile
float StepperController::calculateDelay(long stepNum, long accelSteps, long totalSteps, float minDelay, float accelMM_s2) {
    float currentSpeed;
    
    if (stepNum < accelSteps) {
        // ACCELERATION phase
        currentSpeed = sqrt(2.0 * (accelMM_s2 * STEPS_PER_MM) * (stepNum + 1));
    } 
    else if (stepNum >= totalSteps - accelSteps) {
        // DECELERATION phase
        long stepsRemaining = totalSteps - stepNum;
        currentSpeed = sqrt(2.0 * (accelMM_s2 * STEPS_PER_MM) * stepsRemaining);
    } 
    else {
        // CONSTANT SPEED phase
        return minDelay;
    }
    
    float delay = 1000000.0 / currentSpeed;
    if (delay > 20000) delay = 20000;  // Safety clamp
    if (delay < minDelay) delay = minDelay;
    return delay;
}

// Start a non-blocking move
void StepperController::startMove(Axis axis, float distanceMM, float maxSpeedMM_s, float accelMM_s2) {
    // Apply defaults if needed
    if (maxSpeedMM_s <= 0) maxSpeedMM_s = MAX_SPEED_MM_S;
    if (accelMM_s2 <= 0) accelMM_s2 = MAX_ACCEL_MM_S2;
    
    long steps = (long)(distanceMM * STEPS_PER_MM);
    if (steps == 0) return;
    
    MotionState& m = _motion[axis];
    
    m.direction = steps > 0;
    m.targetSteps = abs(steps);
    m.currentStep = 0;
    m.completed = false;
    
    // Set direction
    setDirection(axis, m.direction);
    
    // Calculate acceleration steps
    m.accelSteps = (long)((maxSpeedMM_s * maxSpeedMM_s * STEPS_PER_MM * STEPS_PER_MM) / (2.0 * accelMM_s2 * STEPS_PER_MM));
    if (m.accelSteps > m.targetSteps / 2) {
        m.accelSteps = m.targetSteps / 2;
    }
    
    // Calculate min delay (at max speed)
    m.minDelay = 1000000.0 / (maxSpeedMM_s * STEPS_PER_MM);
    
    // Calculate initial delay
    m.currentDelay = calculateDelay(0, m.accelSteps, m.targetSteps, m.minDelay, accelMM_s2);
    
    m.lastStepTime = micros();
    m.active = true;
}

// Process non-blocking motion for all axes (call in loop)
void StepperController::update() {
    unsigned long now = micros();
    
    for (int i = 0; i < 3; i++) {
        MotionState& m = _motion[i];
        
        if (!m.active) continue;
        
        // Check if enough time has passed for next step
        if (now - m.lastStepTime >= (unsigned long)m.currentDelay) {
            // Take a step
            step((Axis)i);
            m.currentStep++;
            m.lastStepTime = now;
            
            // Update position tracking
            float stepMM = 1.0 / STEPS_PER_MM;
            if (m.direction) {
                _positionMM[i] += stepMM;
            } else {
                _positionMM[i] -= stepMM;
            }
            
            // Check if move complete
            if (m.currentStep >= m.targetSteps) {
                m.active = false;
                m.completed = true;
            } else {
                // Check soft limits
                if (_limitsEnabled) {
                    if (_positionMM[i] <= _limitMin[i] || _positionMM[i] >= _limitMax[i]) {
                        m.active = false;
                        m.completed = true;
                        Serial.printf("LIMIT %d %.2f\n", i, _positionMM[i]);
                    }
                }
                
                // Calculate next delay
                m.currentDelay = calculateDelay(m.currentStep, m.accelSteps, m.targetSteps, m.minDelay, MAX_ACCEL_MM_S2);
            }
        }
    }
}

// Legacy blocking move (for compatibility)
void StepperController::moveMM(Axis axis, float distanceMM, float maxSpeedMM_s, float accelMM_s2) {
    startMove(axis, distanceMM, maxSpeedMM_s, accelMM_s2);
    
    // Block until complete
    while (_motion[axis].active) {
        update();
    }
}

bool StepperController::isBusy(Axis axis) {
    return _motion[axis].active;
}

bool StepperController::isAnyBusy() {
    return _motion[AXIS_X].active || _motion[AXIS_Y].active || _motion[AXIS_Z].active;
}

bool StepperController::checkCompleted(Axis axis) {
    if (_motion[axis].completed) {
        _motion[axis].completed = false;  // Clear flag
        return true;
    }
    return false;
}

float StepperController::getPositionMM(Axis axis) {
    return _positionMM[axis];
}

void StepperController::setPositionMM(Axis axis, float pos) {
    _positionMM[axis] = pos;
}

void StepperController::homeAll() {
    stopAll();
    enable();  // Re-enable motors
    for (int i = 0; i < 3; i++) {
        _positionMM[i] = 0.0;
    }
}

void StepperController::stopAll() {
    for (int i = 0; i < 3; i++) {
        stopAxis((Axis)i);
    }
}

void StepperController::stopAxis(Axis axis) {
    _motion[axis].active = false;
    _motion[axis].completed = false;
}

void StepperController::setLimits(Axis axis, float minMM, float maxMM) {
    _limitMin[axis] = minMM;
    _limitMax[axis] = maxMM;
}

void StepperController::enableLimits(bool enable) {
    _limitsEnabled = enable;
}

bool StepperController::isAtLimit(Axis axis) {
    return _positionMM[axis] <= _limitMin[axis] || _positionMM[axis] >= _limitMax[axis];
}

float StepperController::getLimitMax(Axis axis) {
    return _limitMax[axis];
}

