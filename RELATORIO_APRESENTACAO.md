# 📋 Relatório de Apresentação - Sistema de Monitoramento Orange Pi

## 1. Linguagem Escolhida: Python

### Por que Python?

**Python 3.x** foi escolhido como linguagem principal do projeto por:

1. **Suporte nativo a Threading** - Módulo `threading` com sincronização primitiva (Mutex, Condition Variables)
2. **Simplicidade e Legibilidade** - Código limpo e fácil de entender, ideal para sistemas embarcados
3. **Portabilidade** - Roda em Orange Pi Linux, Windows, macOS sem modificações
4. **Bibliotecas poderosas** - `psutil` para monitoramento, `socket` para rede, `customtkinter` para GUI
5. **Prototipagem rápida** - Ideal para demonstrações em tempo real

---

## 2. Arquitetura Geral do Sistema

```
┌─────────────────────────────────────────────────────────┐
│                    REDE TCP/IP (Porta 5000)            │
│              JSON over TCP Sockets                       │
└──────────────┬──────────────────────────────┬───────────┘
               │                              │
      ┌────────▼─────────┐          ┌────────▼────────┐
      │  SERVIDOR        │          │  CLIENTE        │
      │  (Orange Pi)     │          │  (Desktop GUI)  │
      │                  │          │                 │
      │  4 Threads       │          │  2 Threads      │
      │  Mutex/Condition │◄────────►│  Thread Pool    │
      │  Sincronização   │          │  Auto-Refresh   │
      └──────────────────┘          └─────────────────┘
         (Embedded)                   (Interface Gráfica)
```

---

## 3. REQUISITO 1: 4 Threads no Servidor ✅

### Localização: `src/server/main.py` (linhas 80-95)

```python
if __name__ == "__main__":
    print("--- INICIANDO SISTEMA EMBARCADO (ORANGE PI) ---")
    
    # Criação das 4 Threads exigidas no escopo
    t1 = threading.Thread(target=network_thread_logic, name="Thread-Rede")
    t2 = threading.Thread(target=monitor.sensor_thread_logic, name="Thread-Sensores")
    t3 = threading.Thread(target=log_thread_logic, name="Thread-Log")
    t4 = threading.Thread(target=monitor.protection_thread_logic, name="Thread-Protecao")

    t1.daemon = True
    t2.daemon = True
    t3.daemon = True
    t4.daemon = True

    t1.start()
    t2.start()
    t3.start()
    t4.start()
```

### Thread 1: REDE (obrigatória) 📡
**Arquivo**: `src/server/main.py`, linhas 58-73

```python
def network_thread_logic():
    """Thread 1 (Obrigatória): Comunicação em Rede (Socket Listen)"""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen()
    print(f"[SERVIDOR INICIADO] Escutando em {HOST}:{PORT}")
    
    while True:
        conn, addr = server.accept()
        # Delega o cliente para uma sub-thread
        client_handler = threading.Thread(target=handle_client, args=(conn, addr))
        client_handler.daemon = True
        client_handler.start()
```

**Responsabilidades:**
- Cria socket TCP na porta 5000
- Aguarda conexões de clientes em loop infinito
- Cria uma thread filha para cada cliente (evita bloqueio do accept)
- Roda em paralelo com outras threads

---

### Thread 2: SENSORES (periódica) 📊
**Arquivo**: `src/server/monitor.py`, linhas 23-32

```python
def sensor_thread_logic(self):
    while True:
        with self.lock:  # SINCRONIZAÇÃO COM MUTEX
            self.cpu_usage = psutil.cpu_percent(interval=None)
            self.ram_usage = psutil.virtual_memory().percent
            
            if not self.is_stress_testing:
                self.temperature = self._read_cpu_temp()
            
            if self.temperature > self.temp_limit:
                self.condition.notify_all()  # Acorda thread de proteção
        
        time.sleep(2)  # Periódica a cada 2 segundos
```

