import socket
import threading
import json
import time
from monitor import OrangePiMonitor

# Configurações de Rede
HOST = '0.0.0.0'  # Escuta em todas as interfaces de rede (Wi-Fi/Ethernet do Orange Pi)
PORT = 5000       # Porta de comunicação

# Instância global do monitor (recurso compartilhado)
monitor = OrangePiMonitor()

def log_thread_logic():
    """Thread Periódica 2 (Obrigatória): Log do Sistema a cada 10s"""
    while True:
        time.sleep(10)
        # Trava o Mutex para ler o estado de forma consistente
        with monitor.lock:
            status = {
                "cpu": monitor.cpu_usage,
                "ram": monitor.ram_usage,
                "temp": monitor.temperature,
                "fan": monitor.fan_status
            }
        
        # Escreve de forma incremental no arquivo
        try:
            with open("orange_pi_log.txt", "a") as f:
                timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
                f.write(f"[{timestamp}] {json.dumps(status)}\n")
        except Exception as e:
            print(f"[ERRO DE LOG] Falha ao escrever arquivo: {e}")

def handle_client(conn, addr):
    """Lida com as requisições de um cliente específico"""
    print(f"[REDE] Novo cliente conectado: {addr}")
    with conn:
        while True:
            try:
                # Aguarda dados do cliente (bloqueante)
                data = conn.recv(1024)
                if not data:
                    break # Cliente desconectou
                
                comando = data.decode('utf-8').strip()
                resposta = {"status": "error", "message": "Comando invalido"}

                # --- IMPLEMENTAÇÃO DOS 6 COMANDOS ---
                
                if comando == "GET_STATUS":
                    with monitor.lock:
                        resposta = {
                            "cpu": round(monitor.cpu_usage, 1),
                            "ram": round(monitor.ram_usage, 1),
                            "temp": round(monitor.temperature, 1),
                            "fan_status": monitor.fan_status
                        }

                elif comando == "FAN_ON":
                    with monitor.lock:
                        monitor.fan_status = "ON"
                    resposta = {"message": "Ventoinha LIGADA manualmente."}

                elif comando == "FAN_OFF":
                    with monitor.lock:
                        monitor.fan_status = "OFF"
                    resposta = {"message": "Ventoinha DESLIGADA manualmente."}

                elif comando.startswith("SET_TEMP_LIMIT"):
                    try:
                        _, valor = comando.split()
                        novo_limite = float(valor)
                        with monitor.lock:
                            monitor.temp_limit = novo_limite
                        resposta = {"message": f"Limite de alarme alterado para {novo_limite} C."}
                    except ValueError:
                        resposta = {"message": "Erro de sintaxe. Use: SET_TEMP_LIMIT 65.0"}

                elif comando == "FORCE_LOG":
                    with monitor.lock:
                        current_temp = monitor.temperature
                    with open("orange_pi_log.txt", "a") as f:
                        f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] FORCED LOG - Temp: {current_temp}\n")
                    resposta = {"message": "Log gravado imediatamente."}

                elif comando == "STRESS_TEST":
                    def apply_stress():
                        with monitor.lock:
                            monitor.is_stress_testing = True # Block real sensors
                            monitor.temperature = 95.0
                            monitor.condition.notify_all()
                        
                        time.sleep(15) # Hold the heat for 15 seconds!
                        
                        with monitor.lock:
                            monitor.is_stress_testing = False # Let real sensors work again
                            
                    # Start the stress test in the background so the GUI doesn't freeze!
                    threading.Thread(target=apply_stress, daemon=True).start()
                    
                    resposta = {"message": "Stress test at 95C activated for 15 seconds!"}

                # Codifica o dicionário para JSON e envia de volta ao cliente
                conn.sendall((json.dumps(resposta) + "\n").encode('utf-8'))
                
            except ConnectionResetError:
                break
                
    print(f"[REDE] Cliente {addr} desconectado.")

def network_thread_logic():
    """Thread 1 (Obrigatória): Comunicação em Rede (Socket Listen)"""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # Evita erro "Port in use"
    server.bind((HOST, PORT))
    server.listen()
    print(f"[SERVIDOR INICIADO] Escutando em {HOST}:{PORT}")
    
    while True:
        conn, addr = server.accept()
        # Delega o cliente para uma sub-thread para não travar o accept()
        client_handler = threading.Thread(target=handle_client, args=(conn, addr))
        client_handler.daemon = True
        client_handler.start()

if __name__ == "__main__":
    print("--- INICIANDO SISTEMA EMBARCADO (ORANGE PI) ---")
    
    # Criação das 4 Threads exigidas no escopo
    t1 = threading.Thread(target=network_thread_logic, name="Thread-Rede")
    t2 = threading.Thread(target=monitor.sensor_thread_logic, name="Thread-Sensores")
    t3 = threading.Thread(target=log_thread_logic, name="Thread-Log")
    t4 = threading.Thread(target=monitor.protection_thread_logic, name="Thread-Protecao")

    # Transforma em Daemons (se o programa principal morrer, elas morrem junto)
    t1.daemon = True
    t2.daemon = True
    t3.daemon = True
    t4.daemon = True

    # Inicialização da Concorrência
    t1.start()
    t2.start()
    t3.start()
    t4.start()

    print("[SISTEMA] Todas as 4 threads rodando. Pressione Ctrl+C para parar.")
    
    # Mantém a thread principal (Main) rodando para que os daemons não fechem
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[SISTEMA] Desligamento seguro iniciado. Encerrando servidor.")