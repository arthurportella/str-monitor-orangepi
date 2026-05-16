# src/server/monitor.py
import threading
import time
import psutil
import os

class OrangePiMonitor:
    def __init__(self):
        # Recursos compartilhados
        self.cpu_usage = 0.0
        self.ram_usage = 0.0
        self.temperature = 0.0
        self.fan_status = "OFF"
        self.temp_limit = 70.0 # Reduzido para um limite real de segurança
        
        # Sincronização
        self.lock = threading.Lock()
        self.condition = threading.Condition(self.lock)

    def _read_cpu_temp(self):
        """Lê a temperatura real do SoC via Sysfs"""
        try:
            # Caminho padrão na maioria das distros para Orange Pi/Allwinner
            with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                temp = f.read().strip()
                return float(temp) / 1000.0
        except FileNotFoundError:
            # Fallback caso o caminho seja diferente em sua versão do kernel
            return 0.0

    def sensor_thread_logic(self):
        """Thread Periódica 1: Lê sensores reais a cada 2s"""
        while True:
            with self.lock:
                # Coleta de dados reais
                self.cpu_usage = psutil.cpu_percent(interval=None)
                self.ram_usage = psutil.virtual_memory().percent
                self.temperature = self._read_cpu_temp()
                
                # Log interno para depuração no terminal do servidor
                # print(f"[SENSORS] CPU: {self.cpu_usage}% | Temp: {self.temperature}°C")
                
                # Notifica a Thread de Proteção se o limite for atingido
                if self.temperature > self.temp_limit:
                    self.condition.notify_all()
            
            time.sleep(2)

def protection_thread_logic(self):
        """Thread 4: Proteção Térmica baseada em Variável de Condição"""
        while True:
            # 1. Wait for the alarm inside the condition block
            with self.condition:
                self.condition.wait() # Sleeps and releases the lock
                # When it wakes up, it holds the lock again!
                self.fan_status = "ON"
                print(f"!!! ALERTA TÉRMICO: {self.temperature:.1f}°C !!!")
            
            # 2. EXIT the condition block IMMEDIATELY to release the lock!
            # Now other threads (like the Network and Sensors) can keep running.
            
            # 3. Cooling loop (Runs without holding the lock hostage)
            while True:
                time.sleep(2)
                
                # Briefly grab the lock just to check the current temperature
                with self.lock:
                    current_temp = self.temperature
                    limit = self.temp_limit
                    
                # If it cooled down by just 2 degrees below the limit, turn off the fan
                if current_temp < (limit):
                    with self.lock:
                        self.fan_status = "OFF"
                    print("[INFO] Temperatura normalizada. Cooler desligado.")
                    break # Exit the cooling loop and go back to waiting for the next alarm