**Responsabilidades:**
- Lê CPU usando `psutil.cpu_percent()`
- Lê RAM usando `psutil.virtual_memory()`
- Lê temperatura do arquivo `/sys/class/thermal/thermal_zone0/temp`
- **Sincronização**: Usa `threading.Lock()` para proteger acesso
- **Condition Variable**: Notifica thread de alarme se temp > limite
- **Período**: 2 segundos

---

### Thread 3: LOG (periódica) 📝
**Arquivo**: `src/server/main.py`, linhas 8-20

```python
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
```

**Responsabilidades:**
- Aguarda 10 segundos entre execuções
- **Sincronização**: Usa `with monitor.lock:` para ler estado de forma atômica
- Grava JSON com CPU, RAM, Temperatura e Status do Fan
- Arquivo persistido em `orange_pi_log.txt` (auditoria)
- Período: 10 segundos

---

### Thread 4: PROTEÇÃO TÉRMICA (Condition Variable) 🌡️
**Arquivo**: `src/server/monitor.py`, linhas 34-56

```python
def protection_thread_logic(self):
    while True:
        with self.condition:  # ADQUIRE LOCK + CONDITION VARIABLE
            self.condition.wait()  # ⏸️ Dorme até ser notificada
            
            self.fan_status = "ON"
            msg = f"!!! ALERTA TERMICO: {self.temperature:.1f} C !!!"
            print(msg)
            self.message_queue.append(msg)  # Envia para GUI
        
        # Loop de resfriamento
        while True:
            time.sleep(2)
            
            with self.lock:
                current_temp = self.temperature
                limit = self.temp_limit
            
            # Se temperatura voltou ao normal, desliga fan
            if current_temp < (limit - 2.0):
                with self.lock:
                    self.fan_status = "OFF"
                    msg = "[INFO] Temperatura normalizada. Cooler desligado."
                    print(msg)
                    self.message_queue.append(msg)
                break  # Volta para condition.wait()
```

**Responsabilidades:**
- **DORMINDO**: Fica em `condition.wait()` até thread de sensores notificar
- **ACORDADA**: Quando `temp > temp_limit`, liga ventoinha
- **MONITORAMENTO**: Verifica a cada 2 segundos se temp caiu `(limit - 2.0)`
- **DESLIGAMENTO**: Desliga fan quando temperatura normaliza
- **SEM ESPERA OCUPADA**: Usa Condition Variable (não consome CPU)

---

## 4. REQUISITO 2: Sincronização (Mutex + Condition Variable) ✅

### Localização: `src/server/monitor.py`, linhas 1-19

```python
class OrangePiMonitor:
    def __init__(self):
        self.cpu_usage = 0.0
        self.ram_usage = 0.0
        self.temperature = 0.0
        self.fan_status = "OFF"
        self.temp_limit = 70.0 
        self.is_stress_testing = False
        self.message_queue = [] 
        
        # ✅ MUTEX (Obrigatório)
        self.lock = threading.Lock()
        
        # ✅ CONDITION VARIABLE (Obrigatória)
        self.condition = threading.Condition(self.lock)
```

### MUTEX em Ação

**Exemplo 1 - Thread de Sensores** (protege leitura):
```python
with self.lock:  # Adquire lock
    self.cpu_usage = psutil.cpu_percent(interval=None)
    self.ram_usage = psutil.virtual_memory().percent
    self.temperature = self._read_cpu_temp()
# Libera lock automaticamente ao sair do bloco
```

**Exemplo 2 - Handler de Cliente** (protege escrita):
```python
elif comando == "GET_STATUS":
    with monitor.lock:  # Garante leitura atômica
        resposta = {
            "cpu": round(monitor.cpu_usage, 1),
            "ram": round(monitor.ram_usage, 1),
            "temp": round(monitor.temperature, 1),
            "fan_status": monitor.fan_status
        }
```

**Exemplo 3 - Comando FAN_ON** (protege modificação):
```python
elif comando == "FAN_ON":
    with monitor.lock:  # Garante escrita atômica
        monitor.fan_status = "ON"
    resposta = {"message": "Ventoinha LIGADA manualmente."}
```

### CONDITION VARIABLE em Ação

