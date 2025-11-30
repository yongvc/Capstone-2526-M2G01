#include "ServoController.h"
#include "PinMap.h"
#include "Config.h"

ServoController::ServoController() {
    _pins[0] = PIN_SERVO_1;
    _pins[1] = PIN_SERVO_2;
    _pins[2] = PIN_SERVO_3;
    _pins[3] = PIN_SERVO_4;
}

void ServoController::init() {
    // ESP32Servo needs to be attached
    // We can allocate timers if needed, but the library handles it mostly
    for(int i=0; i<4; i++) {
        _servos[i].setPeriodHertz(50); // Standard 50hz servo
        _servos[i].attach(_pins[i], SERVO_MIN_US, SERVO_MAX_US);
    }
}

void ServoController::write(uint8_t index, int angle) {
    if(index < 4) {
        if(angle < 0) angle = 0;
        if(angle > 180) angle = 180;
        _servos[index].write(angle);
    }
}
