# Lemon Harvesting Robot Capstone Project

This project contains the complete source code and design files for an autonomous lemon harvesting robot. The system uses computer vision to detect lemons and controls a robotic arm/gantry to harvest them.

## Directory Structure

- **[`Dashboard/`](./Dashboard)**: The main control software.
    - Python-based GUI (CustomTkinter).
    - Real-time Computer Vision (OpenCV) for Lemon Detection.
    - Serial communication with the firmware.
- **[`Motor_Controller_Firmware/`](./Motor_Controller_Firmware)**:
    - Arduino/C++ firmware for the motor controller.
    - Handles stepper motor movements and servo actions (End Effector).
- **[`CAD/`](./CAD)**:
    - SolidWorks mechanical design files (Assembly, Parts).
- **[`PCB/`](./PCB)**:
    - Printed Circuit Board designs.

## Getting Started

### Prerequisites
- Python 3.x
- Arduino IDE (for firmware upload)
- SolidWorks (to view CAD files)

### Running the Dashboard
1.  Navigate to the `Dashboard` directory.
2.  Activate the virtual environment (if using one):
    ```bash
    .\Dashboard\venv\Scripts\activate
    ```
3.  Run the application:
    ```bash
    python Dashboard/main.py
    ```

### Key Features
- **Real-time Detection**: Uses HSV color segmentation and Watershed algorithm to detect lemons.
- **Mock Mode**: Toggle between live Webcam feed and pre-recorded video for testing without hardware.
- **Motor Control**: Manual and G-Code based control of the 3-axis system.