**Notificação** (Thread de Sensores notifica quando temp sobe):
```python
with self.lock:
    if self.temperature > self.temp_limit:
        self.condition.notify_all()  # 🔔 Acorda thread de proteção
```

**Espera** (Thread de Proteção dorme até notificação):
```python
with self.condition:
    self.condition.wait()  # ⏸️ Dorme aqui até notify_all()
    # Código só executa após notificação
    self.fan_status = "ON"
```

**Problema que resolve**: Sem Condition Variable, teríamos **espera ocupada** (polling com sleep).
Com ela: **Eficiência energética** em sistemas embarcados.

---

## 5. REQUISITO 3: Comunicação Cliente-Servidor ✅

### Protocolo: TCP Sockets + JSON

**Localização**: `src/server/main.py`, linhas 21-56

#### Handshake de Conexão
```python
def handle_client(conn, addr):
    """Lida com as requisições de um cliente específico"""
    print(f"[REDE] Novo cliente conectado: {addr}")
    with conn:
        while True:
            try:
                # RECEBE dados do cliente
                data = conn.recv(1024)
                if not data:
                    break  # Cliente desconectou
                
                comando = data.decode('utf-8').strip()
```

#### Formato de Mensagens
```python
# CLIENTE ENVIA (texto simples + newline):
"GET_STATUS\n"
"FAN_ON\n"
"SET_TEMP_LIMIT 75.0\n"

# SERVIDOR RESPONDE (JSON + newline):
{"cpu": 45.2, "ram": 60.1, "temp": 62.5, "fan_status": "OFF"}\n
{"message": "Ventoinha LIGADA manualmente."}\n
```

#### Resposta do Servidor
```python
# Codifica o dicionário para JSON e envia de volta
conn.sendall((json.dumps(resposta) + "\n").encode('utf-8'))
```

---

## 6. REQUISITO 4: Interface Gráfica no Cliente ✅

### Localização: `src/client/main.py`

#### 1. Conexão com Servidor

```python
def connect_to_server(self):
    if not self.connected:
        try:
            self.socket_conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket_conn.connect((SERVER_IP, SERVER_PORT))  # TCP Connect
            self.connected = True
            
            self.status_label.configure(text="Status: CONNECTED", text_color="green")
            self.connect_btn.configure(text="Disconnect")
            self.safe_log_msg("[SYSTEM] Connected to Orange Pi successfully.")
            
            # Thread secundária para não travar UI
            threading.Thread(target=self.listen_to_server, daemon=True).start()
            
            # Auto-refresh de métricas a cada 2 segundos
            self.auto_refresh()
```

#### 2. Envio de Comandos

```python
def send_command(self, cmd):
    if self.connected and self.socket_conn:
        try:
            self.socket_conn.sendall((cmd + '\n').encode('utf-8'))
        except Exception as e:
            self.safe_log_msg(f"[ERROR] Failed to send: {e}")
    else:
        self.safe_log_msg("[WARNING] You must connect first!")
```

#### 3. Visualização de Respostas (Thread de Rede)

```python
def listen_to_server(self):
    while self.connected:
        try:
            data = self.socket_conn.recv(1024)
            if not data:
                break
            
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
```

#### 4. Atualização Segura da UI (sem travamentos)

```python
def safe_update_metrics(self, cpu, ram, temp, fan):
    # Força a thread principal Tkinter a executar
    self.after(0, self._apply_metrics, cpu, ram, temp, fan)

def _apply_metrics(self, cpu, ram, temp, fan):
    self.cpu_label.configure(text=f"CPU: {cpu} %")
    self.ram_label.configure(text=f"RAM: {ram} %")
    self.temp_label.configure(text=f"Temp: {temp} °C")
    
    color = "green" if fan == "ON" else "gray"
    self.fan_label.configure(text=f"Fan: {fan}", text_color=color)
```

#### 5. Auto-Refresh (a cada 2 segundos)

```python
def auto_refresh(self):
    """Automatically asks for status every 2 seconds"""
    if self.connected:
        self.send_command("GET_STATUS")
        self.after(2000, self.auto_refresh)  # Agenda próxima execução
```

---

## 7. REQUISITO 5: 6 Comandos Cliente-Servidor ✅

