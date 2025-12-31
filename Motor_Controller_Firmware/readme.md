# Motor Controller Firmware

This directory contains the firmware for the robot's main controller (Arduino/ESP32 compatible). It handles low-level hardware control including stepper motor drivers, servos, and IO pins.

## Architecture
The firmware is modularized into controllers:
- **`StepperController`**: Manages the movement of the X, Y, Z axes using stepper drivers.
- **`ServoController`**: Controls the harvesting end-effector servo.
- **`LEDController`**: Manages status LEDs.
- **`IOController`**: Handles other input/output signals.
- **`PinMap.h`**: Centralized definition of all pin assignments.

## Communication Protocol
The firmware accepts serial commands (baud rate `115200`):
- **Move Command**: `M <axis> <dist> <speed> <accel>`
- **Servo Command**: `S <id> <angle>`

## Setup
1.  Open `Motor_Controller_Firmware.ino` in the Arduino IDE.
2.  Select the correct board (e.g., Arduino Mega or correct microcontroller).
3.  Upload the code to the board.
