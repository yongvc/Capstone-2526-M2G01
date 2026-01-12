# Lemon Harvesting Robot Capstone Project

This project contains the complete source code and design files for an autonomous lemon harvesting robot. The system uses computer vision to detect lemons and controls a 3-axis gantry robot to harvest them automatically.

## System Architecture

```
+------------------+     Serial (115200)     +------------------+
|    Dashboard     | <------------------->   |   ESP32 MCU      |
|  (Python + CV)   |                         |   (Firmware)     |
+--------+---------+                         +--------+---------+
         |                                            |
         v                                            v
+------------------+                         +------------------+
| - Camera Capture |                         | - TMC2209 x3     |
| - Lemon Detection|                         | - Servos x4      |
| - Kalman Tracking|                         | - LEDs x4        |
| - Visual Servo   |                         | - Soft Limits    |
| - Harvest State  |                         | - I/O Expansion  |
+------------------+                         +------------------+
```

## Directory Structure

- **[`Dashboard/`](./Dashboard)**: The main control software
    - Python-based GUI (CustomTkinter) with dark theme
    - Real-time Computer Vision (OpenCV) for lemon detection
    - Kalman filter tracking for smooth, jitter-resistant control
    - Visual servo control with closed-loop feedback
    - Multi-threaded camera capture at 30 FPS
    - Auto-harvest mode for consecutive fruit harvesting
    - Serial communication with the firmware

- **[`Motor_Controller_Firmware/`](./Motor_Controller_Firmware)**: ESP32 firmware
    - Non-blocking stepper motor control with TMC2209 drivers
    - Trapezoidal acceleration profiles for smooth motion
    - Servo control for cutter and gripper mechanisms
    - 16+ serial commands for complete robot control
    - LED status indicators and soft limit protection

- **[`CAD/`](./CAD)**: Mechanical design files
    - SolidWorks assembly and part files
    - 3-axis gantry robot design

- **[`PCB/`](./PCB)**: Electronics design
    - Printed Circuit Board designs for motor driver integration

- **[`Report/`](./Report)**: Project documentation
    - Individual progress reports
    - Technical documentation

## Key Features

### Computer Vision
- **HSV Color Segmentation**: Tuned for yellow lemon detection (H: 10-30, S: 70-255, V: 40-255)
- **Watershed Algorithm**: Separates touching/overlapping lemons
- **Kalman Filter Tracking**: Smooth position estimation with velocity prediction
- **Persistent Object IDs**: Maintains tracking across frames even during temporary occlusion

### Motion Control
- **Non-Blocking Movement**: Firmware responds to commands during motion
- **Multi-Axis Simultaneous Control**: X, Y, Z axes move together for smooth tracking
- **Visual Servo Control**: Closed-loop approach using camera feedback
- **Trapezoidal Acceleration**: Smooth start/stop for precise positioning

### Harvesting Automation
- **State Machine Control**: IDLE -> APPROACHING -> CUTTING -> DEPOSITING -> RETURNING
- **Auto-Harvest Mode**: Consecutively harvest multiple lemons (configurable count)
- **Dynamic Speed Control**: Fast when far, slow and precise when close
- **Cutter Alignment Offset**: Configurable offset to compensate for camera-cutter distance

### User Interface
- **Real-time Video Display**: Embedded OpenCV window for 60 FPS performance
- **Manual Control Panel**: Direct stepper and servo control
- **Target Selection**: Click to select which lemon to harvest
- **Status Indicators**: FPS display, harvest state, axis positions
- **Mock Mode**: Test with pre-recorded video without hardware

## Getting Started

### Prerequisites
- Python 3.8+ with pip
- Arduino IDE or PlatformIO (for firmware upload)
- ESP32 development board
- USB webcam (640x480 recommended)

### Running the Dashboard

1. Navigate to the `Dashboard` directory:
    ```bash
    cd Dashboard
    ```

2. Create and activate virtual environment:
    ```bash
    python -m venv venv
    # Windows:
    .\venv\Scripts\activate
    # Linux/Mac:
    source venv/bin/activate
    ```

3. Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

4. Run the application:
    ```bash
    python main.py
    ```

### Uploading Firmware

1. Open `Motor_Controller_Firmware/Motor_Controller_Firmware.ino` in Arduino IDE
2. Install required libraries:
   - TMC2209 (for stepper driver communication)
3. Select ESP32 board and correct COM port
4. Upload to the ESP32

### Hardware Setup

1. Connect ESP32 to computer via USB
2. Connect webcam
3. Power on motor drivers (12-24V)
4. In Dashboard, select COM port and click "Connect"
5. Use "Set Zero" to establish home position
6. Start detection and select target lemon
7. Click "HARVEST" or use "AUTO" mode

## Serial Command Protocol

| Command | Format | Description |
|---------|--------|-------------|
| M | `M <axis> <dist> <speed> <accel>` | Non-blocking move (mm) |
| B | `B <axis> <dist> <speed> <accel>` | Blocking move (mm) |
| ? | `?` | Query position and busy state |
| G | `G` | Get axis limits configuration |
| H | `H` | Set current position as zero |
| R | `R` | Release/unlock steppers |
| ! | `!` | Emergency stop |
| S | `S <index> <angle>` | Set servo angle |
| C | `C <angle>` | Execute cut sequence |
| D | `D <angle>` | Execute drop sequence |

## Performance

- **Camera Capture**: 30 FPS (640x480)
- **Detection Rate**: 25-30 FPS
- **Display Rate**: 60 FPS (native OpenCV)
- **Serial Latency**: <50ms round-trip
- **Tracking Recovery**: Up to 3 seconds occlusion tolerance (90 frames)

## Technical Specifications

| Component | Specification |
|-----------|---------------|
| **Axis Travel** | X: 130mm, Y: 230mm, Z: 130mm |
| **Max Speed** | 500 mm/s |
| **Max Acceleration** | 6000 mm/s² |
| **Steps per mm** | 40 |
| **Camera Resolution** | 640 x 480 @ 30 FPS |
| **Detection HSV** | H: 10-30, S: 70-255, V: 40-255 |
| **Kalman Filter** | process_noise=0.5, measurement_noise=1.0 |
| **Visual Servo Gain** | 0.10 mm/pixel |
| **Area Threshold** | 23000 px² (triggers cutting) |
| **Approach Threshold** | 25 px (alignment tolerance) |
| **Cutter Offset** | Z: 50mm, Y: 60mm |
| **Total Cost** | RM 608 |

## Authors

- **M2G01 Team** - UTM Capstone Project 2025/2026