### Localização: `src/common/protocol.py` e `src/server/main.py` (linhas 21-56)

| # | Comando | Direção | Descrição | Linha |
|---|---------|---------|-----------|-------|
| 1 | `GET_STATUS` | C→S | Solicita métricas atuais (CPU, RAM, Temp, Fan) | 25 |
| 2 | `FAN_ON` | C→S | Liga manualmente o sistema de resfriamento | 31 |
| 3 | `FAN_OFF` | C→S | Desliga manualmente o sistema de resfriamento | 34 |
| 4 | `SET_TEMP_LIMIT <valor>` | C→S | Altera limite de temperatura para alarme | 37 |
| 5 | `FORCE_LOG` | C→S | Força gravação imediata no arquivo de auditoria | 45 |
| 6 | `STRESS_TEST` | C→S | Simula pico de temperatura (95°C por 7s) | 50 |

### Implementação de cada comando:

```python
if comando == "GET_STATUS":
    # Retorna métricas em JSON
    with monitor.lock:
        resposta = {
            "cpu": round(monitor.cpu_usage, 1),
            "ram": round(monitor.ram_usage, 1),
            "temp": round(monitor.temperature, 1),
            "fan_status": monitor.fan_status
        }
        if len(monitor.message_queue) > 0:
            resposta["message"] = monitor.message_queue.pop(0)

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
            monitor.is_stress_testing = True
            monitor.temperature = 95.0
            monitor.condition.notify_all()  # Acorda thread de proteção
        
        time.sleep(7)  # Mantém alta temperatura por 7 segundos
        
        with monitor.lock:
            monitor.is_stress_testing = False
    
    threading.Thread(target=apply_stress, daemon=True).start()
    resposta = {"message": "Stress test at 95C activated for 7 seconds!"}
```

---

## 8. Fluxo Completo de Execução

### Cenário: Cliente envia GET_STATUS

```
┌─ CLIENTE (Thread Principal UI)
│  ├─ User clica botão "1. GET STATUS"
│  ├─ send_command("GET_STATUS")
│  └─ socket_conn.sendall("GET_STATUS\n")
│
├─ REDE (Cabos/WiFi)
│
└─ SERVIDOR (Múltiplas Threads)
   │
   ├─ Thread-Rede: accept() → cria client_handler
   │  └─ handle_client() recebe "GET_STATUS"
   │
   ├─ Thread-Sensores (paralela): 
   │  ├─ with monitor.lock:
   │  │  └─ cpu_usage = psutil.cpu_percent()
   │  │     ram_usage = psutil.virtual_memory().percent
   │  │     temperature = ler("/sys/class/thermal/...")
   │  │     if temp > limit: condition.notify_all()
   │  └─ time.sleep(2)
   │
   ├─ Thread-Log (paralela):
   │  ├─ time.sleep(10)
   │  ├─ with monitor.lock:
   │  │  └─ grava status em JSON
   │  └─ append("orange_pi_log.txt")
   │
   ├─ Thread-Proteção (paralela):
   │  ├─ condition.wait()  ⏸️ (dorme até notificação)
   │  └─ [Se acordada] liga fan, monitora resfriamento
   │
   └─ handle_client():
      ├─ with monitor.lock:
      │  ├─ resposta["cpu"] = 45.2
      │  ├─ resposta["ram"] = 60.1
      │  ├─ resposta["temp"] = 62.5
      │  └─ resposta["fan_status"] = "OFF"
      ├─ json.dumps(resposta)
      └─ conn.sendall(JSON + "\n")

└─ CLIENTE (Thread de Rede)
   ├─ listen_to_server(): recv(1024)
   ├─ json.loads(response)
   └─ self.after(0, _apply_metrics, ...)
      └─ self.cpu_label.configure(text="CPU: 45.2 %")
         self.ram_label.configure(text="RAM: 60.1 %")
         self.temp_label.configure(text="Temp: 62.5 °C")
         self.fan_label.configure(text="Fan: OFF")
```

---

## 9. Sincronização em Ação (Exemplo Prático)

