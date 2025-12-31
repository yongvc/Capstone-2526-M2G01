#ifndef STEPPERCONTROLLER_H
#define STEPPERCONTROLLER_H

#include <Arduino.h>
#include <TMC2209.h>

enum Axis {
    AXIS_X = 0,
    AXIS_Y = 1,
    AXIS_Z = 2
};

class StepperController {
public:
    StepperController();
    void init();
    void enable();
    void disable();
    
    // Motion control
    void setDirection(Axis axis, bool dir);
    void step(Axis axis); // Generate a single step pulse
    void moveMM(Axis axis, float distanceMM, float maxSpeedMM_s, float accelMM_s2);

    static constexpr float STEPS_PER_MM = 40.0;
    static constexpr float MAX_SPEED_MM_S = 500.0;
    static constexpr float MAX_ACCEL_MM_S2 = 6000.0;

private:
    TMC2209 _tmc[3]; // One driver object per axis
    // Pin mappings
    uint8_t _stepPins[3];
    uint8_t _dirPins[3];
    uint8_t _enPin;
    
    // Helper to setup TMC
    void setupDriver(Axis axis, uint8_t address);
};

#endif
