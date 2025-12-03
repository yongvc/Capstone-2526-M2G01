import customtkinter as ctk
import cv2
from PIL import Image, ImageTk
import serial
import serial.tools.list_ports
import threading
import time

class DashboardApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Motor Controller Dashboard")
        self.geometry("1200x800")
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        # Serial Connection
        self.serial_port = None
        self.is_connected = False

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
        self.controls_frame = ctk.CTkFrame(self, width=400)
        self.controls_frame.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
        
        self.setup_controls()

        # Camera Setup
        self.cap = cv2.VideoCapture(0)
        self.update_camera()

        # Polling Thread
        self.polling = False
        self.poll_thread = None

    def setup_controls(self):
        # Connection Section
        self.conn_frame = ctk.CTkFrame(self.controls_frame)
        self.conn_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(self.conn_frame, text="Serial Connection", font=("Arial", 16, "bold")).pack(pady=5)
        
        self.port_combo = ctk.CTkComboBox(self.conn_frame, values=self.get_serial_ports())
        self.port_combo.pack(pady=5)
        
        self.connect_btn = ctk.CTkButton(self.conn_frame, text="Connect", command=self.toggle_connection)
        self.connect_btn.pack(pady=5)

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

    def update_camera(self):
        ret, frame = self.cap.read()
        if ret:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame)
            
            # Resize to fit (maintain aspect ratio)
            w_frame = self.camera_frame.winfo_width()
            h_frame = self.camera_frame.winfo_height()
            if w_frame > 10 and h_frame > 10: # Avoid error on init
                img.thumbnail((w_frame, h_frame))
                
            imgtk = ImageTk.PhotoImage(image=img)
            self.camera_label.configure(image=imgtk, text="")
            self.camera_label.image = imgtk # Keep reference
        
        self.after(10, self.update_camera)

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
        self.send_command(cmd)

    def emergency_stop(self):
        # Assuming there is a stop command or we just stop sending? 
        # The firmware doesn't seem to have an explicit STOP command in the snippet I saw.
        # I'll send a move 0 command or just log it for now.
        # Actually, let's check firmware... It doesn't have a STOP command.
        # I'll implement a soft stop by sending a move with 0 distance for now, or just log.
        # Ideally firmware should have a STOP command.
        self.log_message("STOP pressed (Soft stop not fully implemented in FW)")

    def update_servo_label(self, value):
        self.servo_label.configure(text=f"Angle: {int(value)}")

    def set_servo(self):
        angle = int(self.servo_slider.get())
        # Protocol: S <index> <angle>
        # Assuming index 0 for now
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
        if self.cap.isOpened():
            self.cap.release()
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
        self.destroy()

if __name__ == "__main__":
    app = DashboardApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
