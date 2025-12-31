# Robot Dashboard

The Dashboard is the central control interface for the Lemon Harvesting Robot. It visualizes the camera feed, runs the lemon detection algorithms, and sends commands to the firmware.

## Features
- **Live Camera Feed**: View real-time video from the robot's camera.
- **Object Detection**: Uses Computer Vision (HSV + Watershed) to detect lemons.
- **Object Tracking**: Assigns unique IDs to lemons and tracks them across frames.
- **Manual Control**: Interface to manually move the robot's stepper motors and servo.
- **Mock Mode**: Toggle to simulate camera input using a video file (`mock_lemon.mp4`) for testing without hardware.

## Setup
1.  Navigate to this directory.
2.  Set up the Python environment:
    ```bash
    python -m venv venv
    .\venv\Scripts\activate
    pip install -r requirements.txt
    ```

## Usage
Run the main application:
```bash
python main.py
```

## Key Files
- `main.py`: The main entry point and UI implementation (CustomTkinter).
- `LemonDetector/detect.py`: The computer vision logic class.
- `mock_lemon.mp4`: A sample video file for Mock Mode testing.