### Cenário: STRESS_TEST com possível race condition

**SEM Mutex (❌ ERRADO):**
```
Thread-Sensores           Thread-Handle-Client
      │                         │
      ├─ Lê CPU                 │
      │  (mudou!)               ├─ Recebe STRESS_TEST
      ├─ Lê RAM                 │
      │  (mudou!)               ├─ Seta temp = 95.0
      ├─ Lê Temp ──────────────►│ (leitura inconsistente!)
      │  (mudou!)               │
      └─ Notifica               └─ Retorna JSON com dados mistos
      
   ❌ Resposta pode conter:
      {"cpu": 45.2, "ram": 60.1, "temp": 23.5}
      (Temperatura inconsistente!)
```

**COM Mutex (✅ CORRETO):**
```
Thread-Sensores           Thread-Handle-Client
      │                         │
      ├─ LOCK()                 │
      │  ├─ Lê CPU              │
      │  ├─ Lê RAM              │
      │  ├─ Lê Temp             │
      │  └─ UNLOCK()            ├─ LOCK() [esperando...]
      │     (liberado!)          │
      │                          ├─ Seta temp = 95.0
      │                          ├─ UNLOCK()
      │                          │
      └─ [Próxima iteração]     └─ Retorna JSON consistente
      
   ✅ Resposta é sempre consistente:
      {"cpu": 45.2, "ram": 60.1, "temp": 95.0}
```

---

## 10. Fluxo de Alarme Térmico (Condition Variable)

### Passo 1: Temperatura Normal

```
THREAD-SENSORES              THREAD-PROTEÇÃO
      │                            │
      ├─ temp = 62.5°C            ├─ condition.wait()
      │  (< 70°C limit)            │  ⏸️ DORMINDO
      │                            │
      └─ Sem notificação           └─ Sem mudança
```

### Passo 2: Temperatura Sobe

```
THREAD-SENSORES              THREAD-PROTEÇÃO
      │                            │
      ├─ temp = 75.0°C            │
      │  (> 70°C limit)            │
      ├─ condition.notify_all()    │
      │  🔔 NOTIFICA!              │
      │                            ├─ 🔔 ACORDADA!
      │                            │
      │                            ├─ fan_status = "ON"
      │                            ├─ msg = "!!! ALERTA ..."
      │                            └─ message_queue.append(msg)
      │                               (CLIENT recebe na próxima GET_STATUS)
```

### Passo 3: Resfriamento

```
THREAD-PROTEÇÃO (em loop)
      │
      ├─ time.sleep(2)
      ├─ Lê temperatura atual (65.0°C)
      │
      ├─ É < (70.0 - 2.0)?  → SIM!
      │  └─ fan_status = "OFF"
      │     msg = "[INFO] Temperatura normalizada..."
      │     break  (volta para condition.wait())
```

---

## 11. Estrutura de Arquivos do Projeto

```
str-monitor-orangepi/
├── README.md                          # Documentação geral
├── RELATORIO_APRESENTACAO.md          # Este arquivo
│
├── src/
│   ├── common/
│   │   └── protocol.py               # Definição de comandos e keys
│   │
│   ├── server/
│   │   ├── main.py                   # Threads 1, 2, 3 + handler
│   │   └── monitor.py                # Classe OrangePiMonitor (Threads 4)
│   │
│   └── client/
│       └── main.py                   # Interface gráfica com Tkinter
│
└── orange_pi_log.txt                 # Arquivo de auditoria (gerado)
```

---

## 12. Tabela de Sincronização

| Componente | Tipo | Finalidade | Onde Usado |
|-----------|------|-----------|-----------|
| `monitor.lock` | Mutex | Proteger acesso às variáveis compartilhadas | Threads Sensores, Log, Proteção e Handlers |
| `monitor.condition` | Condition Variable | Sincronização event-driven entre Sensores e Proteção | `notify_all()` em Sensores, `wait()` em Proteção |
| `self.after()` | Callback Tkinter | Atualizar UI de forma thread-safe | Listener de rede em Cliente |

---

## 13. Métricas de Performance

