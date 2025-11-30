#ifndef LEDCONTROLLER_H
#define LEDCONTROLLER_H

#include <Arduino.h>

class LEDController {
public:
    LEDController();
    void init();
    void set(uint8_t index, bool state);
    void toggle(uint8_t index);
    void blink(uint8_t index, unsigned long interval); // Call this in loop for non-blocking blink
    void update(); // Call in loop

private:
    uint8_t _pins[4];
    unsigned long _lastToggleTime[4];
    unsigned long _blinkInterval[4];
    bool _isBlinking[4];
};

#endif
