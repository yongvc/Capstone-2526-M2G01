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
  while(!Serial) delay(10);
  Serial.println("Motor Controller Firmware Starting...");

  ledController.init();
  servoController.init();
  stepperController.init();
  ioController.init();

  // Initialize servo positions to neutral (90 degrees)
  servoController.write(0, 90);  // Cutter 1
  servoController.write(1, 90);  // Cutter 2
  servoController.write(2, 90);  // Gripper/Drop
  servoController.write(3, 90);  // Spare

  Serial.println("Initialization Complete.");
  Serial.println("Commands: M(ove) ?(status) !(stop) H(ome) S(ervo) C(ut) D(rop) L(ed) I(o) Z(limit)");
  
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
          Serial.printf("OK L %d %d\n", index, state);
        }
        break;
        
      case 'S': // Servo: S <index> <angle>
        {
          int index = Serial.parseInt();
          int angle = Serial.parseInt();
          servoController.write(index, angle);
          Serial.printf("OK S %d %d\n", index, angle);
        }
        break;
        
      case 'M': // Move Stepper (non-blocking): M <axis> <distance_mm> <speed> <accel>
        {
          int axis = Serial.parseInt();
          float distanceMM = Serial.parseFloat();
          float maxSpeed = Serial.parseFloat();
          float accel = Serial.parseFloat();
          
          if(maxSpeed <= 0) maxSpeed = StepperController::MAX_SPEED_MM_S;
          if(accel <= 0) accel = StepperController::MAX_ACCEL_MM_S2;

          stepperController.startMove((Axis)axis, distanceMM, maxSpeed, accel);
          Serial.printf("OK M %d %.2f\n", axis, distanceMM);
        }
        break;
        
      case 'B': // Blocking Move: B <axis> <distance_mm> <speed> <accel>
        {
          int axis = Serial.parseInt();
          float distanceMM = Serial.parseFloat();
          float maxSpeed = Serial.parseFloat();
          float accel = Serial.parseFloat();
          
          if(maxSpeed <= 0) maxSpeed = StepperController::MAX_SPEED_MM_S;
          if(accel <= 0) accel = StepperController::MAX_ACCEL_MM_S2;

          Serial.printf("BUSY M %d\n", axis);
          stepperController.moveMM((Axis)axis, distanceMM, maxSpeed, accel);
          Serial.printf("DONE %d\n", axis);
        }
        break;
        
      case '?': // STATUS - Query motor position and busy state
        {
          // Position
          Serial.printf("POS %.2f %.2f %.2f\n", 
            stepperController.getPositionMM(AXIS_X),
            stepperController.getPositionMM(AXIS_Y),
            stepperController.getPositionMM(AXIS_Z));
          // Busy state
          Serial.printf("BUSY %d %d %d\n",
            stepperController.isBusy(AXIS_X) ? 1 : 0,
            stepperController.isBusy(AXIS_Y) ? 1 : 0,
            stepperController.isBusy(AXIS_Z) ? 1 : 0);
        }
        break;
        
      case 'G': // CONFIG - Get axis limits
        {
          Serial.printf("LIMITS %.2f %.2f %.2f\n", 
            stepperController.getLimitMax(AXIS_X),
            stepperController.getLimitMax(AXIS_Y),
            stepperController.getLimitMax(AXIS_Z));
        }
        break;
        
      case '!': // Emergency stop
        {
          stepperController.stopAll();
          Serial.println("STOP");
        }
        break;
        
      case 'H': // SET ZERO - Reset position to 0,0,0 and lock motors
        {
          stepperController.homeAll();
          Serial.println("OK H");
        }
        break;
        
      case 'R': // UNLOCK - Disable steppers for manual movement
        {
          stepperController.disable();
          Serial.println("OK R");
        }
        break;
        
      case 'P': // Set position: P <axis> <position_mm>
        {
          int axis = Serial.parseInt();
          float pos = Serial.parseFloat();
          stepperController.setPositionMM((Axis)axis, pos);
          Serial.printf("OK P %d %.2f\n", axis, pos);
        }
        break;
        
      case 'W': // Set limits: W <axis> <min_mm> <max_mm>
        {
          int axis = Serial.parseInt();
          float minMM = Serial.parseFloat();
          float maxMM = Serial.parseFloat();
          stepperController.setLimits((Axis)axis, minMM, maxMM);
          Serial.printf("OK W %d %.2f %.2f\n", axis, minMM, maxMM);
        }
        break;
        
      case 'E': // Enable/disable limits: E <0|1>
        {
          int enable = Serial.parseInt();
          stepperController.enableLimits(enable != 0);
          Serial.printf("OK E %d\n", enable);
        }
        break;
        
      case 'I': // Read IO: I <index>
        {
          int index = Serial.parseInt();
          bool val = ioController.readDigital(index);
          Serial.printf("IO %d %d\n", index, val);
        }
        break;
        
      case 'Z': // Read Limit: Z <axis>
        {
          int axis = Serial.parseInt();
          bool val = ioController.readLimitSwitch(axis);
          Serial.printf("LIMIT %d %d\n", axis, val);
        }
        break;
        
      case 'C': // Cut sequence
        {
          int angle = Serial.parseInt();
          Serial.println("BUSY C");
          servoController.write(0, 90-angle);
          servoController.write(1, 90+angle);
          delay(300);
          servoController.write(0, 90);
          servoController.write(1, 90);
          delay(300);
          servoController.write(0, 90-angle);
          servoController.write(1, 90+angle);
          delay(300);
          servoController.write(0, 90);
          servoController.write(1, 90);
          delay(300);
          servoController.write(0, 90-angle);
          servoController.write(1, 90+angle);
          delay(300);
          servoController.write(0, 90);
          servoController.write(1, 90);
          delay(300);
          servoController.write(0, 90-angle);
          servoController.write(1, 90+angle);
          delay(300);
          servoController.write(0, 90);
          servoController.write(1, 90);
          delay(300);
          servoController.write(0, 90-angle);
          servoController.write(1, 90+angle);
          delay(300);
          servoController.write(0, 90);
          servoController.write(1, 90);
          Serial.println("OK C");
        }
        break;
        
      case 'D': // Drop sequence
        {
          int angle = Serial.parseInt();
          Serial.println("BUSY D");
          servoController.write(2, 90-angle);
          delay(1000);
          servoController.write(2, 90);
          Serial.println("OK D");
        }
        break;
    }
    
    // Clear remaining characters only until newline (preserve next command)
    while(Serial.available()) {
      char c = Serial.read();
      if (c == '\n' || c == '\r') break;  // Stop at end of this command
    }
  }
}

