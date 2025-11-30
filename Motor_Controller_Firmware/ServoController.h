#ifndef SERVOCONTROLLER_H
#define SERVOCONTROLLER_H

#include <Arduino.h>
#include <ESP32Servo.h>

class ServoController {
public:
    ServoController();
    void init();
    void write(uint8_t index, int angle);

private:
    Servo _servos[4];
    uint8_t _pins[4];
};

#endif