| Métrica | Valor | Propósito |
|---------|-------|----------|
| Período de Sensores | 2s | Monitoramento em tempo real |
| Período de Log | 10s | Auditoria com granularidade |
| Limite Térmico Padrão | 70.0°C | Disparador de alarme |
| Hysteresis de Desligamento | 2.0°C | Evita oscilação (desliga em 68°C) |
| Stress Test Duração | 7s | Demonstração suficiente do alarme |
| Auto-Refresh do Cliente | 2s | Sincronização visual |

---

## 14. Pontos-Chave para Apresentação

### 🎯 Destaques Técnicos

1. **Concorrência sem travamentos**: 4 threads rodando em paralelo
2. **Sincronização robusta**: Mutex garante consistência de dados
3. **Event-Driven**: Condition Variable não consome CPU (espera passiva)
4. **Comunicação em rede**: TCP/IP com protocolo JSON
5. **UI responsiva**: Thread secundária de rede + `self.after()` no Tkinter
6. **Auditoria**: Logs persistidos em arquivo a cada 10 segundos

### 🧪 Testes Práticos na Apresentação

1. **Conectar cliente ao servidor**
   - Executar `python src/server/main.py` em um terminal
   - Executar `python src/client/main.py` em outro terminal
   - Clicar "Connect" no cliente

2. **Testar GET_STATUS**
   - Clicar "1. GET STATUS"
   - Verificar se métricas aparecem na GUI

3. **Demonstrar sincronização com STRESS_TEST**
   - Clicar "6. ⚠️ STRESS TEST ⚠️"
   - Observar:
     - Temperatura muda para 95.0°C
     - Fan status muda para "ON"
     - Mensagem de alerta aparece
     - Após 7s: Temperatura volta, Fan desliga, mensagem de normalização

4. **Verificar arquivo de log**
   - Abrir `orange_pi_log.txt`
   - Ver JSON gravado a cada 10 segundos

5. **Testar SET_TEMP_LIMIT**
   - Digitar "50.0" no campo de entrada
   - Clicar "4. SET TEMP LIMIT"
   - Executar STRESS_TEST novamente (alarme deve disparar mais rápido)

---

## 15. Resposta aos Questionamentos Técnicos Previstos

### P: Por que usar Mutex se Python tem GIL?
**R:** O GIL protege interpretação Python, mas NÃO garante atomicidade de operações compostas. Por exemplo:
```python
# SEM MUTEX:
self.temperature = 75.0  # GIL protege esta linha
self.fan_status = "ON"   # Mas outra thread pode ler entre as duas!

# COM MUTEX:
with self.lock:
    self.temperature = 75.0
    self.fan_status = "ON"  # Ambas atômicas!
```

### P: Qual a diferença entre `notify()` e `notify_all()`?
**R:** 
- `notify()`: Acorda apenas UMA thread em espera
- `notify_all()`: Acorda TODAS as threads em espera

Usamos `notify_all()` porque queremos garantir que a thread de proteção acorde mesmo que houver múltiplas threads esperando.

### P: Por que usar JSON em vez de protocolo binário?
**R:** JSON é:
- Legível para debug/logging
- Fácil de expandir (adicionar novos campos)
- Compatível entre plataformas
- Adequado para aplicações embarcadas (não precisa ser ultra-otimizado)

### P: Como evitar race condition no `message_queue`?
**R:** Está protegido por Mutex:
```python
# ESCRITA (na thread de proteção):
with self.lock:
    self.message_queue.append(msg)

# LEITURA (no handler de cliente):
with monitor.lock:
    if len(monitor.message_queue) > 0:
        resposta["message"] = monitor.message_queue.pop(0)
```

---

## Conclusão

Este projeto demonstra os **4 pilares** obrigatórios:
- ✅ **4 Threads** com papéis bem definidos
- ✅ **Sincronização** robusta com Mutex e Condition Variable
- ✅ **Comunicação em rede** via TCP/IP + JSON
- ✅ **Interface gráfica** responsiva e intuitiva

A escolha de **Python** permite código limpo e legível, ideal para demonstração de conceitos de sistemas de tempo real em ambiente educacional.
