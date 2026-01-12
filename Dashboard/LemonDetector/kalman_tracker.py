"""
Kalman filter tracker for smooth lemon position tracking.
Tuned for responsive tracking with minimal lag.
"""

import numpy as np
import cv2


class KalmanTracker:
    """
    Kalman filter for smooth 2D position tracking.

    Uses a constant velocity model with tuning for responsive tracking.
    Lower process noise = smoother but more lag
    Higher process noise = more responsive but noisier
    """

    def __init__(self, initial_pos, responsive=True):
        """
        Initialize Kalman filter tracker.

        Args:
            initial_pos: (x, y) initial position
            responsive: If True, use responsive tuning (less lag, follows quickly)
                       If False, use smooth tuning (more lag, smoother trajectory)
        """
        # 4 state variables: x, y, vx, vy
        # 2 measurements: x, y
        self.kf = cv2.KalmanFilter(4, 2)

        # State transition matrix (constant velocity model)
        # [x]   [1 0 dt 0 ] [x]
        # [y] = [0 1 0  dt] [y]
        # [vx]  [0 0 1  0 ] [vx]
        # [vy]  [0 0 0  1 ] [vy]
        dt = 1.0  # Time step (normalized, actual dt handled by frame rate)
        self.kf.transitionMatrix = np.array(
            [[1, 0, dt, 0], [0, 1, 0, dt], [0, 0, 1, 0], [0, 0, 0, 1]], dtype=np.float32
        )

        # Measurement matrix (we only measure x, y)
        self.kf.measurementMatrix = np.array(
            [[1, 0, 0, 0], [0, 1, 0, 0]], dtype=np.float32
        )

        # Tuning based on responsiveness preference
        if responsive:
            # Responsive but stable: balanced for tracking during camera jitter
            # Medium process noise - allows tracking but filters jitter
            process_noise = 0.5  # Reduced from 1.0 - more stable during jitter
            measurement_noise = 1.0  # Increased from 0.5 - filters out jitter noise
        else:
            # Smooth: Lower process noise, higher measurement noise
            # Trusts model more, smoother but laggier
            process_noise = 0.01
            measurement_noise = 5.0

        # Process noise covariance (Q)
        # Higher values = filter adapts faster to changes
        self.kf.processNoiseCov = np.array(
            [
                [process_noise, 0, 0, 0],
                [0, process_noise, 0, 0],
                [0, 0, process_noise * 2, 0],  # Velocity can change faster
                [0, 0, 0, process_noise * 2],
            ],
            dtype=np.float32,
        )

        # Measurement noise covariance (R)
        # Lower values = filter trusts measurements more
        self.kf.measurementNoiseCov = np.array(
            [[measurement_noise, 0], [0, measurement_noise]], dtype=np.float32
        )

        # Error covariance matrix (P) - initial uncertainty
        self.kf.errorCovPost = np.eye(4, dtype=np.float32) * 1.0

        # Initialize state
        x, y = initial_pos
        self.kf.statePost = np.array(
            [
                [np.float32(x)],
                [np.float32(y)],
                [np.float32(0)],  # Initial velocity = 0
                [np.float32(0)],
            ],
            dtype=np.float32,
        )

        # Track frames since last measurement
        self.frames_without_measurement = 0
        self.max_prediction_frames = (
            60  # Increased: predict longer during jitter (2 sec at 30fps)
        )

    def predict(self):
        """
        Predict next position based on model.
        Call this every frame, even without measurement.

        Returns:
            (x, y) predicted position
        """
        prediction = self.kf.predict()
        self.frames_without_measurement += 1
        return (int(prediction[0][0]), int(prediction[1][0]))

    def update(self, measurement):
        """
        Update filter with new measurement.

        Args:
            measurement: (x, y) measured position
        """
        self.kf.correct(
            np.array(
                [[np.float32(measurement[0])], [np.float32(measurement[1])]],
                dtype=np.float32,
            )
        )
        self.frames_without_measurement = 0

    def get_position(self):
        """
        Get current filtered position.

        Returns:
            (x, y) smoothed position
        """
        state = self.kf.statePost
        return (int(state[0][0]), int(state[1][0]))

    def get_velocity(self):
        """
        Get current velocity estimate.

        Returns:
            (vx, vy) velocity in pixels per frame
        """
        state = self.kf.statePost
        return (float(state[2][0]), float(state[3][0]))

    def is_prediction_valid(self):
        """
        Check if prediction is still valid (not too many frames without measurement).

        Returns:
            True if prediction can be trusted
        """
        return self.frames_without_measurement < self.max_prediction_frames

    def get_predicted_position(self, frames_ahead=5):
        """
        Get predicted future position.

        Args:
            frames_ahead: Number of frames to predict ahead

        Returns:
            (x, y) predicted future position
        """
        state = self.kf.statePost
        x = state[0][0] + state[2][0] * frames_ahead
        y = state[1][0] + state[3][0] * frames_ahead
        return (int(x), int(y))


class MultiObjectKalmanTracker:
    """
    Manages multiple Kalman trackers for multiple objects.
    Integrates with the existing LemonDetector tracking system.
    """

    def __init__(self, responsive=True):
        self.trackers = {}  # object_id -> KalmanTracker
        self.responsive = responsive

    def register(self, object_id, position):
        """Register a new object to track."""
        self.trackers[object_id] = KalmanTracker(position, self.responsive)

    def deregister(self, object_id):
        """Remove an object from tracking."""
        if object_id in self.trackers:
            del self.trackers[object_id]

    def update(self, object_id, position):
        """Update tracker with new measurement (predict + correct cycle)."""
        if object_id in self.trackers:
            # Only correct, prediction already done during matching phase
            self.trackers[object_id].update(position)

    def predict(self, object_id):
        """Predict position without measurement."""
        if object_id in self.trackers:
            return self.trackers[object_id].predict()
        return None

    def get_smoothed_position(self, object_id):
        """Get the Kalman-filtered position for an object."""
        if object_id in self.trackers:
            return self.trackers[object_id].get_position()
        return None

    def get_velocity(self, object_id):
        """Get velocity estimate for an object."""
        if object_id in self.trackers:
            return self.trackers[object_id].get_velocity()
        return (0, 0)

    def is_valid(self, object_id):
        """Check if tracker prediction is still valid."""
        if object_id in self.trackers:
            return self.trackers[object_id].is_prediction_valid()
        return False
