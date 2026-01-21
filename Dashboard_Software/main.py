"""
Motor Controller Dashboard - Main Application
"""

import customtkinter as ctk
import cv2
import serial
import serial.tools.list_ports
import threading
import time

from camera import CameraThread, DetectionThread
from harvester import HarvestState, HarvestingStateMachine
from embedded_cv_display import EmbeddedCVDisplay


class DashboardApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Motor Controller Dashboard")
        self.geometry("1200x800")

        # Fullscreen
        self.after(0, lambda: self.state("zoomed"))
        self.bind("<Escape>", lambda e: self.destroy())

        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        # Serial Connection
        self.serial_port = None
        self.is_connected = False

        # Camera and Detection Threads (decoupled)
        self.camera_thread = CameraThread(
            mock_mode=False, mock_path="mock_lemon.mp4", target_fps=30
        )
        self.detection_thread = DetectionThread(self.camera_thread.frame_buffer)

        self.camera_thread.start()
        self.detection_thread.start()

        self.selected_lemon_id = None
        self.detected_lemons = []
        self.lemon_buttons = {}

        # Harvesting State Machine
        self.harvester = HarvestingStateMachine(self)

        # Layout Configuration
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)
        self.grid_rowconfigure(0, weight=1)

        # Left Frame: Camera (container for embedded OpenCV window)
        self.camera_frame = ctk.CTkFrame(self)
        self.camera_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        # Embedded OpenCV display (native performance)
        self.cv_display = EmbeddedCVDisplay(self.camera_frame, "Camera Feed")

        # Right Frame: Controls
        self.controls_frame = ctk.CTkScrollableFrame(self, width=400)
        self.controls_frame.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")

        self.setup_controls()

        # Polling Thread
        self.polling = False
        self.poll_thread = None

        # Start UI Update Loop (delay to ensure window is realized)
        self.after(500, self.update_camera_ui)

    def setup_controls(self):
        # Connection Section
        self.conn_frame = ctk.CTkFrame(self.controls_frame)
        self.conn_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(
            self.conn_frame, text="Serial Connection", font=("Arial", 16, "bold")
        ).pack(pady=5)

        self.port_combo = ctk.CTkComboBox(
            self.conn_frame, values=self.get_serial_ports()
        )
        self.port_combo.pack(pady=5)

        self.connect_btn = ctk.CTkButton(
            self.conn_frame, text="Connect", command=self.toggle_connection
        )
        self.connect_btn.pack(pady=5)

        # Detected Lemons Section (compact)
        self.lemon_frame = ctk.CTkFrame(self.controls_frame)
        self.lemon_frame.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(
            self.lemon_frame, text="Detected Lemons", font=("Arial", 14, "bold")
        ).pack(pady=3)

        self.lemon_list_container = ctk.CTkScrollableFrame(self.lemon_frame, height=100)
        self.lemon_list_container.pack(fill="x", padx=5, pady=3)

        # ========== HARVESTING CONTROL SECTION ==========
        self.harvest_frame = ctk.CTkFrame(self.controls_frame)
        self.harvest_frame.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(
            self.harvest_frame, text="Harvesting Control", font=("Arial", 14, "bold")
        ).pack(pady=3)

        # Status display
        self.harvest_status_label = ctk.CTkLabel(
            self.harvest_frame,
            text="Status: IDLE",
            font=("Arial", 12),
            text_color="#00FF00",
        )
        self.harvest_status_label.pack(pady=3)

        # Center offset controls (compact row)
        offset_frame = ctk.CTkFrame(self.harvest_frame, fg_color="transparent")
        offset_frame.pack(fill="x", padx=5, pady=2)

        ctk.CTkLabel(offset_frame, text="Offset X:", width=50).pack(side="left")
        self.offset_x_entry = ctk.CTkEntry(offset_frame, width=50)
        self.offset_x_entry.insert(0, "0")
        self.offset_x_entry.pack(side="left", padx=2)

        ctk.CTkLabel(offset_frame, text="Y:", width=20).pack(side="left")
        self.offset_y_entry = ctk.CTkEntry(offset_frame, width=50)
        self.offset_y_entry.insert(0, "0")
        self.offset_y_entry.pack(side="left", padx=2)

        self.apply_offset_btn = ctk.CTkButton(
            offset_frame, text="Apply", width=50, command=self.apply_offset
        )
        self.apply_offset_btn.pack(side="left", padx=5)

        # Harvest buttons row
        harvest_btn_row = ctk.CTkFrame(self.harvest_frame, fg_color="transparent")
        harvest_btn_row.pack(fill="x", padx=5, pady=3)

        self.start_harvest_btn = ctk.CTkButton(
            harvest_btn_row,
            text="▶ HARVEST",
            fg_color="#228B22",
            hover_color="#006400",
            height=35,
            font=("Arial", 12, "bold"),
            command=self.start_harvest,
        )
        self.start_harvest_btn.pack(side="left", expand=True, fill="x", padx=2)

        self.auto_harvest_btn = ctk.CTkButton(
            harvest_btn_row,
            text="▶▶ AUTO (3)",
            fg_color="#1E90FF",
            hover_color="#0066CC",
            height=35,
            font=("Arial", 12, "bold"),
            command=self.start_auto_harvest,
        )
        self.auto_harvest_btn.pack(side="left", expand=True, fill="x", padx=2)

        self.abort_harvest_btn = ctk.CTkButton(
            harvest_btn_row,
            text="⏹ ABORT",
            fg_color="#8B0000",
            hover_color="#B22222",
            height=35,
            font=("Arial", 12, "bold"),
            command=self.abort_harvest,
        )
        self.abort_harvest_btn.pack(side="left", expand=True, fill="x", padx=2)

        # Motor Control Section
        self.motor_frame = ctk.CTkFrame(self.controls_frame)
        self.motor_frame.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(
            self.motor_frame, text="Stepper Control", font=("Arial", 14, "bold")
        ).pack(pady=3)

        # Axis Selection - horizontal
        axis_row = ctk.CTkFrame(self.motor_frame, fg_color="transparent")
        axis_row.pack(fill="x", padx=5, pady=5)
        self.axis_var = ctk.StringVar(value="0")
        ctk.CTkRadioButton(
            axis_row, text="X", variable=self.axis_var, value="0", width=50
        ).pack(side="left", expand=True)
        ctk.CTkRadioButton(
            axis_row, text="Y", variable=self.axis_var, value="1", width=50
        ).pack(side="left", expand=True)
        ctk.CTkRadioButton(
            axis_row, text="Z", variable=self.axis_var, value="2", width=50
        ).pack(side="left", expand=True)

        # Parameters
        self.dist_entry = self.create_labeled_entry(
            self.motor_frame, "Distance (mm):", "10"
        )
        self.speed_entry = self.create_labeled_entry(
            self.motor_frame, "Speed (mm/s):", "50"
        )
        self.accel_entry = self.create_labeled_entry(
            self.motor_frame, "Accel (mm/s²):", "100"
        )

        # Move Buttons Row
        move_row = ctk.CTkFrame(self.motor_frame, fg_color="transparent")
        move_row.pack(fill="x", padx=5, pady=5)

        self.move_btn = ctk.CTkButton(
            move_row, text="Move", width=55, command=self.send_move_command
        )
        self.move_btn.pack(side="left", padx=2, expand=True)

        self.center_btn = ctk.CTkButton(
            move_row,
            text="Center",
            width=55,
            fg_color="#228B22",
            command=self.send_home_command,
        )
        self.center_btn.pack(side="left", padx=2, expand=True)

        self.query_btn = ctk.CTkButton(
            move_row, text="Status", width=55, command=self.send_query_command
        )
        self.query_btn.pack(side="left", padx=2, expand=True)

        # Utility Buttons Row
        util_row = ctk.CTkFrame(self.motor_frame, fg_color="transparent")
        util_row.pack(fill="x", padx=5, pady=5)

        self.zero_btn = ctk.CTkButton(
            util_row, text="Set Zero", width=60, command=self.send_reset_command
        )
        self.zero_btn.pack(side="left", padx=2, expand=True)

        self.unlock_btn = ctk.CTkButton(
            util_row,
            text="Unlock",
            width=55,
            fg_color="#666666",
            command=self.send_release_command,
        )
        self.unlock_btn.pack(side="left", padx=2, expand=True)

        self.config_btn = ctk.CTkButton(
            util_row, text="Config", width=55, command=self.send_config_command
        )
        self.config_btn.pack(side="left", padx=2, expand=True)

        # Stop Button
        self.stop_btn = ctk.CTkButton(
            self.motor_frame,
            text="⚠ EMERGENCY STOP",
            fg_color="red",
            hover_color="darkred",
            height=35,
            command=self.emergency_stop,
        )
        self.stop_btn.pack(pady=5, fill="x", padx=5)

        # Servo / Cutter Control Section (compact)
        self.servo_frame = ctk.CTkFrame(self.controls_frame)
        self.servo_frame.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(
            self.servo_frame, text="Servo / Cutter", font=("Arial", 14, "bold")
        ).pack(pady=3)

        # Combined servo/cut/drop row
        servo_row = ctk.CTkFrame(self.servo_frame, fg_color="transparent")
        servo_row.pack(fill="x", padx=5, pady=2)

        ctk.CTkLabel(servo_row, text="Servo#:", width=45).pack(side="left")
        self.servo_index_entry = ctk.CTkEntry(servo_row, width=35)
        self.servo_index_entry.insert(0, "0")
        self.servo_index_entry.pack(side="left", padx=2)

        ctk.CTkLabel(servo_row, text="Ang:", width=30).pack(side="left")
        self.servo_angle_entry = ctk.CTkEntry(servo_row, width=40)
        self.servo_angle_entry.insert(0, "90")
        self.servo_angle_entry.pack(side="left", padx=2)

        self.servo_btn = ctk.CTkButton(
            servo_row, text="Set", width=40, command=self.set_servo
        )
        self.servo_btn.pack(side="left", padx=3)

        # Cut/Drop row
        cut_drop_row = ctk.CTkFrame(self.servo_frame, fg_color="transparent")
        cut_drop_row.pack(fill="x", padx=5, pady=2)

        ctk.CTkLabel(cut_drop_row, text="Cut:", width=30).pack(side="left")
        self.cut_angle_entry = ctk.CTkEntry(cut_drop_row, width=40)
        self.cut_angle_entry.insert(0, "45")
        self.cut_angle_entry.pack(side="left", padx=2)

        self.cut_btn = ctk.CTkButton(
            cut_drop_row,
            text="Cut",
            width=40,
            fg_color="#8B4513",
            command=self.test_cut,
        )
        self.cut_btn.pack(side="left", padx=3)

        ctk.CTkLabel(cut_drop_row, text="Drop:", width=35).pack(side="left")
        self.drop_angle_entry = ctk.CTkEntry(cut_drop_row, width=40)
        self.drop_angle_entry.insert(0, "45")
        self.drop_angle_entry.pack(side="left", padx=2)

        self.drop_btn = ctk.CTkButton(
            cut_drop_row,
            text="Drop",
            width=40,
            fg_color="#4682B4",
            command=self.test_drop,
        )
        self.drop_btn.pack(side="left", padx=3)

        # Console/Log (compact)
        self.log_box = ctk.CTkTextbox(self.controls_frame, height=100)
        self.log_box.pack(fill="both", expand=True, padx=10, pady=5)
        self.log_message("Dashboard Ready.")

    def create_labeled_entry(self, parent, text, default_val):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", padx=5, pady=2)
        ctk.CTkLabel(frame, text=text, width=100, anchor="w").pack(side="left")
        entry = ctk.CTkEntry(frame)
        entry.insert(0, default_val)
        entry.pack(side="right", expand=True, fill="x")
        return entry

    def get_serial_ports(self):
        ports = [port.device for port in serial.tools.list_ports.comports()]
        return ports if ports else ["No Ports"]

    def toggle_connection(self):
        if not self.is_connected:
            port = self.port_combo.get()
            if port == "No Ports":
                self.log_message("No serial port selected.")
                return
            try:
                self.serial_port = serial.Serial(port, 115200, timeout=1)
                self.is_connected = True
                self.connect_btn.configure(text="Disconnect", fg_color="red")
                self.log_message(f"Connected to {port}")
                self.start_polling()
                # Auto-query config and status after connection
                self.after(500, self._auto_query_on_connect)
            except Exception as e:
                self.log_message(f"Connection Failed: {e}")
        else:
            self.stop_polling()
            if self.serial_port:
                self.serial_port.close()
            self.is_connected = False
            self.connect_btn.configure(text="Connect", fg_color="#1f6aa5")
            self.log_message("Disconnected")

    def _auto_query_on_connect(self):
        """Auto-query config and status after connecting."""
        if self.is_connected:
            self.log_message("Auto-querying config and status...")
            self.send_command("G")  # Get limits/config
            self.after(200, lambda: self.send_command("?"))  # Get position/status

    def update_camera_ui(self):
        # Get detection results
        res_frame, lemons = self.detection_thread.get_latest()

        # Get FPS for overlay (no separate label)
        cam_fps = self.camera_thread.get_fps()
        det_fps = self.detection_thread.get_fps()

        if res_frame is not None:
            self.detected_lemons = lemons

            # Selection Logic
            if not lemons:
                self.selected_lemon_id = None
            else:
                ids = [l["id"] for l in lemons]
                if self.selected_lemon_id not in ids:
                    self.selected_lemon_id = lemons[0]["id"]

            # Highlight Selection
            if self.selected_lemon_id is not None:
                for l in lemons:
                    if l["id"] == self.selected_lemon_id:
                        cv2.circle(res_frame, (l["cX"], l["cY"]), 30, (0, 255, 255), 3)
                        cv2.putText(
                            res_frame,
                            "TARGET",
                            (l["cX"] - 20, l["cY"] - 30),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.6,
                            (0, 255, 255),
                            2,
                        )
                        break

            # Update UI List
            self.update_lemon_list_ui()

            # Draw overlays on original frame (before resize)
            h_img, w_img = res_frame.shape[:2]

            # Draw FPS overlay on frame
            fps_text = f"CAM: {cam_fps:.0f} | DET: {det_fps:.0f}"
            cv2.putText(
                res_frame,
                fps_text,
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2,
            )

            # Draw center crosshair (target alignment guide) at original resolution
            cx = w_img // 2 + self.harvester.center_offset_x
            cy = h_img // 2 + self.harvester.center_offset_y
            crosshair_size = 20
            cv2.line(
                res_frame,
                (cx - crosshair_size, cy),
                (cx + crosshair_size, cy),
                (0, 255, 255),
                2,
            )
            cv2.line(
                res_frame,
                (cx, cy - crosshair_size),
                (cx, cy + crosshair_size),
                (0, 255, 255),
                2,
            )

            # Draw approach threshold circle (when harvesting)
            if self.harvester.state != HarvestState.IDLE:
                cv2.circle(
                    res_frame,
                    (cx, cy),
                    self.harvester.approach_threshold,
                    (0, 255, 255),
                    1,
                )

            # Display using embedded OpenCV window (native performance)
            self.cv_display.update(res_frame)

        # Update Harvesting State Machine
        if self.harvester.update():
            # Update status display
            state_colors = {
                "IDLE": "#00FF00",
                "APPROACHING": "#FFD700",
                "CUTTING": "#FF4500",
                "DEPOSITING": "#1E90FF",
                "RETURNING": "#9370DB",
            }
            state_name = self.harvester.get_state_name()
            # Show auto-harvest progress if active
            auto_status = self.harvester.get_auto_status()
            if auto_status:
                status_text = f"{auto_status} | {state_name}"
            else:
                status_text = f"Status: {state_name}"
            self.harvest_status_label.configure(
                text=status_text,
                text_color=state_colors.get(state_name, "#FFFFFF"),
            )
        else:
            self.harvest_status_label.configure(
                text="Status: IDLE", text_color="#00FF00"
            )

        # Schedule next update (33ms ≈ 30 FPS UI refresh)
        self.after(33, self.update_camera_ui)

    def update_lemon_list_ui(self):
        current_ids = set()

        for lemon in self.detected_lemons:
            l_id = lemon["id"]
            current_ids.add(l_id)
            dist = int(lemon["dist"])

            is_selected = l_id == self.selected_lemon_id
            new_color = "green" if is_selected else "#1f6aa5"
            new_text = f"ID: {l_id} | Dist: {dist}px"

            if l_id in self.lemon_buttons:
                btn, old_text, old_color = self.lemon_buttons[l_id]
                if old_text != new_text or old_color != new_color:
                    btn.configure(text=new_text, fg_color=new_color)
                    self.lemon_buttons[l_id] = (btn, new_text, new_color)
            else:
                btn = ctk.CTkButton(
                    self.lemon_list_container,
                    text=new_text,
                    fg_color=new_color,
                    command=lambda i=l_id: self.select_lemon(i),
                )
                btn.pack(pady=2, fill="x")
                self.lemon_buttons[l_id] = (btn, new_text, new_color)

        for l_id in list(self.lemon_buttons.keys()):
            if l_id not in current_ids:
                btn, _, _ = self.lemon_buttons[l_id]
                btn.destroy()
                del self.lemon_buttons[l_id]

    def select_lemon(self, lemon_id):
        self.selected_lemon_id = lemon_id

    def apply_offset(self):
        """Apply center offset from UI entries."""
        try:
            self.harvester.center_offset_x = int(self.offset_x_entry.get())
            self.harvester.center_offset_y = int(self.offset_y_entry.get())
            self.log_message(
                f"Center offset set to ({self.harvester.center_offset_x}, {self.harvester.center_offset_y})"
            )
        except ValueError:
            self.log_message("Invalid offset values!")

    def start_harvest(self):
        """Start harvesting the selected lemon."""
        if self.selected_lemon_id is None:
            self.log_message("No lemon selected!")
            return
        if not self.is_connected:
            self.log_message("Serial not connected! Connect first.")
            return
        self.harvester.start(self.selected_lemon_id)

    def start_auto_harvest(self):
        """Start auto-harvest mode to consecutively harvest 3 lemons."""
        if not self.is_connected:
            self.log_message("Serial not connected! Connect first.")
            return
        if not self.detected_lemons:
            self.log_message("No lemons detected!")
            return
        self.harvester.start_auto(target_count=3)

    def abort_harvest(self):
        """Abort the current harvesting sequence."""
        # Send emergency stop to firmware
        self.send_command("!")
        self.harvester.abort()

    def log_message(self, msg):
        self.log_box.insert("end", msg + "\n")
        self.log_box.see("end")

    def send_command(self, cmd):
        if self.is_connected and self.serial_port:
            try:
                self.serial_port.write((cmd + "\n").encode())
                self.log_message(f"Sent: {cmd}")
            except Exception as e:
                self.log_message(f"Send Error: {e}")
        else:
            self.log_message("Not Connected")

    def send_move_command(self):
        axis = self.axis_var.get()
        dist = self.dist_entry.get()
        speed = self.speed_entry.get()
        accel = self.accel_entry.get()
        cmd = f"M {axis} {dist} {speed} {accel}"
        self.send_command(cmd)

    def send_home_command(self):
        """Move to home position (X center, Y=0, Z=0)."""
        home = self.harvester.home_pos
        # Move to home position from current position
        self.send_command(f"M 0 {home[0] - self.harvester._current_pos[0]:.2f} 100 200")
        self.send_command(f"M 1 {home[1] - self.harvester._current_pos[1]:.2f} 100 200")
        self.send_command(f"M 2 {home[2] - self.harvester._current_pos[2]:.2f} 100 200")
        self.harvester._current_pos = list(home)
        self.log_message(f"Moving to home: X={home[0]}, Y={home[1]}, Z={home[2]}")

    def send_query_command(self):
        """Query current position and status."""
        self.send_command("?")

    def send_config_command(self):
        """Query configuration (axis limits)."""
        self.send_command("G")

    def send_reset_command(self):
        """Reset position counter to 0,0,0."""
        self.send_command("H")
        self.harvester._current_pos = [0, 0, 0]
        self.log_message("Position reset to 0,0,0")

    def send_release_command(self):
        """Release/disable steppers for manual movement."""
        self.send_command("R")
        self.log_message("Steppers released - manual move OK")

    def emergency_stop(self):
        """Emergency stop all motors."""
        self.send_command("!")
        self.harvester.abort()
        self.log_message("EMERGENCY STOP")

    def set_servo(self):
        """Set servo to specified angle."""
        try:
            index = int(self.servo_index_entry.get())
            angle = int(self.servo_angle_entry.get())
            cmd = f"S {index} {angle}"
            self.send_command(cmd)
        except ValueError:
            self.log_message("Invalid servo values!")

    def test_cut(self):
        """Test cut sequence."""
        try:
            angle = int(self.cut_angle_entry.get())
            cmd = f"C {angle}"
            self.send_command(cmd)
        except ValueError:
            self.log_message("Invalid cut angle!")

    def test_drop(self):
        """Test drop sequence."""
        try:
            angle = int(self.drop_angle_entry.get())
            cmd = f"D {angle}"
            self.send_command(cmd)
        except ValueError:
            self.log_message("Invalid drop angle!")

    def start_polling(self):
        self.polling = True
        self.poll_thread = threading.Thread(target=self.poll_loop, daemon=True)
        self.poll_thread.start()

    def stop_polling(self):
        self.polling = False

    def poll_loop(self):
        while self.polling:
            if self.is_connected and self.serial_port:
                try:
                    if self.serial_port.in_waiting:
                        line = self.serial_port.readline().decode().strip()
                        if line:
                            # Parse response for special handling
                            self.after(0, lambda l=line: self._handle_response(l))
                except Exception as e:
                    print(f"Serial Read Error: {e}")
            time.sleep(0.05)  # Faster polling for better responsiveness

    def _handle_response(self, line):
        """Handle responses from firmware."""
        self.log_message(f"RX: {line}")

        # Parse DONE messages (move complete)
        if line.startswith("DONE"):
            parts = line.split()
            if len(parts) >= 2:
                axis = int(parts[1])
                # Notify harvester that move is complete
                self.harvester.on_move_done(axis)

        # Parse OK C (cut complete) and OK D (drop complete)
        elif line.startswith("OK C") or line.startswith("OK D"):
            self.harvester.on_move_done(-1)  # Clear wait flag

        # Parse POS messages
        elif line.startswith("POS"):
            parts = line.split()
            if len(parts) >= 4:
                try:
                    x = float(parts[1])
                    y = float(parts[2])
                    z = float(parts[3])
                    self.harvester._current_pos = [x, y, z]
                except ValueError:
                    pass

        # Parse LIMITS messages - auto-configure axis lengths
        elif line.startswith("LIMITS"):
            parts = line.split()
            if len(parts) >= 4:
                try:
                    x_max = float(parts[1])
                    y_max = float(parts[2])
                    z_max = float(parts[3])
                    # Use the new method to update limits and recalculate positions
                    self.harvester.update_axis_limits(x_max, y_max, z_max)
                    self.log_message(f"Configured: X={x_max}, Y={y_max}, Z={z_max}")
                except ValueError:
                    pass

    def on_closing(self):
        self.stop_polling()
        self.camera_thread.stop()
        self.detection_thread.stop()
        self.cv_display.destroy()
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
        self.destroy()


if __name__ == "__main__":
    app = DashboardApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
