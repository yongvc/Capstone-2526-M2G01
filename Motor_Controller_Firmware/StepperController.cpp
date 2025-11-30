#include "StepperController.h"
#include "PinMap.h"
#include "Config.h"
#include <stdlib.h>
#include <math.h>

// Assuming Serial2 for TMC UART communication
#define TMC_SERIAL Serial2 

StepperController::StepperController() {
    _stepPins[AXIS_X] = PIN_STEP_X;
    _dirPins[AXIS_X] = PIN_DIR_X;

    _stepPins[AXIS_Y] = PIN_STEP_Y;
    _dirPins[AXIS_Y] = PIN_DIR_Y;

    _stepPins[AXIS_Z] = PIN_STEP_Z;
    _dirPins[AXIS_Z] = PIN_DIR_Z;
    
    _enPin = PIN_EN;
}

void StepperController::init() {
    // Initialize pins
    pinMode(_enPin, OUTPUT);
    digitalWrite(_enPin, LOW); // Enable by default
    
    for(int i=0; i<3; i++) {
        pinMode(_stepPins[i], OUTPUT);
        pinMode(_dirPins[i], OUTPUT);
    }

    // // Initialize UART for TMC
    // TMC_SERIAL.begin(SERIAL_BAUD_RATE, SERIAL_8N1, PIN_TMC_RX, PIN_TMC_TX);

    // // Setup drivers
    // // Assuming addresses 0, 1, 2 for X, Y, Z. 
    // // If using single wire UART without addressing, this needs adjustment.
    // // The Janelia library setup: setup(Stream& serial, long baud_rate, uint8_t address)
    
    // _tmc[AXIS_X].setup(TMC_SERIAL, SERIAL_BAUD_RATE, TMC2209::SERIAL_ADDRESS_0);
    // _tmc[AXIS_Y].setup(TMC_SERIAL, SERIAL_BAUD_RATE, TMC2209::SERIAL_ADDRESS_1);
    // _tmc[AXIS_Z].setup(TMC_SERIAL, SERIAL_BAUD_RATE, TMC2209::SERIAL_ADDRESS_2);

    // // Configure defaults
    // for(int i=0; i<3; i++) {
    //     _tmc[i].setRunCurrent(500); // Default 500mA
    //     _tmc[i].setMicrostepsPerStep(16); // Default 16 microsteps
    //     _tmc[i].enable(); // Enable the driver via UART (if supported/needed in addition to EN pin)
    // }
}

void StepperController::enable() {
    digitalWrite(_enPin, LOW); // Enable (shared pin)
    // for(int i=0; i<3; i++) {
    //     _tmc[i].enable();
    // }
}

void StepperController::disable() {
    // Note: Disabling the shared pin disables ALL axes. 
    // If we want individual control, we rely on UART disable, 
    // but if we want to save power on all, we toggle the pin.
    // For now, we only disable the specific driver via UART, 
    // unless we want to enforce hardware disable.
    // Let's keep the pin LOW (enabled) if we want any axis to run.
    // This logic might need refinement if independent hardware disable is required.
    // for(int i=0; i<3; i++) {
    //     _tmc[i].disable();
    // }
    digitalWrite(_enPin, HIGH); // Disable (shared pin)
}

void StepperController::setDirection(Axis axis, bool dir) {
    digitalWrite(_dirPins[axis], dir ? HIGH : LOW);
}

void StepperController::step(Axis axis) {
    digitalWrite(_stepPins[axis], HIGH);
    delayMicroseconds(2); // Minimum pulse width
    digitalWrite(_stepPins[axis], LOW);
}

void StepperController::moveMM(Axis axis, float distanceMM, float maxSpeedMM_s, float accelMM_s2) {
    long steps = (long)(distanceMM * STEPS_PER_MM);
    if (steps == 0) return;
    
    bool dir = steps > 0;
    steps = abs(steps);
    setDirection(axis, dir);

    // Calculate limit for acceleration (steps to reach max speed)
    // v^2 = 2*a*s  ->  s = v^2 / 2a
    long accelSteps = (long)((maxSpeedMM_s * maxSpeedMM_s * STEPS_PER_MM * STEPS_PER_MM) / (2.0 * accelMM_s2 * STEPS_PER_MM));
    
    // If path is too short, we accel to half point then decel
    if (accelSteps > steps / 2) {
        accelSteps = steps / 2;
    }

    // Min delay (at max speed)
    float minDelayUs = 1000000.0 / (maxSpeedMM_s * STEPS_PER_MM);
    
    // Initial delay (based on acceleration start)
    // v = sqrt(2 * a * s) where s=1 step
    float startVelocity = sqrt(2.0 * accelMM_s2 * STEPS_PER_MM);
    float currentDelay = 1000000.0 / startVelocity;

    for(long i = 0; i < steps; i++) {
        float currentSpeed; // Steps per second

        if (i < accelSteps) {
            // ACCELERATION: v = sqrt(2 * a * s)
            // We use (i+1) to avoid zero
            currentSpeed = sqrt(2.0 * (accelMM_s2 * STEPS_PER_MM) * (i + 1));
            currentDelay = 1000000.0 / currentSpeed;
        } 
        else if (i >= steps - accelSteps) {
            // DECELERATION
            long stepsRemaining = steps - i;
            currentSpeed = sqrt(2.0 * (accelMM_s2 * STEPS_PER_MM) * stepsRemaining);
            currentDelay = 1000000.0 / currentSpeed;
        } 
        else {
            // CONSTANT SPEED
            currentDelay = minDelayUs;
        }

        // Safety clamp for delay
        if(currentDelay > 20000) currentDelay = 20000; 

        step(axis);
        
        // Use a precise delay. 
        // Note: Overhead of sqrt() is high. 
        // For 8-bit Arduino, this loop might be too slow for high speeds.
        // For ESP32/STM32, this is fine.
        delayMicroseconds((unsigned int)currentDelay);
    }
}
