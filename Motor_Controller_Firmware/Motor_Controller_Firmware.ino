#include <Arduino.h>
#include "Config.h"
#include "PinMap.h"
#include "LEDController.h"
#include "ServoController.h"
#include "StepperController.h"
#include "IOController.h"

// Instantiate Controllers
LEDController ledController;
ServoController servoController;
StepperController stepperController;
IOController ioController;

void setup() {
  Serial.begin(SERIAL_BAUD_RATE);
  while(!Serial) delay(10); // Wait for serial
  Serial.println("Motor Controller Firmware Starting...");

  // Initialize Controllers
  ledController.init();
  servoController.init();
  stepperController.init();
  ioController.init();

  Serial.println("Initialization Complete.");
  
  // Blink LED 1 to show life
  ledController.blink(0, 500);
}

void processSerialCommand() {
  if (Serial.available() > 0) {
    char cmd = Serial.read();
    
    switch(cmd) {
      case 'L': // LED: L <index> <state>
        {
          int index = Serial.parseInt();
          int state = Serial.parseInt();
          ledController.set(index, state);
          Serial.printf("LED %d set to %d\n", index, state);
        }
        break;
      case 'S': // Servo: S <index> <angle>
        {
          int index = Serial.parseInt();
          int angle = Serial.parseInt();
          servoController.write(index, angle);
          Serial.printf("Servo %d set to %d\n", index, angle);
        }
        break;
      case 'M': // Move Stepper: M <axis> <distance_mm> <max_speed_mm_s> <accel_mm_s2>
        {
          int axis = Serial.parseInt();
          float distanceMM = Serial.parseFloat();
          float maxSpeed = Serial.parseFloat();
          float accel = Serial.parseFloat();
          
          if(maxSpeed <= 0) maxSpeed = StepperController::MAX_SPEED_MM_S; // Default speed mm/s
          if(accel <= 0) accel = StepperController::MAX_ACCEL_MM_S2; // Default accel mm/s^2

          Serial.printf("Moving Axis %d, %.2f mm, Speed %.2f, Accel %.2f\n", axis, distanceMM, maxSpeed, accel);
          
          stepperController.moveMM((Axis)axis, distanceMM, maxSpeed, accel);
          
          Serial.println("Move Complete");
        }
        break;
      case 'I': // Read IO: I <index>
        {
          int index = Serial.parseInt();
          bool val = ioController.readDigital(index);
          Serial.printf("IO %d: %d\n", index, val);
        }
        break;
      case 'Z': // Read Limit: Z <axis>
        {
          int axis = Serial.parseInt();
          bool val = ioController.readLimitSwitch(axis);
          Serial.printf("Limit %d: %d\n", axis, val);
        }
        break;
      case 'C':
        {
          int angle = Serial.parseInt();
          servoController.write(0, 90-angle);
          servoController.write(1, 90+angle);
          delay(300);
          servoController.write(0, 90);
          servoController.write(1, 90);
          delay(200);
          servoController.write(0, 90-angle);
          servoController.write(1, 90+angle);
          delay(300);
          servoController.write(0, 90);
          servoController.write(1, 90);
        }
        break;
      case 'D':
        {
          int angle = Serial.parseInt();
          servoController.write(2, 90-angle);
          delay(1000);
          servoController.write(2, 90);
          
        }
        break;
    }
    
    // Clear buffer
    while(Serial.available()) Serial.read();
  }
}

void loop() {
  ledController.update();
  processSerialCommand();
}
