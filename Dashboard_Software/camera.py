"""
Camera module for high-performance video capture and detection.
"""

import cv2
import threading
import time
from collections import deque
from LemonDetector.detect import LemonDetector


class FrameBuffer:
    """Triple-buffer for zero-copy frame delivery between threads."""

    def __init__(self):
        self._buffers = [None, None, None]
        self._write_idx = 0
        self._read_idx = -1
        self._lock = threading.Lock()
        self._frame_ready = threading.Event()

    def write(self, frame):
        """Write a frame to the buffer (producer side)."""
        with self._lock:
            self._buffers[self._write_idx] = frame
            self._read_idx = self._write_idx
            self._write_idx = (self._write_idx + 1) % 3
        self._frame_ready.set()

    def read(self):
        """Read the latest frame without copying (consumer side)."""
        with self._lock:
            if self._read_idx < 0:
                return None
            return self._buffers[self._read_idx]

    def wait_for_frame(self, timeout=0.1):
        """Wait for a new frame to be available."""
        return self._frame_ready.wait(timeout)

    def clear_event(self):
        """Clear the frame ready event."""
        self._frame_ready.clear()


class CameraThread(threading.Thread):
    """High-performance camera capture thread with FPS control."""

    def __init__(self, mock_mode=False, mock_path="mock_lemon.mp4", target_fps=30):
        super().__init__()
        self.daemon = True
        self.running = True

        self.mock_mode = mock_mode
        self.mock_path = mock_path
        self.target_fps = target_fps
        self._frame_interval = 1.0 / target_fps

        self.cap = None
        self.frame_buffer = FrameBuffer()

        # FPS tracking
        self._fps_times = deque(maxlen=30)
        self._current_fps = 0.0

        # Source update lock
        self._source_lock = threading.Lock()
        self._needs_reopen = False

        self._open_camera()

    def _open_camera(self):
        if self.cap is not None:
            self.cap.release()

        if self.mock_mode:
            print(f"CameraThread: Opening Mock {self.mock_path}")
            self.cap = cv2.VideoCapture(self.mock_path)
        else:
            print("CameraThread: Opening Webcam 0")
            self.cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)  # DirectShow for Windows

            # Configure camera for maximum FPS
            # 1. Use MJPG codec (lower latency than YUV)
            self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))

            # 2. Lower resolution for higher FPS (640x480 typically supports 60fps)
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

            # 3. Set target FPS
            self.cap.set(cv2.CAP_PROP_FPS, self.target_fps)

            # 4. Minimize buffer delay
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

            # Print actual camera settings
            actual_fps = self.cap.get(cv2.CAP_PROP_FPS)
            actual_w = self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)
            actual_h = self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
            print(
                f"Camera configured: {actual_w:.0f}x{actual_h:.0f} @ {actual_fps:.0f} FPS"
            )

    def update_source(self, mock_mode, mock_path):
        with self._source_lock:
            self.mock_mode = mock_mode
            self.mock_path = mock_path
            self._needs_reopen = True

    def stop(self):
        self.running = False
        if self.cap:
            self.cap.release()

    def get_fps(self):
        return self._current_fps

    def run(self):
        while self.running:
            # Check if source needs to be reopened
            with self._source_lock:
                if self._needs_reopen:
                    self._open_camera()
                    self._needs_reopen = False

            if self.cap is None or not self.cap.isOpened():
                time.sleep(0.1)
                continue

            frame_start = time.perf_counter()

            ret, frame = self.cap.read()

            # Handle Looping for Mock Mode
            if not ret and self.mock_mode:
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = self.cap.read()

            if ret and frame is not None:
                # Write directly to buffer (no copy)
                self.frame_buffer.write(frame)

                # FPS calculation
                self._fps_times.append(time.perf_counter())
                if len(self._fps_times) >= 2:
                    elapsed = self._fps_times[-1] - self._fps_times[0]
                    if elapsed > 0:
                        self._current_fps = (len(self._fps_times) - 1) / elapsed

            # FPS limiting - sleep to maintain target framerate
            elapsed = time.perf_counter() - frame_start
            sleep_time = self._frame_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)


class DetectionThread(threading.Thread):
    """Asynchronous detection thread - doesn't block camera capture."""

    def __init__(self, frame_buffer):
        super().__init__()
        self.daemon = True
        self.running = True

        self.frame_buffer = frame_buffer
        self.detector = LemonDetector(
            tuning_mode=False, use_kalman=True, responsive_tracking=True
        )

        self._result_lock = threading.Lock()
        self._latest_frame = None
        self._latest_lemons = []

        # FPS tracking for detection
        self._fps_times = deque(maxlen=30)
        self._current_fps = 0.0

    def stop(self):
        self.running = False

    def get_fps(self):
        return self._current_fps

    def get_latest(self):
        """Get latest detection results."""
        with self._result_lock:
            return self._latest_frame, list(self._latest_lemons)

    def run(self):
        while self.running:
            # Wait for new frame
            if not self.frame_buffer.wait_for_frame(timeout=0.1):
                continue

            frame = self.frame_buffer.read()
            if frame is None:
                continue

            # Make a copy for detection (detection modifies the frame)
            frame_copy = frame.copy()

            # Run detection
            res_frame, lemons = self.detector.detect(frame_copy)

            with self._result_lock:
                self._latest_frame = res_frame
                self._latest_lemons = lemons

            # FPS calculation
            self._fps_times.append(time.perf_counter())
            if len(self._fps_times) >= 2:
                elapsed = self._fps_times[-1] - self._fps_times[0]
                if elapsed > 0:
                    self._current_fps = (len(self._fps_times) - 1) / elapsed
