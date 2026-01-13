"""
Harvesting state machine for automated lemon harvesting.
Supports multi-axis simultaneous movement for smooth tracking.
"""

import time
from enum import Enum, auto


class HarvestState(Enum):
    IDLE = auto()
    APPROACHING = auto()
    CUTTING = auto()
    DEPOSITING = auto()
    RETURNING = auto()


class HarvestingStateMachine:
    """State machine for automated lemon harvesting sequence with multi-axis control."""

    def __init__(self, app):
        self.app = app
        self.state = HarvestState.IDLE
        self.target_id = None
        self._auto_mode = False

        # Configurable parameters - tuned for responsive tracking
        self.area_threshold = 23000  # area (pixels^2) to trigger cutting
        self.approach_threshold = (
            25  # pixels from center to align (reduced for precision)
        )
        self.visual_servo_gain = (
            0.10  # mm per pixel error (increased for faster response)
        )
        self.forward_speed = 20.0  # mm per step forward (increased)
        self.max_correction = 15.0  # max mm per correction (increased)

        # Speed settings - separate for smooth tracking vs fast operations
        # X/Z correction: slow to avoid jittering/shaking
        self.approach_speed = 30  # mm/s (slow for X/Z tracking)
        self.approach_accel = 30  # mm/s^2 (gentle acceleration)

        # Forward Y: faster but still smooth (no jitter)
        self.forward_approach_speed = 80  # mm/s (faster forward movement)
        self.forward_approach_accel = 100  # mm/s^2 (smooth acceleration)

        # Fast operations: depositing, returning, cutting movements
        # From StepperController.h: MAX_SPEED_MM_S = 500.0, MAX_ACCEL_MM_S2 = 6000.0
        self.fast_speed = 200  # mm/s (fast for non-tracking moves)
        self.fast_accel = 200  # mm/s^2 (quick acceleration)

        # Center offset - adjust target point relative to camera center (pixels)
        self.center_offset_x = 0  # positive = right
        self.center_offset_y = 0  # positive = down

        # Cutter is 50mm below camera - move Z UP to cut
        self.cutting_z_offset = 55  # mm (positive = up)
        self.cutting_y_offset = 55  # mm (positive = forward)

        # Axis lengths (mm) - configure to match your machine
        self.axis_length_x = 130  # X axis total travel
        self.axis_length_y = 230  # Y axis total travel
        self.axis_length_z = 130  # Z axis total travel

        # Predefined positions - calculated from axis lengths
        self.home_pos = (self.axis_length_x / 2, 0, 60)
        self.basket_pos = (self.axis_length_x / 2, 80, 60)

        # Cutting parameters
        self.cut_angle = 60
        self.drop_angle = 60

        # State tracking - PER AXIS busy tracking for simultaneous control
        self._step = 0
        self._axis_busy = [False, False, False]  # X, Y, Z busy flags
        self._waiting_for_action = False  # For cut/drop operations
        self._current_pos = [0, 0, 0]
        self._position_known = False  # True only after position sync from firmware

        # Smooth tracking parameters
        self._frames_lost = 0
        self._max_frames_lost = (
            90  # 3 seconds at 30fps before abort (increased for jitter tolerance)
        )

        # Last known target position (for tracking during jitter)
        self._last_target_pos = None  # (cX, cY)
        self._last_target_area = 0

        # Auto-harvest mode
        self._auto_mode = False
        self._auto_target_count = 3  # Number of lemons to harvest in auto mode
        self._auto_harvested = 0  # Number of lemons harvested so far
        self._auto_delay_frames = 0  # Delay between harvests for target re-acquisition

    def update_axis_limits(self, x_max, y_max, z_max):
        """Update axis limits and recalculate dependent positions."""
        self.axis_length_x = x_max
        self.axis_length_y = y_max
        self.axis_length_z = z_max
        # Recalculate positions that depend on axis limits
        # Keep Y and Z from current values, only update X center
        self.home_pos = (x_max / 2, self.home_pos[1], self.home_pos[2])
        self.basket_pos = (x_max / 2, self.basket_pos[1], self.basket_pos[2])

    def sync_position(self, x, y, z):
        """Sync position from firmware - marks position as known."""
        self._current_pos = [x, y, z]
        self._position_known = True

    def invalidate_position(self):
        """Mark position as unknown (after release, e-stop, etc)."""
        self._position_known = False

    def is_position_known(self):
        """Check if position is known/valid."""
        return self._position_known

    def query_position(self):
        """Query position from firmware. Response handled by sync_position()."""
        self.app.send_command("?")

    def ensure_position_known(self):
        """
        Auto-query position if unknown.
        Returns True if position is known, False if query was sent (wait for response).
        """
        if self._position_known:
            return True
        self.app.log_message("Position unknown - querying firmware...")
        self.query_position()
        return False

    def reset_position(self):
        """Reset position to zero - called after firmware reset."""
        self._current_pos = [0, 0, 0]
        self._position_known = True

    def move_to_home(self):
        """
        Move to home position using proper _send_move with limits.
        Returns True if moves were sent, False if already at home or busy.
        Auto-queries position if unknown.
        """
        if not self._position_known:
            self.app.log_message("Position unknown - querying before home move...")
            self.query_position()
            return False

        moved = False
        dx = self.home_pos[0] - self._current_pos[0]
        dy = self.home_pos[1] - self._current_pos[1]
        dz = self.home_pos[2] - self._current_pos[2]

        if abs(dx) > 0.5:
            self._send_move(0, dx)
            moved = True
        if abs(dy) > 0.5:
            self._send_move(1, dy)
            moved = True
        if abs(dz) > 0.5:
            self._send_move(2, dz)
            moved = True

        return moved

    def start(self, target_id):
        """Start harvesting sequence on the specified target."""
        if self.state != HarvestState.IDLE:
            self.app.log_message("Harvest already in progress!")
            return False

        if not self._position_known:
            self.app.log_message(
                "Position unknown - querying. Try again after position sync."
            )
            self.query_position()
            return False

        self.target_id = target_id
        self.state = HarvestState.APPROACHING
        self._step = 0
        self._frames_lost = 0
        self._last_target_pos = None  # Reset last known position
        self._last_target_area = 0
        self._reset_axis_busy()
        self.app.log_message(f"Starting harvest on target ID: {target_id}")
        return True

    def start_auto(self, target_count=3):
        """Start auto-harvest mode to consecutively harvest multiple lemons."""
        if self.state != HarvestState.IDLE:
            self.app.log_message("Harvest already in progress!")
            return False

        if not self._position_known:
            self.app.log_message(
                "Position unknown - querying. Try again after position sync."
            )
            self.query_position()
            return False

        self._auto_mode = True
        self._auto_target_count = target_count
        self._auto_harvested = 0
        self._auto_delay_frames = 0

        self.app.log_message(f"=== AUTO HARVEST MODE: {target_count} lemons ===")
        self._start_next_auto_target()

    def _start_next_auto_target(self):
        """Find and start harvesting the best available target."""
        # Find best target (closest to center = first in sorted list)
        best_target = self._find_best_target()

        if best_target is None:
            self.app.log_message("No targets available! Waiting...")
            self._auto_delay_frames = 30  # Wait 1 second before retry
            return False

        target_id = best_target.get("id")
        self.app.log_message(
            f"Auto-targeting lemon ID {target_id} ({self._auto_harvested + 1}/{self._auto_target_count})"
        )

        # Start harvest on this target
        self.target_id = target_id
        self.state = HarvestState.APPROACHING
        self._step = 0
        self._frames_lost = 0
        self._last_target_pos = None
        self._last_target_area = 0
        self._reset_axis_busy()

        # Update UI selection
        self.app.selected_lemon_id = target_id

        return True

    def _find_best_target(self):
        """Find the best target to harvest (closest to center)."""
        lemons = self.app.detected_lemons
        if not lemons:
            return None
        # Already sorted by distance to center, first is best
        return lemons[0]

    def abort(self):
        """Abort current harvesting sequence and cancel auto mode."""
        if self.state != HarvestState.IDLE:
            self.app.log_message("Harvest ABORTED")
            self._auto_mode = False  # Cancel auto mode
            self._auto_harvested = 0
            self.state = HarvestState.RETURNING
            self._step = 0
            self._reset_axis_busy()

    def _reset_axis_busy(self):
        """Reset all axis busy flags."""
        self._axis_busy = [False, False, False]
        self._waiting_for_action = False

    def get_state_name(self):
        return self.state.name

    def _is_any_axis_busy(self):
        """Check if any axis is currently moving."""
        return any(self._axis_busy)

    def _is_all_axes_idle(self):
        """Check if all axes are idle."""
        return not any(self._axis_busy) and not self._waiting_for_action

    def update(self):
        """Called every UI frame to process state machine. Returns True if active."""
        # Handle auto-mode delay (waiting for target re-acquisition)
        if self._auto_mode and self.state == HarvestState.IDLE:
            if self._auto_delay_frames > 0:
                self._auto_delay_frames -= 1
                return True  # Still active, waiting
            elif self._auto_harvested < self._auto_target_count:
                # Try to start next target
                self._start_next_auto_target()
                return True

        if self.state == HarvestState.IDLE:
            return False

        if self.state == HarvestState.APPROACHING:
            self._do_approaching()
        elif self.state == HarvestState.CUTTING:
            self._do_cutting()
        elif self.state == HarvestState.DEPOSITING:
            self._do_depositing()
        elif self.state == HarvestState.RETURNING:
            self._do_returning()
        return True

    def _send_move(self, axis, distance_mm, speed=None, accel=None):
        """
        Send move command to firmware.

        Args:
            axis: 0=X, 1=Y, 2=Z
            distance_mm: Distance to move
            speed: Speed in mm/s (defaults to fast_speed)
            accel: Acceleration in mm/s^2 (defaults to fast_accel)
        """
        # Skip if axis already busy
        if self._axis_busy[axis]:
            return False

        # Skip tiny moves
        if abs(distance_mm) < 0.5:
            return False

        # Get axis limit for clamping
        axis_limits = [self.axis_length_x, self.axis_length_y, self.axis_length_z]
        axis_limit = axis_limits[axis]

        # Calculate new position and clamp to [0, axis_limit]
        current = self._current_pos[axis]
        new_pos = current + distance_mm
        clamped_pos = max(0, min(axis_limit, new_pos))

        # Calculate actual distance after clamping
        actual_distance = clamped_pos - current

        # Skip if clamped distance is too small
        if abs(actual_distance) < 0.5:
            return False

        # Default to fast speed/accel
        if speed is None:
            speed = self.fast_speed
        if accel is None:
            accel = self.fast_accel

        # Invert X axis (axis 0) because camera X positive is on frame left
        send_dist = -actual_distance if axis == 0 else actual_distance

        cmd = f"M {axis} {send_dist:.2f} {speed} {accel}"
        self.app.send_command(cmd)

        # Update position tracking with clamped distance
        self._current_pos[axis] = clamped_pos

        # Mark axis as busy
        self._axis_busy[axis] = True

        return True

    def _send_move_xyz(self, dx, dy, dz):
        """Send simultaneous moves on multiple axes."""
        if abs(dx) > 0.5 and not self._axis_busy[0]:
            self._send_move(0, dx)
        if abs(dy) > 0.5 and not self._axis_busy[1]:
            self._send_move(1, dy)
        if abs(dz) > 0.5 and not self._axis_busy[2]:
            self._send_move(2, dz)

    def on_move_done(self, axis):
        """Called when firmware reports move completion."""
        if axis >= 0 and axis < 3:
            self._axis_busy[axis] = False
        elif axis == -1:  # Cut/drop complete
            self._waiting_for_action = False

    def _send_cut(self):
        """Send cut command."""
        cmd = f"C {self.cut_angle}"
        self.app.send_command(cmd)
        self._waiting_for_action = True

    def _send_drop(self):
        """Send drop command."""
        cmd = f"D {self.drop_angle}"
        self.app.send_command(cmd)
        self._waiting_for_action = True

    def _find_target(self):
        """Find target lemon in current detections."""
        for lemon in self.app.detected_lemons:
            if lemon.get("id") == self.target_id:
                return lemon
        return None

    def _do_approaching(self):
        """
        Visual servo approach with SIMULTANEOUS multi-axis movement.
        Moves X, Y, Z at the same time for smooth tracking.
        Uses last known position when target temporarily lost (jitter tolerance).
        """
        target = self._find_target()

        if target is None:
            # Lost target - use last known position if available
            self._frames_lost += 1

            if self._last_target_pos is not None and self._frames_lost <= 30:
                # Use last known position for up to 1 second (30 frames)
                # Continue moving forward slowly, don't correct X/Z
                if not self._axis_busy[1]:
                    self._send_move(
                        1, 2.0, self.approach_speed, self.approach_accel
                    )  # Small forward step
                return

            if self._frames_lost > self._max_frames_lost:
                self.app.log_message("Target lost! Aborting.")
                self.abort()
            return

        self._frames_lost = 0  # Reset lost counter

        # Get target info - use smoothed position if available
        target_area = target.get("area", 0)

        # Calculate alignment errors (center-based: 0 = center)
        # Use smoothed coordinates if available for Kalman-filtered tracking
        cx = target.get("smoothed_cX", target.get("cX", 0))
        cy = target.get("smoothed_cY", target.get("cY", 0))

        # Store last known position for jitter recovery
        self._last_target_pos = (cx, cy)
        self._last_target_area = target_area

        # Get frame dimensions from detection (default to 640x480)
        frame_width = target.get("frame_width", 640)
        frame_height = target.get("frame_height", 480)
        center_x, center_y = frame_width // 2, frame_height // 2
        error_x = center_x - cx + self.center_offset_x
        error_z = center_y - cy + self.center_offset_y  # Camera Y is robot Z

        # Check if close enough (area threshold reached)
        if target_area > self.area_threshold:
            # Close enough - check alignment
            if (
                abs(error_x) < self.approach_threshold
                and abs(error_z) < self.approach_threshold
            ):
                self.app.log_message(
                    f"Area {target_area} > {self.area_threshold}, aligned. Starting cut!"
                )
                self.state = HarvestState.CUTTING
                self._step = 0
                # self._reset_axis_busy()
                return

        # Calculate correction moves with proportional control
        move_x = error_x * self.visual_servo_gain
        move_z = error_z * self.visual_servo_gain

        # Clamp to max correction
        move_x = max(-self.max_correction, min(self.max_correction, move_x))
        move_z = max(-self.max_correction, min(self.max_correction, move_z))

        # Dynamic forward DISTANCE: large steps when far, small steps when close
        # Based on area ratio (0 = far, 1 = at threshold)
        if target_area < self.area_threshold:
            area_ratio = target_area / self.area_threshold  # 0.0 to 1.0
            # Distance scales from forward_speed (far) down to min_step (close)
            min_step = 2.0  # mm minimum step when very close for precision
            move_y = self.forward_speed - (self.forward_speed - min_step) * area_ratio
        else:
            move_y = 0

        # Send SIMULTANEOUS moves on all axes that need correction
        # Use SLOW speed for smooth tracking without jitter
        if abs(error_x) > self.approach_threshold / 2 and not self._axis_busy[0]:
            self._send_move(0, move_x, self.approach_speed, self.approach_accel)

        if abs(error_z) > self.approach_threshold / 2 and not self._axis_busy[2]:
            self._send_move(2, move_z, self.approach_speed, self.approach_accel)

        # Forward Y uses dynamic distance (large when far, small when close)
        # Uses faster speed for forward movement while keeping it smooth
        if move_y > 0 and not self._axis_busy[1]:
            self._send_move(
                1, move_y, self.forward_approach_speed, self.forward_approach_accel
            )

    def _do_cutting(self):
        """Execute cutting sequence - waits for each move to complete before next step."""
        # Wait for any pending action or axis movement
        if self._waiting_for_action or self._is_any_axis_busy():
            return

        if self._step == 0:
            # Step 0: Move Z up
            self.app.log_message("Cutting: Moving Z up...")
            self._send_move(2, self.cutting_z_offset)
            self._step = 1
        elif self._step == 1:
            # Step 1: Z move complete, now move Y forward
            self.app.log_message("Cutting: Moving Y forward...")
            self._send_move(
                1, self.cutting_y_offset, self.approach_speed, self.approach_accel
            )
            self._step = 2
        elif self._step == 2:
            # Step 2: Y move complete, now cut
            self.app.log_message("Cutting: Activating cutter...")
            self._send_cut()
            self._step = 3
        elif self._step == 3:
            # Step 3: Cut complete, retract Y
            self.app.log_message("Cutting: Retracting Y...")
            self._send_move(1, -self.cutting_y_offset)
            self._step = 4
        elif self._step == 4:
            # Step 4: Y retracted, move Z down
            self.app.log_message("Cutting: Moving Z down...")
            self._send_move(2, self.basket_pos[2] - self._current_pos[2])
            self._step = 5
        elif self._step == 5:
            # Step 5: All moves complete, transition to depositing
            self.app.log_message("Cut complete! Moving to basket.")
            self.state = HarvestState.DEPOSITING
            self._step = 0
            self._reset_axis_busy()

    def _do_depositing(self):
        """Move to basket and drop - uses simultaneous movement."""
        if self._waiting_for_action:
            return

        if self._step == 0:
            # Move X and Y simultaneously to basket
            dx = self.basket_pos[0] - self._current_pos[0]
            dy = self.basket_pos[1] - self._current_pos[1]
            dz = self.basket_pos[2] - self._current_pos[2]

            moved = False
            if abs(dx) > 0.5 and not self._axis_busy[0]:
                self.app.log_message("Depositing: Moving X to basket...")
                self._send_move(0, dx)
                moved = True
            if abs(dy) > 0.5 and not self._axis_busy[1]:
                self.app.log_message("Depositing: Moving Y to basket...")
                self._send_move(1, dy)
                moved = True
            if abs(dz) > 0.5 and not self._axis_busy[2]:
                self.app.log_message("Depositing: Moving Z to basket...")
                self._send_move(2, dz)
                moved = True

            if not moved or self._is_all_axes_idle():
                self._step = 1
        elif self._step == 1:
            if self._is_all_axes_idle():
                self.app.log_message("Dropping lemon...")
                self._send_drop()
                self._step = 2
        elif self._step == 2:
            self.app.log_message("Lemon deposited! Returning home.")
            self.state = HarvestState.RETURNING
            self._step = 0
            self._reset_axis_busy()

    def _do_returning(self):
        """Return to home position - uses simultaneous movement."""
        if self._step == 0:
            # Move all axes simultaneously to home
            dx = self.home_pos[0] - self._current_pos[0]
            dy = self.home_pos[1] - self._current_pos[1]
            dz = self.home_pos[2] - self._current_pos[2]

            moved = False
            if abs(dx) > 0.5 and not self._axis_busy[0]:
                self.app.log_message("Returning: Moving X to home...")
                self._send_move(0, dx)
                moved = True
            if abs(dy) > 0.5 and not self._axis_busy[1]:
                self.app.log_message("Returning: Moving Y to home...")
                self._send_move(1, dy)
                moved = True
            if abs(dz) > 0.5 and not self._axis_busy[2]:
                self.app.log_message("Returning: Moving Z to home...")
                self._send_move(2, dz)
                moved = True

            if not moved:
                self._step = 1
        elif self._step == 1:
            if self._is_all_axes_idle():
                # Position is already tracked by _send_move - no need to override
                # Just verify we're close to home (within tolerance)
                dx = abs(self.home_pos[0] - self._current_pos[0])
                dy = abs(self.home_pos[1] - self._current_pos[1])
                dz = abs(self.home_pos[2] - self._current_pos[2])
                if dx > 1 or dy > 1 or dz > 1:
                    self.app.log_message(
                        f"Warning: Not at home pos (delta: X={dx:.1f}, Y={dy:.1f}, Z={dz:.1f})"
                    )

                # Check if auto mode - continue to next target
                if self._auto_mode:
                    self._auto_harvested += 1
                    if self._auto_harvested >= self._auto_target_count:
                        self.app.log_message(
                            f"=== AUTO HARVEST COMPLETE: {self._auto_harvested} lemons ==="
                        )
                        self._auto_mode = False
                        self.state = HarvestState.IDLE
                        self.target_id = None
                    else:
                        self.app.log_message(
                            f"Harvest {self._auto_harvested}/{self._auto_target_count} complete! Finding next target..."
                        )
                        self.state = HarvestState.IDLE
                        self.target_id = None
                        self._auto_delay_frames = (
                            30  # Wait 1 second for detection to stabilize
                        )
                else:
                    self.app.log_message("Harvest sequence complete!")
                    self.state = HarvestState.IDLE
                    self.target_id = None

    def get_auto_status(self):
        """Get auto-harvest status string."""
        if self._auto_mode:
            return f"AUTO {self._auto_harvested}/{self._auto_target_count}"
        return None
