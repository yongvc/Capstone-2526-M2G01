#include "IOController.h"
#include "PinMap.h"

IOController::IOController() {
    _ioPins[0] = PIN_IO_1;
    _ioPins[1] = PIN_IO_2;
    _ioPins[2] = PIN_IO_3;
    _ioPins[3] = PIN_IO_4;
    _ioPins[4] = PIN_IO_5;

    // Limit switches removed from PinMap
}

void IOController::init() {
    for(int i=0; i<5; i++) {
        pinMode(_ioPins[i], INPUT_PULLUP); // Default to input pullup, safer
    }
}

bool IOController::readDigital(uint8_t index) {
    if(index < 5) {
        return digitalRead(_ioPins[index]);
    }
    return false;
}

void IOController::writeDigital(uint8_t index, bool state) {
    if(index < 5) {
        pinMode(_ioPins[index], OUTPUT); // Ensure it is output
        digitalWrite(_ioPins[index], state);
    }
}

bool IOController::readLimitSwitch(uint8_t axis_index) {
    // Limit switches not defined in PinMap currently
    return false;
}
