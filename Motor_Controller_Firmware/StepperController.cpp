#include "StepperController.h"
#include "PinMap.h"
#include "Config.h"

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
    digitalWrite(_enPin, HIGH); // Disable by default

    for(int i=0; i<3; i++) {
        pinMode(_stepPins[i], OUTPUT);
        pinMode(_dirPins[i], OUTPUT);
    }

    // Initialize UART for TMC
    TMC_SERIAL.begin(SERIAL_BAUD_RATE, SERIAL_8N1, PIN_TMC_RX, PIN_TMC_TX);

    // Setup drivers
    // Assuming addresses 0, 1, 2 for X, Y, Z. 
    // If using single wire UART without addressing, this needs adjustment.
    // The Janelia library setup: setup(Stream& serial, long baud_rate, uint8_t address)
    
    _tmc[AXIS_X].setup(TMC_SERIAL, SERIAL_BAUD_RATE, TMC2209::SERIAL_ADDRESS_0);
    _tmc[AXIS_Y].setup(TMC_SERIAL, SERIAL_BAUD_RATE, TMC2209::SERIAL_ADDRESS_1);
    _tmc[AXIS_Z].setup(TMC_SERIAL, SERIAL_BAUD_RATE, TMC2209::SERIAL_ADDRESS_2);

    // Configure defaults
    for(int i=0; i<3; i++) {
        _tmc[i].setRunCurrent(500); // Default 500mA
        _tmc[i].setMicrostepsPerStep(16); // Default 16 microsteps
        _tmc[i].enable(); // Enable the driver via UART (if supported/needed in addition to EN pin)
    }
}

void StepperController::enable(Axis axis) {
    digitalWrite(_enPin, LOW); // Enable (shared pin)
    _tmc[axis].enable();
}

void StepperController::disable(Axis axis) {
    // Note: Disabling the shared pin disables ALL axes. 
    // If we want individual control, we rely on UART disable, 
    // but if we want to save power on all, we toggle the pin.
    // For now, we only disable the specific driver via UART, 
    // unless we want to enforce hardware disable.
    // Let's keep the pin LOW (enabled) if we want any axis to run.
    // This logic might need refinement if independent hardware disable is required.
    _tmc[axis].disable();
}

void StepperController::setMicrosteps(Axis axis, int microsteps) {
    _tmc[axis].setMicrostepsPerStep(microsteps);
}

void StepperController::setCurrent(Axis axis, int ma) {
    _tmc[axis].setRunCurrent(ma);
}

void StepperController::setDirection(Axis axis, bool dir) {
    digitalWrite(_dirPins[axis], dir ? HIGH : LOW);
}

void StepperController::step(Axis axis) {
    digitalWrite(_stepPins[axis], HIGH);
    delayMicroseconds(2); // Minimum pulse width
    digitalWrite(_stepPins[axis], LOW);
}
