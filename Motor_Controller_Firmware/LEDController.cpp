#include "LEDController.h"
#include "PinMap.h"

LEDController::LEDController() {
    _pins[0] = PIN_LED_1;
    _pins[1] = PIN_LED_2;
    _pins[2] = PIN_LED_3;
    _pins[3] = PIN_LED_4;

    for(int i=0; i<4; i++) {
        _isBlinking[i] = false;
        _lastToggleTime[i] = 0;
    }
}

void LEDController::init() {
    for(int i=0; i<4; i++) {
        pinMode(_pins[i], OUTPUT);
        digitalWrite(_pins[i], LOW);
    }
}

void LEDController::set(uint8_t index, bool state) {
    if(index < 4) {
        digitalWrite(_pins[index], state);
        _isBlinking[index] = false; // Stop blinking if manually set
    }
}

void LEDController::toggle(uint8_t index) {
    if(index < 4) {
        digitalWrite(_pins[index], !digitalRead(_pins[index]));
    }
}

void LEDController::blink(uint8_t index, unsigned long interval) {
    if(index < 4) {
        _isBlinking[index] = true;
        _blinkInterval[index] = interval;
    }
}

void LEDController::update() {
    unsigned long currentMillis = millis();
    for(int i=0; i<4; i++) {
        if(_isBlinking[i]) {
            if(currentMillis - _lastToggleTime[i] >= _blinkInterval[i]) {
                toggle(i);
                _lastToggleTime[i] = currentMillis;
            }
        }
    }
}
