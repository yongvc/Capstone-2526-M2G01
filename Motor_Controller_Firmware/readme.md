# Motor Controller Firmware

This directory contains the ESP32 firmware for the robot's motor controller. It provides non-blocking stepper motor control with TMC2209 drivers, servo control for the harvesting mechanism, and a comprehensive serial command protocol.

## Architecture

```
Motor_Controller_Firmware.ino (Main Loop)
    |
    +-- StepperController.cpp/h
    |   - Non-blocking movement with trapezoidal acceleration
    |   - TMC2209 UART driver control
    |   - Position tracking in mm (40 steps/mm)
    |   - Soft limits with min/max per axis
    |   - Move completion detection (checkCompleted)
    |
    +-- ServoController.cpp/h
    |   - PWM control for 4 servos
    |   - Angle-based positioning (0-180 degrees)
    |   - Used for cutter (servos 0,1) and gripper (servo 2)
    |
    +-- LEDController.cpp/h
    |   - 4 status LEDs with non-blocking blink
    |   - LED 0: Heartbeat, LED 1: Moving, LED 2: Home, LED 3: Limit warning
    |
    +-- IOController.cpp/h
    |   - Digital input reading
    |   - Reserved for limit switch inputs (optional hardware)
    |
    +-- Config.h
    |   - Serial baud rate, timing constants
    |
    +-- PinMap.h
        - Pin assignments for ESP32
```

## Features

### Non-Blocking Motor Control
- Motors move without blocking serial command processing
- `M` command returns immediately, firmware sends `DONE <axis>` when complete
- Enables visual servo control with real-time position updates

### Trapezoidal Acceleration
- Smooth acceleration/deceleration profiles
- Configurable max speed (500 mm/s) and acceleration (6000 mm/s^2)
- Per-axis motion state tracking

### Soft Limits (Software-Based)
- Configurable min/max limits per axis
- Prevents over-travel using software position tracking
- No physical limit switches required (optional hardware)
- Limits sent to Dashboard via `G` command

### LED Status Indicators
| LED | Function |
|-----|----------|
| 0 | Heartbeat (continuous blink) |
| 1 | Moving (ON when any axis active) |
| 2 | Home (ON when all axes at 0,0,0) |
| 3 | Limit warning (fast blink when at limit) |

## Serial Command Protocol

**Baud Rate**: 115200

### Motor Commands

| Command | Format | Response | Description |
|---------|--------|----------|-------------|
| M | `M <axis> <dist> <speed> <accel>` | `OK M` then `DONE <axis>` | Non-blocking move |
| B | `B <axis> <dist> <speed> <accel>` | `BUSY M` then `DONE <axis>` | Blocking move |
| ? | `?` | `POS x y z` + `BUSY 0 0 0` | Query position/status |
| G | `G` | `LIMITS x y z` | Get axis limits |
| H | `H` | `OK H` | Set current position as 0,0,0 |
| R | `R` | `OK R` | Release/unlock steppers |
| P | `P <axis> <pos>` | `OK P` | Set axis position value |
| W | `W <axis> <min> <max>` | `OK W` | Set soft limits |
| E | `E <0\|1>` | `OK E` | Enable/disable limits |
| ! | `!` | `STOP` | Emergency stop all axes |

### Servo Commands

| Command | Format | Response | Description |
|---------|--------|----------|-------------|
| S | `S <index> <angle>` | `OK S` | Set servo angle (0-180) |
| C | `C <angle>` | `BUSY C` then `OK C` | Cut sequence (servos 0,1) |
| D | `D <angle>` | `BUSY D` then `OK D` | Drop sequence (servo 2) |

### Utility Commands

| Command | Format | Response | Description |
|---------|--------|----------|-------------|
| L | `L <index> <state>` | `OK L` | Control LED on/off |
| I | `I <index>` | `IO <index> <val>` | Read digital input |
| Z | `Z <axis>` | `LIMIT <axis> <val>` | Read limit switch (optional) |

### Axis Numbering
- 0 = X axis (left-right)
- 1 = Y axis (forward-backward)  
- 2 = Z axis (up-down)

### Response Messages
- `OK <cmd>` - Command accepted
- `BUSY <cmd>` - Command in progress (blocking)
- `DONE <axis>` - Movement complete on axis
- `STOP` - Emergency stop executed
- `POS x y z` - Current position in mm
- `BUSY 0 0 0` - Busy state per axis (0=idle, 1=moving)
- `LIMITS x y z` - Max limits per axis in mm

## Cut Sequence Details

The `C <angle>` command executes a triple-cut sequence:
1. Servos 0,1 move to scissor position (90-angle, 90+angle)
2. Wait 300ms
3. Return to neutral (90, 90)
4. Repeat 3 times for reliable cutting
5. Send `OK C`

## Drop Sequence Details

The `D <angle>` command executes:
1. Servo 2 moves to release position (90-angle)
2. Wait 1000ms for fruit to fall
3. Return to neutral (90)
4. Send `OK D`

## Configuration

### StepperController.h Constants
```cpp
static constexpr float STEPS_PER_MM = 40.0;      // Steps per millimeter
static constexpr float MAX_SPEED_MM_S = 500.0;   // Max speed mm/s
static constexpr float MAX_ACCEL_MM_S2 = 6000.0; // Max acceleration mm/s^2
```

### Default Axis Limits
- X: 0 to 130 mm
- Y: 0 to 230 mm
- Z: 0 to 130 mm

## Setup

1. Open `Motor_Controller_Firmware.ino` in Arduino IDE

2. Install required libraries:
   - **TMC2209** (for stepper driver UART control)

3. Select board:
   - Board: ESP32 Dev Module (or your specific ESP32 variant)
   - Upload Speed: 921600
   - CPU Frequency: 240MHz

4. Upload the firmware

5. Open Serial Monitor at 115200 baud to test:
   ```
   G           # Get limits
   ?           # Query position
   M 0 50 100 200   # Move X axis 50mm
   ```

## Pin Configuration

See `PinMap.h` for detailed pin assignments. Key pins:
- Stepper step/dir pins for X, Y, Z axes
- TMC2209 UART pins for driver configuration
- Servo PWM pins (4 channels)
- LED output pins (4 channels)
- Digital input pins for optional limit switches (currently using software limits)

## Integration with Dashboard

The Dashboard Python application communicates with this firmware:

1. Dashboard connects to COM port at 115200 baud
2. Queries configuration: `G` command
3. Queries position: `?` command  
4. Sends move commands: `M <axis> <dist> <speed> <accel>`
5. Waits for `DONE <axis>` response
6. Executes cut/drop sequences: `C <angle>`, `D <angle>`

The non-blocking `M` command allows the Dashboard to send corrective movements during visual servo approach without waiting for previous moves to complete.
