import threading
import time
import psutil
import os

class OrangePiMonitor:
    def __init__(self):
        self.cpu_usage = 0.0
        self.ram_usage = 0.0
        self.temperature = 0.0
        self.fan_status = "OFF"
        self.temp_limit = 70.0 
        self.is_stress_testing = False
        
        # ADD THIS: A mailbox for asynchronous messages
        self.message_queue = [] 
        
        self.lock = threading.Lock()
        self.condition = threading.Condition(self.lock)

    def _read_cpu_temp(self):
        try:
            with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                temp = f.read().strip()
                return float(temp) / 1000.0
        except FileNotFoundError:
            return 0.0

    def sensor_thread_logic(self):
        while True:
            with self.lock:
                self.cpu_usage = psutil.cpu_percent(interval=None)
                self.ram_usage = psutil.virtual_memory().percent
                
                if not self.is_stress_testing:
                    self.temperature = self._read_cpu_temp()
                
                if self.temperature > self.temp_limit:
                    self.condition.notify_all()
            
            time.sleep(2)

    def protection_thread_logic(self):
        while True:
            with self.condition:
                self.condition.wait() 
                
                self.fan_status = "ON"
                msg = f"!!! ALERTA TERMICO: {self.temperature:.1f} C !!!"
                print(msg)
                self.message_queue.append(msg) # Put message in the mailbox
            
            while True:
                time.sleep(2)
                
                with self.lock:
                    current_temp = self.temperature
                    limit = self.temp_limit
                    
                if current_temp < (limit - 2.0):
                    with self.lock:
                        self.fan_status = "OFF"
                        msg = "[INFO] Temperatura normalizada. Cooler desligado."
                        print(msg)
                        self.message_queue.append(msg) # Put message in the mailbox
                    break