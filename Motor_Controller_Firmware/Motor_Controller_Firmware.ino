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
      case 'M': // Move Stepper: M <axis> <steps> <dir> <delay_us>
        {
          int axis = Serial.parseInt();
          int steps = Serial.parseInt();
          int dir = Serial.parseInt();
          int delayUs = Serial.parseInt();
          if(delayUs <= 0) delayUs = 1000; // Default speed

          stepperController.setDirection((Axis)axis, dir);
          Serial.printf("Moving Axis %d, %d steps, dir %d\n", axis, steps, dir);
          
          // Blocking move for simple demo
          for(int i=0; i<steps; i++) {
            stepperController.step((Axis)axis);
            delayMicroseconds(delayUs);
          }
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
    }
    
    // Clear buffer
    while(Serial.available()) Serial.read();
  }
}

void loop() {
  ledController.update();
  processSerialCommand();
}
