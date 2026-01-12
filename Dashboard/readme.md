# Robot Dashboard

The Dashboard is the central control interface for the Lemon Harvesting Robot. It provides real-time camera visualization, computer vision-based lemon detection with Kalman tracking, and automated harvesting control through a visual servo system.

## Architecture

```
main.py (DashboardApp)
    |
    +-- camera.py
    |   +-- CameraThread      (30 FPS capture, triple-buffered)
    |   +-- DetectionThread   (async detection, Kalman tracking)
    |   +-- FrameBuffer       (zero-copy frame delivery)
    |
    +-- harvester.py
    |   +-- HarvestingStateMachine (visual servo control)
    |   +-- HarvestState enum (IDLE, APPROACHING, CUTTING, DEPOSITING, RETURNING)
    |
    +-- embedded_cv_display.py
    |   +-- EmbeddedCVDisplay (native OpenCV in Tkinter)
    |
    +-- LemonDetector/
        +-- detect.py         (HSV + Watershed detection)
        +-- kalman_tracker.py (Kalman filter tracking)
```

## Features

### Real-time Computer Vision
- **HSV Color Segmentation**: Optimized for yellow lemon detection
- **Watershed Algorithm**: Separates touching/overlapping fruits
- **Multi-Object Tracking**: Persistent IDs across frames
- **Kalman Filter Smoothing**: Reduces jitter, predicts during occlusion

### Visual Servo Control
- **Closed-Loop Approach**: Uses camera feedback for alignment
- **Multi-Axis Simultaneous Movement**: X, Y, Z move together for smooth tracking
- **Dynamic Speed Control**: Fast when far, slow when close for precision
- **Area-Based Distance Estimation**: Triggers cutting when lemon is close enough

### Harvesting Automation
- **Single Target Mode**: Select and harvest one lemon
- **Auto-Harvest Mode**: Consecutively harvest 3 lemons (configurable)
- **State Machine**: IDLE -> APPROACHING -> CUTTING -> DEPOSITING -> RETURNING
- **Jitter Tolerance**: Maintains tracking during camera vibration (up to 3s occlusion)

### User Interface
- **Dark Theme**: Modern CustomTkinter interface
- **Embedded Video Display**: Native OpenCV rendering at 60 FPS
- **Manual Controls**: Direct stepper and servo control
- **Status Display**: FPS, harvest state, detected lemons list
- **Center Offset**: Calibrate cutter position relative to camera

## Module Documentation

### main.py - DashboardApp

The main application class that integrates all components:

```python
class DashboardApp(ctk.CTk):
    def __init__(self):
        # Initialize camera and detection threads
        self.camera_thread = CameraThread(mock_mode=False, target_fps=30)
        self.detection_thread = DetectionThread(self.camera_thread.frame_buffer)
        
        # Initialize harvesting state machine
        self.harvester = HarvestingStateMachine(self)
        
        # Setup UI components
        self.setup_controls()
```

Key methods:
- `toggle_connection()`: Connect/disconnect serial port
- `update_camera_ui()`: Main UI update loop (33ms interval)
- `start_harvest()`: Begin harvesting selected lemon
- `start_auto_harvest()`: Begin auto-harvest mode
- `send_command(cmd)`: Send command to firmware

### camera.py - Multi-Threaded Capture

**CameraThread**: Captures frames at target FPS
```python
class CameraThread(threading.Thread):
    def __init__(self, mock_mode=False, mock_path="mock_lemon.mp4", target_fps=30):
        self.frame_buffer = FrameBuffer()  # Triple-buffered output
```

**DetectionThread**: Runs detection asynchronously
```python
class DetectionThread(threading.Thread):
    def __init__(self, frame_buffer):
        self.detector = LemonDetector(use_kalman=True, responsive_tracking=True)
    
    def get_latest(self):
        return self._latest_frame, list(self._latest_lemons)
```

**FrameBuffer**: Zero-copy frame delivery
```python
class FrameBuffer:
    def write(self, frame): # Producer (camera thread)
    def read(self):         # Consumer (detection thread)
    def wait_for_frame(self, timeout=0.1):
```

### harvester.py - Harvesting State Machine

Visual servo control with multi-axis simultaneous movement:

```python
class HarvestingStateMachine:
    # Key parameters (tunable)
    self.area_threshold = 23000       # pixels^2 to trigger cutting
    self.approach_threshold = 25      # pixels alignment tolerance
    self.visual_servo_gain = 0.10     # mm per pixel error
    self.forward_speed = 20.0         # mm per forward step
    self.max_correction = 15.0        # max mm per correction
    self._max_frames_lost = 90        # 3 seconds at 30fps before abort
    
    # Speed settings
    self.approach_speed = 30          # mm/s for X/Z corrections
    self.forward_approach_speed = 80  # mm/s for Y forward
    self.fast_speed = 200             # mm/s for deposit/return
    
    # Cutter offsets
    self.cutting_z_offset = 50        # mm (cutter below camera)
    self.cutting_y_offset = 60        # mm (cutter behind camera)
```