void loop() {
  ledController.update();
  stepperController.update();
  
  // --- LED Status Updates ---
  // LED 0: Heartbeat (set in setup)
  
  // LED 1: Moving/Action Indicator
  if (stepperController.isAnyBusy()) {
    ledController.set(1, HIGH);
  } else {
    ledController.set(1, LOW);
  }
  
  // LED 2: Ready/Home Indicator (All axes at 0)
  bool isHome = (stepperController.getPositionMM(AXIS_X) == 0 && 
                 stepperController.getPositionMM(AXIS_Y) == 0 && 
                 stepperController.getPositionMM(AXIS_Z) == 0);
  if (isHome) {
    ledController.set(2, HIGH);
  } else {
    ledController.set(2, LOW);
  }
  
  // LED 3: Limit/Error Warning
  bool atLimit = (stepperController.isAtLimit(AXIS_X) || 
                  stepperController.isAtLimit(AXIS_Y) || 
                  stepperController.isAtLimit(AXIS_Z));
  
  static bool wasAtLimit = false;
  if (atLimit && !wasAtLimit) {
    ledController.blink(3, 100); // Fast blink on error/limit
  } else if (!atLimit && wasAtLimit) {
    ledController.set(3, LOW);   // Off when safe
  }
  wasAtLimit = atLimit;
  // --------------------------
  
  // Check for move completions and report
  for(int i = 0; i < 3; i++) {
    if(stepperController.checkCompleted((Axis)i)) {
      Serial.printf("DONE %d\n", i);
    }
  }
  
  processSerialCommand();
}
