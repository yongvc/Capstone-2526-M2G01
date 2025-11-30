#ifndef PINMAP_H
#define PINMAP_H

#include <Arduino.h>

// --- Onboard LEDs (4) ---
// Update these pins according to your custom board layout
#define PIN_LED_1  39
#define PIN_LED_2  40
#define PIN_LED_3  41
#define PIN_LED_4  42

// --- Servos (4) ---
#define PIN_SERVO_1 9
#define PIN_SERVO_2 10
#define PIN_SERVO_3 11
#define PIN_SERVO_4 12

// --- Steppers (X, Y, Z) ---
// TMC2209 UART Pins (SoftwareSerial or HardwareSerial)
// Assuming separate UART pins or shared single wire UART. 
// If using HardwareSerial, define RX/TX.
#define PIN_TMC_RX 2
#define PIN_TMC_TX 1

#define PIN_EN    20
// X Axis
#define PIN_STEP_X  8
#define PIN_DIR_X   18

// Y Axis
#define PIN_STEP_Y  17
#define PIN_DIR_Y   16

// Z Axis
#define PIN_STEP_Z  15
#define PIN_DIR_Z   7

// --- Limit Switches (Mapped to IO pins for now) ---
#define PIN_LIMIT_X PIN_IO_1
#define PIN_LIMIT_Y PIN_IO_2
#define PIN_LIMIT_Z PIN_IO_3

// --- Digital IOs (5) ---
#define PIN_IO_1    13
#define PIN_IO_2    14
#define PIN_IO_3    21
#define PIN_IO_4    47
#define PIN_IO_5    48

#endif // PINMAP_H
