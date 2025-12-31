import customtkinter as ctk
import cv2
from PIL import Image, ImageTk
import serial
import serial.tools.list_ports
import threading
import time
from LemonDetector.detect import LemonDetector

class CameraThread(threading.Thread):
    def __init__(self, mock_mode=False, mock_path="mock_lemon.mp4"):
        super().__init__()
        self.daemon = True
        self.running = True
        self.lock = threading.Lock()
        
        self.mock_mode = mock_mode
        self.mock_path = mock_path
        
        self.cap = None
        self.detector = LemonDetector(tuning_mode=False)
        
        self.latest_frame = None
        self.latest_lemons = []
        
        self._open_camera()

    def _open_camera(self):
        if self.cap is not None:
            self.cap.release()
            
        if self.mock_mode:
            print(f"CameraThread: Opening Mock {self.mock_path}")
            self.cap = cv2.VideoCapture(self.mock_path)
        else:
            print("CameraThread: Opening Webcam 0")
            self.cap = cv2.VideoCapture(0)

    def update_source(self, mock_mode, mock_path):
        with self.lock:
            self.mock_mode = mock_mode
            self.mock_path = mock_path
            self._open_camera()

    def stop(self):
        self.running = False
        if self.cap:
            self.cap.release()

    def run(self):
        while self.running:
            if self.cap is None or not self.cap.isOpened():
                time.sleep(0.1)
                continue

            ret, frame = self.cap.read()

            # Handle Looping for Mock Mode
            if not ret and self.mock_mode:
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = self.cap.read()
            
            if ret and frame is not None:
                # Run Detection
                res_frame, lemons = self.detector.detect(frame)
                
                with self.lock:
                    self.latest_frame = res_frame
                    self.latest_lemons = lemons
            else:
                time.sleep(0.01) # fast sleep if no frame

    def get_latest(self):
        with self.lock:
            if self.latest_frame is None:
                return None, []
            return self.latest_frame.copy(), list(self.latest_lemons)


class DashboardApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Motor Controller Dashboard")
        self.geometry("1200x800")
        
        # Fullscreen
        self.after(0, lambda: self.state('zoomed')) # Maximized
        # self.attributes("-fullscreen", True) # Alternative for true fullscreen
        self.bind("<Escape>", lambda e: self.destroy())

        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        # Serial Connection
        self.serial_port = None
        self.is_connected = False
        
        # Camera Thread Initialization
        self.camera_thread = CameraThread(mock_mode=False, mock_path="mock_lemon.mp4")
        self.camera_thread.start()

        self.selected_lemon_id = None
        self.detected_lemons = []
        self.lemon_buttons = {} # id -> (widget, text, color)

        # Layout Configuration
        self.grid_columnconfigure(0, weight=1) # Camera
        self.grid_columnconfigure(1, weight=0) # Controls
        self.grid_rowconfigure(0, weight=1)

        # Left Frame: Camera
        self.camera_frame = ctk.CTkFrame(self)
        self.camera_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        self.camera_label = ctk.CTkLabel(self.camera_frame, text="Camera Feed Loading...")
        self.camera_label.pack(expand=True, fill="both", padx=5, pady=5)

        # Right Frame: Controls
        self.controls_frame = ctk.CTkScrollableFrame(self, width=400) # Made scrollable for potentially long list
        self.controls_frame.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
        
        self.setup_controls()

        # Polling Thread
        self.polling = False
        self.poll_thread = None

        # Start UI Update Loop
        self.update_camera_ui()

    def setup_controls(self):
        # Connection Section
        self.conn_frame = ctk.CTkFrame(self.controls_frame)
        self.conn_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(self.conn_frame, text="Serial Connection", font=("Arial", 16, "bold")).pack(pady=5)
        
        self.port_combo = ctk.CTkComboBox(self.conn_frame, values=self.get_serial_ports())
        self.port_combo.pack(pady=5)
        
        self.connect_btn = ctk.CTkButton(self.conn_frame, text="Connect", command=self.toggle_connection)
        self.connect_btn.pack(pady=5)

        # Camera Source Section (Mock Mode)
        self.cam_src_frame = ctk.CTkFrame(self.controls_frame)
        self.cam_src_frame.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(self.cam_src_frame, text="Camera Source", font=("Arial", 16, "bold")).pack(pady=5)
        
        self.mock_switch = ctk.CTkSwitch(self.cam_src_frame, text="Mock Mode", command=self.toggle_mock_mode)
        self.mock_switch.pack(pady=5)
        
        self.mock_entry = ctk.CTkEntry(self.cam_src_frame, placeholder_text="Path to video/image")
        self.mock_entry.insert(0, "mock_lemon.mp4")
        self.mock_entry.pack(pady=5, fill="x", padx=10)
        
        self.reload_btn = ctk.CTkButton(self.cam_src_frame, text="Reload Source", command=self.reload_source)
        self.reload_btn.pack(pady=5)

        # Lemon List Section
        self.lemon_frame = ctk.CTkFrame(self.controls_frame)
        self.lemon_frame.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(self.lemon_frame, text="Detected Lemons", font=("Arial", 16, "bold")).pack(pady=5)
        
        # Changed to Scrollable Frame with fixed height
        self.lemon_list_container = ctk.CTkScrollableFrame(self.lemon_frame, height=200)
        self.lemon_list_container.pack(fill="x", padx=5, pady=5)
        # We will dynamically populate this container

        # Motor Control Section
        self.motor_frame = ctk.CTkFrame(self.controls_frame)
        self.motor_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(self.motor_frame, text="Stepper Control", font=("Arial", 16, "bold")).pack(pady=5)
        
        # Axis Selection
        self.axis_var = ctk.StringVar(value="0")
        ctk.CTkRadioButton(self.motor_frame, text="X Axis", variable=self.axis_var, value="0").pack(anchor="w", padx=20)
        ctk.CTkRadioButton(self.motor_frame, text="Y Axis", variable=self.axis_var, value="1").pack(anchor="w", padx=20)
        ctk.CTkRadioButton(self.motor_frame, text="Z Axis", variable=self.axis_var, value="2").pack(anchor="w", padx=20)

        # Parameters
        self.dist_entry = self.create_labeled_entry(self.motor_frame, "Distance (mm):", "10")
        self.speed_entry = self.create_labeled_entry(self.motor_frame, "Speed (mm/s):", "50")
        self.accel_entry = self.create_labeled_entry(self.motor_frame, "Accel (mm/s²):", "100")

        # Buttons
        self.move_btn = ctk.CTkButton(self.motor_frame, text="Move", command=self.send_move_command)
        self.move_btn.pack(pady=10)
        
        self.stop_btn = ctk.CTkButton(self.motor_frame, text="STOP", fg_color="red", hover_color="darkred", command=self.emergency_stop)
        self.stop_btn.pack(pady=5)

        # Servo Control Section
        self.servo_frame = ctk.CTkFrame(self.controls_frame)
        self.servo_frame.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(self.servo_frame, text="Servo Control", font=("Arial", 16, "bold")).pack(pady=5)
        
        self.servo_slider = ctk.CTkSlider(self.servo_frame, from_=0, to=180, command=self.update_servo_label)
        self.servo_slider.pack(pady=10)
        self.servo_label = ctk.CTkLabel(self.servo_frame, text="Angle: 0")
        self.servo_label.pack()
        self.servo_btn = ctk.CTkButton(self.servo_frame, text="Set Servo", command=self.set_servo)
        self.servo_btn.pack(pady=5)

        # Console/Log
        self.log_box = ctk.CTkTextbox(self.controls_frame, height=150)
        self.log_box.pack(fill="x", padx=10, pady=10)
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
            except Exception as e:
                self.log_message(f"Connection Failed: {e}")
        else:
            self.stop_polling()
            if self.serial_port:
                self.serial_port.close()
            self.is_connected = False
            self.connect_btn.configure(text="Connect", fg_color="#1f6aa5") # Default blue
            self.log_message("Disconnected")

    def toggle_mock_mode(self):
        mock_mode = self.mock_switch.get()
        # Ensure we just call reload source which handles the thread update
        self.reload_source()

    def reload_source(self):
        mock_mode = self.mock_switch.get()
        path = self.mock_entry.get()
        self.camera_thread.update_source(mock_mode, path)
        self.log_message(f"Source Updated. Mock: {mock_mode}, Path: {path}")

    def update_camera_ui(self):
        # Poll the thread for the latest frame
        res_frame, lemons = self.camera_thread.get_latest()

        if res_frame is not None:
            self.detected_lemons = lemons
            
            # Selection Logic
            if not lemons:
                self.selected_lemon_id = None
            else:
                ids = [l['id'] for l in lemons]
                if self.selected_lemon_id not in ids:
                    self.selected_lemon_id = lemons[0]['id']
            
            # Highlight Selection
            if self.selected_lemon_id is not None:
                for l in lemons:
                    if l['id'] == self.selected_lemon_id:
                        cv2.circle(res_frame, (l['x'], l['y']), 30, (0, 255, 255), 3)
                        cv2.putText(res_frame, "TARGET", (l['x'] - 20, l['y'] - 30), 
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
                        break

            # Update UI List (Optimized)
            self.update_lemon_list_ui()

            # Display (Optimized Resize)
            w_frame = self.camera_frame.winfo_width()
            h_frame = self.camera_frame.winfo_height()
            
            if w_frame > 10 and h_frame > 10:
                h_img, w_img = res_frame.shape[:2]
                img_ratio = w_img / h_img
                frame_ratio = w_frame / h_frame
                
                if frame_ratio > img_ratio:
                    new_h = h_frame
                    new_w = int(h_frame * img_ratio)
                else:
                    new_w = w_frame
                    new_h = int(w_frame / img_ratio)
                
                # Resize using OpenCV (Much faster than PIL)
                res_frame = cv2.resize(res_frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

            # Convert to PIL
            frame_rgb = cv2.cvtColor(res_frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame_rgb)
            
            # Use CTkImage instead of ImageTk
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(new_w, new_h))
            
            self.camera_label.configure(image=ctk_img, text="")
            self.camera_label.image = ctk_img # Keep reference
        
        self.after(10, self.update_camera_ui)

    def update_lemon_list_ui(self):
        current_ids = set()
        
        if not self.detected_lemons:
             pass

        # Update or Create Buttons
        for lemon in self.detected_lemons:
            l_id = lemon['id']
            current_ids.add(l_id)
            dist = int(lemon['dist'])
            
            is_selected = (l_id == self.selected_lemon_id)
            new_color = "green" if is_selected else "#1f6aa5"
            new_text = f"ID: {l_id} | Dist: {dist}px"
            
            if l_id in self.lemon_buttons:
                # Update existing
                btn, old_text, old_color = self.lemon_buttons[l_id]
                if old_text != new_text or old_color != new_color:
                    btn.configure(text=new_text, fg_color=new_color)
                    self.lemon_buttons[l_id] = (btn, new_text, new_color)
            else:
                # Create new
                btn = ctk.CTkButton(self.lemon_list_container, 
                                    text=new_text, 
                                    fg_color=new_color,
                                    command=lambda i=l_id: self.select_lemon(i))
                btn.pack(pady=2, fill="x")
                self.lemon_buttons[l_id] = (btn, new_text, new_color)

        # Remove Old Buttons
        for l_id in list(self.lemon_buttons.keys()):
            if l_id not in current_ids:
                btn, _, _ = self.lemon_buttons[l_id]
                btn.destroy()
                del self.lemon_buttons[l_id]

    def select_lemon(self, lemon_id):
        self.selected_lemon_id = lemon_id

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
        # Protocol: M <axis> <distance_mm> <max_speed_mm_s> <accel_mm_s2>
        cmd = f"M {axis} {dist} {speed} {accel}"
        self.log_message(f"Sent: {cmd}")

    def emergency_stop(self):
        self.log_message("STOP pressed (Soft stop)")

    def update_servo_label(self, value):
        self.servo_label.configure(text=f"Angle: {int(value)}")

    def set_servo(self):
        angle = int(self.servo_slider.get())
        cmd = f"S 0 {angle}"
        self.send_command(cmd)

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
                            # Use after to update UI from thread
                            self.after(0, lambda l=line: self.log_message(f"RX: {l}"))
                except Exception as e:
                    print(f"Serial Read Error: {e}")
            time.sleep(0.1)

    def on_closing(self):
        self.stop_polling()
        self.camera_thread.stop()
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
        self.destroy()

if __name__ == "__main__":
    app = DashboardApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
