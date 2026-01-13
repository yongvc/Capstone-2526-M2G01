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
        self.geometry("1366x768")

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

        # Layout Configuration - fixed width right panel
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0, minsize=420)
        self.grid_rowconfigure(0, weight=1)

        # Left Frame: Camera (container for embedded OpenCV window)
        self.camera_frame = ctk.CTkFrame(self)
        self.camera_frame.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")

        # Embedded OpenCV display (native performance)
        self.cv_display = EmbeddedCVDisplay(self.camera_frame, "Camera Feed")

        # Right Frame: Controls (fixed, no scroll)
        self.controls_frame = ctk.CTkFrame(self, width=420)
        self.controls_frame.grid(row=0, column=1, padx=5, pady=5, sticky="nsew")
        self.controls_frame.grid_propagate(False)

        self.setup_controls()

        # Polling Thread
        self.polling = False
        self.poll_thread = None

        # Start UI Update Loop (delay to ensure window is realized)
        self.after(500, self.update_camera_ui)

    def setup_controls(self):
        """Setup control panel with clean, organized layout."""
        # Configure grid - log box expands
        self.controls_frame.grid_columnconfigure(0, weight=1)
        self.controls_frame.grid_rowconfigure(5, weight=1)

        row = 0
        pad_x, pad_y = 8, 4

        # ===== SECTION 1: Connection =====
        conn_section = ctk.CTkFrame(self.controls_frame)
        conn_section.grid(row=row, column=0, padx=pad_x, pady=(pad_y, 2), sticky="ew")
        row += 1

        # Title bar with status
        title_row = ctk.CTkFrame(conn_section, fg_color="transparent")
        title_row.pack(fill="x", padx=5, pady=(5, 2))
        ctk.CTkLabel(
            title_row,
            text="CONNECTION",
            font=("Arial", 11, "bold"),
            text_color="#888888",
        ).pack(side="left")
        self.harvest_status_label = ctk.CTkLabel(
            title_row, text="IDLE", font=("Arial", 11, "bold"), text_color="#00FF00"
        )
        self.harvest_status_label.pack(side="right")

        # Connection controls
        conn_row = ctk.CTkFrame(conn_section, fg_color="transparent")
        conn_row.pack(fill="x", padx=5, pady=(0, 5))

        self.port_combo = ctk.CTkComboBox(
            conn_row, values=self.get_serial_ports(), width=110
        )
        self.port_combo.pack(side="left", padx=(0, 3))

        self.refresh_btn = ctk.CTkButton(
            conn_row, text="↻", width=28, command=self.refresh_ports
        )
        self.refresh_btn.pack(side="left", padx=2)

        self.connect_btn = ctk.CTkButton(
            conn_row, text="Connect", width=65, command=self.toggle_connection
        )
        self.connect_btn.pack(side="left", padx=2)

        self.stop_btn = ctk.CTkButton(
            conn_row,
            text="E-STOP",
            width=55,
            fg_color="#CC0000",
            hover_color="#990000",
            font=("Arial", 11, "bold"),
            command=self.emergency_stop,
        )
        self.stop_btn.pack(side="right")

        # ===== SECTION 2: Detected Lemons =====
        lemon_section = ctk.CTkFrame(self.controls_frame)
        lemon_section.grid(row=row, column=0, padx=pad_x, pady=2, sticky="ew")
        row += 1

        ctk.CTkLabel(
            lemon_section,
            text="TARGETS",
            font=("Arial", 11, "bold"),
            text_color="#888888",
        ).pack(anchor="w", padx=5, pady=(5, 2))

        self.lemon_list_container = ctk.CTkScrollableFrame(lemon_section, height=75)
        self.lemon_list_container.pack(fill="x", padx=5, pady=(0, 5))

        # ===== SECTION 3: Harvest Control =====
        harvest_section = ctk.CTkFrame(self.controls_frame)
        harvest_section.grid(row=row, column=0, padx=pad_x, pady=2, sticky="ew")
        row += 1

        ctk.CTkLabel(
            harvest_section,
            text="HARVEST",
            font=("Arial", 11, "bold"),
            text_color="#888888",
        ).pack(anchor="w", padx=5, pady=(5, 2))

        # Main harvest buttons
        harvest_btns = ctk.CTkFrame(harvest_section, fg_color="transparent")
        harvest_btns.pack(fill="x", padx=5, pady=2)
        harvest_btns.grid_columnconfigure((0, 1, 2), weight=1)

        ctk.CTkButton(
            harvest_btns,
            text="▶ HARVEST",
            height=34,
            fg_color="#228B22",
            hover_color="#1a6b1a",
            font=("Arial", 12, "bold"),
            command=self.start_harvest,
        ).grid(row=0, column=0, padx=2, sticky="ew")

        ctk.CTkButton(
            harvest_btns,
            text="▶▶ AUTO",
            height=34,
            fg_color="#1976D2",
            hover_color="#1565C0",
            font=("Arial", 12, "bold"),
            command=self.start_auto_harvest,
        ).grid(row=0, column=1, padx=2, sticky="ew")

        ctk.CTkButton(
            harvest_btns,
            text="■ ABORT",
            height=34,
            fg_color="#C62828",
            hover_color="#B71C1C",
            font=("Arial", 12, "bold"),
            command=self.abort_harvest,
        ).grid(row=0, column=2, padx=2, sticky="ew")

        # Offset controls (smaller)
        offset_row = ctk.CTkFrame(harvest_section, fg_color="transparent")
        offset_row.pack(fill="x", padx=5, pady=(2, 5))

        ctk.CTkLabel(offset_row, text="Offset:", width=45, anchor="w").pack(side="left")
        ctk.CTkLabel(offset_row, text="X", width=12).pack(side="left")
        self.offset_x_entry = ctk.CTkEntry(offset_row, width=40)
        self.offset_x_entry.insert(0, "0")
        self.offset_x_entry.pack(side="left", padx=2)
        ctk.CTkLabel(offset_row, text="Y", width=12).pack(side="left")
        self.offset_y_entry = ctk.CTkEntry(offset_row, width=40)
        self.offset_y_entry.insert(0, "0")
        self.offset_y_entry.pack(side="left", padx=2)
        ctk.CTkButton(
            offset_row, text="Set", width=35, height=24, command=self.apply_offset
        ).pack(side="left", padx=5)

        # ===== SECTION 4: Motor Control =====
        motor_section = ctk.CTkFrame(self.controls_frame)
        motor_section.grid(row=row, column=0, padx=pad_x, pady=2, sticky="ew")
        row += 1

        ctk.CTkLabel(
            motor_section,
            text="MOTOR CONTROL",
            font=("Arial", 11, "bold"),
            text_color="#888888",
        ).pack(anchor="w", padx=5, pady=(5, 2))

        # Row 1: Axis selection + Move
        motor_row1 = ctk.CTkFrame(motor_section, fg_color="transparent")
        motor_row1.pack(fill="x", padx=5, pady=2)

        self.axis_var = ctk.StringVar(value="0")
        for axis, label in [("0", "X"), ("1", "Y"), ("2", "Z")]:
            ctk.CTkRadioButton(
                motor_row1, text=label, variable=self.axis_var, value=axis, width=45
            ).pack(side="left")

        ctk.CTkLabel(motor_row1, text="mm:", width=28).pack(side="left", padx=(8, 0))
        self.dist_entry = ctk.CTkEntry(motor_row1, width=50)
        self.dist_entry.insert(0, "10")
        self.dist_entry.pack(side="left", padx=2)

        ctk.CTkLabel(motor_row1, text="spd:", width=28).pack(side="left")
        self.speed_entry = ctk.CTkEntry(motor_row1, width=40)
        self.speed_entry.insert(0, "50")
        self.speed_entry.pack(side="left", padx=2)

        ctk.CTkLabel(motor_row1, text="acc:", width=28).pack(side="left")
        self.accel_entry = ctk.CTkEntry(motor_row1, width=40)
        self.accel_entry.insert(0, "100")
        self.accel_entry.pack(side="left", padx=2)

        # Row 2: Action buttons (compact)
        motor_row2 = ctk.CTkFrame(motor_section, fg_color="transparent")
        motor_row2.pack(fill="x", padx=5, pady=(2, 5))
        motor_row2.grid_columnconfigure((0, 1, 2, 3, 4), weight=1)

        btn_h = 26
        ctk.CTkButton(
            motor_row2,
            text="Move",
            height=btn_h,
            width=40,
            command=self.send_move_command,
        ).grid(row=0, column=0, sticky="ew", padx=2)
        ctk.CTkButton(
            motor_row2,
            text="Home",
            height=btn_h,
            width=40,
            fg_color="#228B22",
            command=self.send_home_command,
        ).grid(row=0, column=1, sticky="ew", padx=2)
        ctk.CTkButton(
            motor_row2,
            text="Sync",
            height=btn_h,
            width=40,
            command=self.send_query_command,
        ).grid(row=0, column=2, sticky="ew", padx=2)
        ctk.CTkButton(
            motor_row2,
            text="Zero",
            height=btn_h,
            width=40,
            fg_color="#B8860B",
            command=self.send_reset_command,
        ).grid(row=0, column=3, sticky="ew", padx=2)
        ctk.CTkButton(
            motor_row2,
            text="Unlock",
            height=btn_h,
            width=40,
            fg_color="#555555",
            command=self.send_release_command,
        ).grid(row=0, column=4, sticky="ew", padx=2)

        # ===== SECTION 5: Tools & Config =====
        tools_section = ctk.CTkFrame(self.controls_frame)
        tools_section.grid(row=row, column=0, padx=pad_x, pady=2, sticky="ew")
        row += 1

        ctk.CTkLabel(
            tools_section,
            text="TOOLS & CONFIG",
            font=("Arial", 11, "bold"),
            text_color="#888888",
        ).pack(anchor="w", padx=5, pady=(5, 2))

        # Cut/Drop test row with editable angles
        test_row = ctk.CTkFrame(tools_section, fg_color="transparent")
        test_row.pack(fill="x", padx=5, pady=2)

        ctk.CTkLabel(test_row, text="Cut°", width=32).pack(side="left")
        self.cut_angle_entry = ctk.CTkEntry(test_row, width=40)
        self.cut_angle_entry.insert(0, str(self.harvester.cut_angle))
        self.cut_angle_entry.pack(side="left", padx=2)
        ctk.CTkButton(
            test_row,
            text="✂ Test",
            width=55,
            height=26,
            fg_color="#8B4513",
            hover_color="#6B3410",
            command=self.test_cut,
        ).pack(side="left", padx=(2, 10))

        ctk.CTkLabel(test_row, text="Drop°", width=38).pack(side="left")
        self.drop_angle_entry = ctk.CTkEntry(test_row, width=40)
        self.drop_angle_entry.insert(0, str(self.harvester.drop_angle))
        self.drop_angle_entry.pack(side="left", padx=2)
        ctk.CTkButton(
            test_row,
            text="↓ Test",
            width=55,
            height=26,
            fg_color="#4682B4",
            hover_color="#36648B",
            command=self.test_drop,
        ).pack(side="left", padx=(2, 10))

        ctk.CTkButton(
            test_row,
            text="Query",
            width=50,
            height=26,
            command=self.send_config_command,
        ).pack(side="right")

        # Config row
        config_row = ctk.CTkFrame(tools_section, fg_color="transparent")
        config_row.pack(fill="x", padx=5, pady=(2, 5))

        ctk.CTkLabel(config_row, text="Area", width=35, anchor="w").pack(side="left")
        self.area_thresh_entry = ctk.CTkEntry(config_row, width=55)
        self.area_thresh_entry.insert(0, str(self.harvester.area_threshold))
        self.area_thresh_entry.pack(side="left", padx=2)

        ctk.CTkLabel(config_row, text="Z↑", width=22).pack(side="left")
        self.z_offset_entry = ctk.CTkEntry(config_row, width=40)
        self.z_offset_entry.insert(0, str(self.harvester.cutting_z_offset))
        self.z_offset_entry.pack(side="left", padx=2)

        ctk.CTkLabel(config_row, text="Y→", width=22).pack(side="left")
        self.y_offset_entry = ctk.CTkEntry(config_row, width=40)
        self.y_offset_entry.insert(0, str(self.harvester.cutting_y_offset))
        self.y_offset_entry.pack(side="left", padx=2)

        ctk.CTkButton(
            config_row,
            text="Apply",
            width=50,
            height=24,
            command=self.apply_harvester_config,
        ).pack(side="left", padx=5)

        # ===== SECTION 6: Log (expands to fill) =====
        log_section = ctk.CTkFrame(self.controls_frame)
        log_section.grid(row=row, column=0, padx=pad_x, pady=(2, pad_y), sticky="nsew")
        log_section.grid_rowconfigure(1, weight=1)
        log_section.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            log_section, text="LOG", font=("Arial", 11, "bold"), text_color="#888888"
        ).grid(row=0, column=0, sticky="w", padx=5, pady=(5, 2))

        self.log_box = ctk.CTkTextbox(log_section, height=60)
        self.log_box.grid(row=1, column=0, padx=5, pady=(0, 5), sticky="nsew")
        self.log_message("Dashboard Ready.")

    def refresh_ports(self):
        """Refresh serial port list."""
        ports = self.get_serial_ports()
        self.port_combo.configure(values=ports)
        if ports:
            self.port_combo.set(ports[0])

    def apply_harvester_config(self):
        """Apply harvester configuration from UI."""
        try:
            self.harvester.area_threshold = int(self.area_thresh_entry.get())
            self.harvester.cutting_z_offset = int(self.z_offset_entry.get())
            self.harvester.cutting_y_offset = int(self.y_offset_entry.get())
            self.log_message(
                f"Config: Area={self.harvester.area_threshold}, Z={self.harvester.cutting_z_offset}, Y={self.harvester.cutting_y_offset}"
            )
        except ValueError:
            self.log_message("Invalid config values!")

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
            new_color = "#228B22" if is_selected else "#1F6AA5"
            hover_color = "#1a6b1a" if is_selected else "#144F7C"
            new_text = f"  ID: {l_id}   |   Dist: {dist}px"

            if l_id in self.lemon_buttons:
                btn, old_text, old_color = self.lemon_buttons[l_id]
                if old_text != new_text or old_color != new_color:
                    btn.configure(
                        text=new_text, fg_color=new_color, hover_color=hover_color
                    )
                    self.lemon_buttons[l_id] = (btn, new_text, new_color)
            else:
                btn = ctk.CTkButton(
                    self.lemon_list_container,
                    text=new_text,
                    fg_color=new_color,
                    hover_color=hover_color,
                    height=30,
                    anchor="w",
                    font=("Consolas", 11, "bold"),
                    command=lambda i=l_id: self.select_lemon(i),
                )
                btn.pack(pady=2, padx=2, fill="x")
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
        # Update position tracking for manual moves
        # Note: Manual moves bypass limit checking - user is responsible
        # X-axis is NOT inverted here as user enters raw firmware values
        try:
            axis_idx = int(axis)
            dist_val = float(dist)
            if 0 <= axis_idx <= 2:
                # For X-axis, firmware receives inverted value, so we invert back
                if axis_idx == 0:
                    dist_val = -dist_val
                self.harvester._current_pos[axis_idx] += dist_val
        except ValueError:
            pass  # Invalid input, skip position update

    def send_home_command(self):
        """Move to home position using proper limit-checked movement."""
        if self.harvester.move_to_home():
            home = self.harvester.home_pos
            self.log_message(f"Moving to home: X={home[0]}, Y={home[1]}, Z={home[2]}")
        elif self.harvester.is_position_known():
            self.log_message("Already at home position")

    def send_query_command(self):
        """Query current position and status."""
        self.send_command("?")

    def send_config_command(self):
        """Query configuration (axis limits)."""
        self.send_command("G")

    def send_reset_command(self):
        """Reset position counter to 0,0,0."""
        self.send_command("H")
        self.harvester.reset_position()
        self.log_message("Position reset to 0,0,0")

    def send_release_command(self):
        """Release/disable steppers for manual movement."""
        self.send_command("R")
        self.harvester.invalidate_position()
        self.log_message("Steppers released - query position after manual move")
        # Auto-query position after a short delay to get current state
        self.after(500, lambda: self.send_command("?"))

    def emergency_stop(self):
        """Emergency stop all motors."""
        self.send_command("!")
        self.harvester.abort()
        self.harvester.invalidate_position()
        self.log_message("EMERGENCY STOP - position unknown")
        # Query actual position from firmware after stop
        self.send_command("?")

    def test_cut(self):
        """Test cut sequence - reads angle from entry and updates harvester config."""
        try:
            angle = int(self.cut_angle_entry.get())
            self.harvester.cut_angle = angle  # Update harvester config
            cmd = f"C {angle}"
            self.send_command(cmd)
            self.log_message(f"Test cut at {angle}°")
        except ValueError:
            self.log_message("Invalid cut angle!")

    def test_drop(self):
        """Test drop sequence - reads angle from entry and updates harvester config."""
        try:
            angle = int(self.drop_angle_entry.get())
            self.harvester.drop_angle = angle  # Update harvester config
            cmd = f"D {angle}"
            self.send_command(cmd)
            self.log_message(f"Test drop at {angle}°")
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
                    self.harvester.sync_position(x, y, z)
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