State transitions:
1. **IDLE**: Waiting for harvest command
2. **APPROACHING**: Visual servo approach using Kalman-smoothed positions
3. **CUTTING**: Move to cutter offset, execute cut sequence
4. **DEPOSITING**: Move to basket, execute drop sequence
5. **RETURNING**: Return to home position

### LemonDetector/detect.py - Detection Pipeline

HSV + Watershed detection with tracking:

```python
class LemonDetector:
    # HSV ranges (tuned for yellow lemons)
    FIXED_H_MIN, FIXED_H_MAX = 10, 30
    FIXED_S_MIN, FIXED_S_MAX = 70, 255
    FIXED_V_MIN, FIXED_V_MAX = 40, 255
    
    # Tracking parameters
    self.maxDisappeared = 1000        # frames before deregistering
    self.maxMatchDistance = 300       # pixels for ID matching
```

Detection pipeline:
1. Gaussian blur (11x11)
2. HSV color thresholding
3. Morphological opening + dilation
4. Distance transform + watershed
5. Contour analysis (filter by area > 1000, circularity > 0.3)
6. Multi-object tracking with Kalman filtering

### LemonDetector/kalman_tracker.py - Smooth Tracking

Constant velocity Kalman filter for each tracked object:

```python
class KalmanTracker:
    # State: [x, y, vx, vy]
    # Responsive mode: process_noise=0.5, measurement_noise=1.0
    
    def predict(self):      # Predict next position
    def update(self, pos):  # Correct with measurement
    def get_position(self): # Get smoothed position
    def get_velocity(self): # Get velocity estimate
```

Benefits:
- Smooths detection jitter from camera vibration
- Predicts position during temporary occlusion (up to 60 frames / 2s in Kalman, 90 frames / 3s in harvester)
- Provides velocity for predictive control

### embedded_cv_display.py - Native OpenCV Display

Embeds OpenCV window inside Tkinter for native rendering performance:

```python
class EmbeddedCVDisplay:
    def _create_and_embed(self):
        # Create OpenCV window
        cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
        
        # Reparent using Windows API
        win32gui.SetParent(self.cv_hwnd, tk_hwnd)
    
    def update(self, frame):
        cv2.imshow(self.window_name, frame)  # Native rendering
```

Performance: ~60 FPS vs ~15 FPS with PIL/ImageTk conversion.

## Setup

1. Navigate to this directory:
    ```bash
    cd Dashboard
    ```

2. Create virtual environment:
    ```bash
    python -m venv venv
    .\venv\Scripts\activate  # Windows
    ```

3. Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

## Usage

Run the main application:
```bash
python main.py
```

### Controls

| Control | Description |
|---------|-------------|
| Connect | Connect to ESP32 via serial port |
| HARVEST | Harvest the selected (highlighted) lemon |
| AUTO (3) | Automatically harvest 3 lemons consecutively |
| ABORT | Stop current harvest and return home |
| Move | Move selected axis by distance/speed/accel |
| Center | Move all axes to home position |
| Set Zero | Set current position as 0,0,0 |
| Unlock | Disable steppers for manual movement |
| Cut/Drop | Test cutter and gripper mechanisms |
| EMERGENCY STOP | Immediately stop all motors |

### Tuning Detection

For different lighting conditions, adjust HSV values in `LemonDetector/detect.py`:
```python
self.FIXED_H_MIN = 10   # Hue minimum (yellow starts ~10)
self.FIXED_H_MAX = 30   # Hue maximum (yellow ends ~35)
self.FIXED_S_MIN = 70   # Saturation minimum (filter out white)
self.FIXED_V_MIN = 40   # Value minimum (filter out dark)
```

Enable tuning mode to use trackbars:
```python
detector = LemonDetector(tuning_mode=True)
```

### Calibrating Center Offset

The cutter is physically offset from the camera. Use the Offset X/Y controls to compensate:
1. Position a lemon at the camera center (crosshair)
2. Observe where the cutter actually aligns
3. Enter offset values to shift the target point
4. Click "Apply" to update

## Key Files

| File | Description |
|------|-------------|
| `main.py` | Main application, UI, serial communication |
| `camera.py` | Multi-threaded camera capture and detection |
| `harvester.py` | Harvesting state machine, visual servo control |
| `embedded_cv_display.py` | Native OpenCV window embedding |
| `LemonDetector/detect.py` | Computer vision detection pipeline |
| `LemonDetector/kalman_tracker.py` | Kalman filter for smooth tracking |
| `mock_lemon.mp4` | Sample video for Mock Mode testing |
| `requirements.txt` | Python dependencies |

## Dependencies

- `customtkinter` - Modern Tkinter widgets
- `opencv-python` - Computer vision
- `numpy` - Numerical operations
- `pyserial` - Serial communication
- `pywin32` - Windows API for embedded display (Windows only)
