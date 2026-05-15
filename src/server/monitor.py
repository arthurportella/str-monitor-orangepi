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
            with self.condition:
                self.condition.wait() # Aguarda o notify da thread de sensores
                
                with self.lock:
                    self.fan_status = "ON"
                
                print(f"!!! ALERTA TÉRMICO: {self.temperature:.1f}°C !!!")
                
                # No Orange Pi real, aqui você poderia acionar um GPIO para o cooler
                # Exemplo conceitual: GPIO.output(PIN, GPIO.HIGH)
                
                # Mantém o cooler ligado até baixar 5 graus do limite
                while True:
                    time.sleep(2)
                    current_temp = self._read_cpu_temp()
                    if current_temp < (self.temp_limit - 5):
                        break
                
                with self.lock:
                    self.fan_status = "OFF"
                print("Temperatura normalizada. Cooler desligado.")