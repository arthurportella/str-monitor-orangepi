# src/client/main.py
import customtkinter as ctk
import socket
import threading
import json

SERVER_IP = "192.168.2.11" 
SERVER_PORT = 5000

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class OrangePiDashboard(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Orange Pi Real-Time Monitor")
        self.geometry("600x500")
        
        self.socket_conn = None
        self.connected = False

        self.create_widgets()

    def create_widgets(self):
        # --- Top: Connection Panel ---
        self.conn_frame = ctk.CTkFrame(self)
        self.conn_frame.pack(pady=10, padx=20, fill="x")
        
        self.status_label = ctk.CTkLabel(self.conn_frame, text="Status: DISCONNECTED", text_color="red", font=("Arial", 14, "bold"))
        self.status_label.pack(side="left", padx=10, pady=10)
        
        self.connect_btn = ctk.CTkButton(self.conn_frame, text="Connect", command=self.connect_to_server)
        self.connect_btn.pack(side="right", padx=10, pady=10)

        # --- Middle: Metrics Panel ---
        self.metrics_frame = ctk.CTkFrame(self)
        self.metrics_frame.pack(pady=10, padx=20, fill="x")
        
        self.cpu_label = ctk.CTkLabel(self.metrics_frame, text="CPU: -- %", font=("Arial", 16))
        self.cpu_label.pack(pady=5)
        
        self.ram_label = ctk.CTkLabel(self.metrics_frame, text="RAM: -- %", font=("Arial", 16))
        self.ram_label.pack(pady=5)
        
        self.temp_label = ctk.CTkLabel(self.metrics_frame, text="Temp: -- °C", font=("Arial", 16))
        self.temp_label.pack(pady=5)
        
        self.fan_label = ctk.CTkLabel(self.metrics_frame, text="Fan: OFF", font=("Arial", 16, "bold"), text_color="gray")
        self.fan_label.pack(pady=5)

        # --- Bottom: Control Panel ---
        self.control_frame = ctk.CTkFrame(self)
        self.control_frame.pack(pady=10, padx=20, fill="both", expand=True)
        
        self.btn_status = ctk.CTkButton(self.control_frame, text="1. GET STATUS", command=lambda: self.send_command("GET_STATUS"))
        self.btn_status.grid(row=0, column=0, padx=10, pady=10)
        
        self.btn_fan_on = ctk.CTkButton(self.control_frame, text="2. FAN ON", command=lambda: self.send_command("FAN_ON"))
        self.btn_fan_on.grid(row=0, column=1, padx=10, pady=10)
        
        self.btn_fan_off = ctk.CTkButton(self.control_frame, text="3. FAN OFF", command=lambda: self.send_command("FAN_OFF"))
        self.btn_fan_off.grid(row=0, column=2, padx=10, pady=10)

        self.limit_entry = ctk.CTkEntry(self.control_frame, placeholder_text="Ex: 65.0")
        self.limit_entry.grid(row=1, column=0, padx=10, pady=10)
        
        self.btn_limit = ctk.CTkButton(self.control_frame, text="4. SET TEMP LIMIT", command=self.send_temp_limit)
        self.btn_limit.grid(row=1, column=1, padx=10, pady=10)
        
        self.btn_log = ctk.CTkButton(self.control_frame, text="5. FORCE LOG", command=lambda: self.send_command("FORCE_LOG"))
        self.btn_log.grid(row=1, column=2, padx=10, pady=10)

        self.btn_stress = ctk.CTkButton(self.control_frame, text="6. ⚠️ STRESS TEST ⚠️", fg_color="darkred", hover_color="red", command=lambda: self.send_command("STRESS_TEST"))
        self.btn_stress.grid(row=2, column=1, padx=10, pady=20)

        self.log_textbox = ctk.CTkTextbox(self.control_frame, height=80)
        self.log_textbox.grid(row=3, column=0, columnspan=3, padx=10, pady=10, sticky="ew")

    # --- SAFE UI UPDATE METHODS ---
    # We use self.after(0, ...) to force the main thread to update the UI safely!
    
    def safe_log_msg(self, msg):
        self.after(0, self._insert_log, msg)

    def _insert_log(self, msg):
        self.log_textbox.insert("end", msg + "\n")
        self.log_textbox.see("end")

    def safe_update_metrics(self, cpu, ram, temp, fan):
        self.after(0, self._apply_metrics, cpu, ram, temp, fan)

    def _apply_metrics(self, cpu, ram, temp, fan):
        self.cpu_label.configure(text=f"CPU: {cpu} %")
        self.ram_label.configure(text=f"RAM: {ram} %")
        self.temp_label.configure(text=f"Temp: {temp} °C")
        
        color = "green" if fan == "ON" else "gray"
        self.fan_label.configure(text=f"Fan: {fan}", text_color=color)

    # --- NETWORK & LOGIC ---

    def auto_refresh(self):
        """Automatically asks for status every 2 seconds"""
        if self.connected:
            self.send_command("GET_STATUS")
            self.after(2000, self.auto_refresh) # Schedule the next refresh

    def connect_to_server(self):
        if not self.connected:
            try:
                self.socket_conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.socket_conn.connect((SERVER_IP, SERVER_PORT))
                self.connected = True
                
                self.status_label.configure(text="Status: CONNECTED", text_color="green")
                self.connect_btn.configure(text="Disconnect")
                self.safe_log_msg("[SYSTEM] Connected to Orange Pi successfully.")
                
                # Start network listener
                threading.Thread(target=self.listen_to_server, daemon=True).start()
                
                # Start the auto-refresh loop
                self.auto_refresh()
                
            except Exception as e:
                self.safe_log_msg(f"[ERROR] Could not connect: {e}")
        else:
            self.connected = False
            if self.socket_conn:
                self.socket_conn.close()
            self.status_label.configure(text="Status: DISCONNECTED", text_color="red")
            self.connect_btn.configure(text="Connect")
            self.safe_log_msg("[SYSTEM] Disconnected.")

    def send_command(self, cmd):
        if self.connected and self.socket_conn:
            try:
                self.socket_conn.sendall((cmd + '\n').encode('utf-8'))
            except Exception as e:
                self.safe_log_msg(f"[ERROR] Failed to send: {e}")
        else:
            self.safe_log_msg("[WARNING] You must connect first!")

    def send_temp_limit(self):
        val = self.limit_entry.get()
        if val:
            self.send_command(f"SET_TEMP_LIMIT {val}")

    def listen_to_server(self):
        while self.connected:
            try:
                data = self.socket_conn.recv(1024)
                if not data:
                    break
                
                # Sometimes TCP sends multiple JSONs in one packet separated by \n
                responses = data.decode('utf-8').strip().split('\n')
                
                for raw_response in responses:
                    if not raw_response:
                        continue
                        
                    try:
                        response_dict = json.loads(raw_response)
                        
                        if "cpu" in response_dict:
                            self.safe_update_metrics(
                                response_dict['cpu'], 
                                response_dict['ram'], 
                                response_dict['temp'], 
                                response_dict['fan_status']
                            )
                        
                        if "message" in response_dict:
                            self.safe_log_msg(f"[SERVER]: {response_dict['message']}")
                            
                    except json.JSONDecodeError:
                        self.safe_log_msg(f"[RAW SERVER]: {raw_response}")
                    
            except Exception as e:
                if self.connected:
                    self.safe_log_msg(f"[NETWORK ERROR] {e}")
                break
                
        self.connected = False

if __name__ == "__main__":
    app = OrangePiDashboard()
    app.mainloop()