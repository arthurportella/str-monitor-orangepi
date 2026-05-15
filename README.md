# Dashboard de Monitoramento Orange Pi (Sistemas de Tempo Real)

Este projeto é um sistema Cliente-Servidor desenvolvido em Python para a disciplina de Sistemas de Tempo Real. O objetivo é realizar o controle e a supervisão remota de métricas de hardware de uma placa embarcada, atuando automaticamente em situações de risco térmico.

## 🏗️ Arquitetura do Sistema

O projeto é dividido em dois módulos principais, comunicando-se via Sockets TCP:

### 1. Servidor Embarcado (Concorrência e Sincronização)
Roda no dispositivo monitorado gerenciando 4 threads protegidas por Mutex:
- **Thread de Rede:** Gerencia a comunicação via Sockets.
- **Thread de Sensores (Periódica):** Lê CPU, RAM e Temperatura a cada 2 segundos.
- **Thread de Log (Periódica):** Grava o estado do sistema a cada 10 segundos.
- **Thread de Alarme Térmico:** Sincronizada via **Variável de Condição**, permanece adormecida até ser notificada sobre um superaquecimento, atuando no acionamento do resfriamento (evitando espera ocupada).

### 2. Cliente Desktop (Interface Gráfica)
Aplicação desenvolvida para solicitar métricas e enviar comandos de controle, operando com uma thread secundária de rede para evitar travamentos da UI.

## 🚀 Comandos Implementados
1. `GET_STATUS`: Solicita as métricas atuais.
2. `FAN_ON`: Liga o sistema de resfriamento manualmente.
3. `FAN_OFF`: Desliga o sistema de resfriamento manualmente.
4. `SET_TEMP_LIMIT <valor>`: Altera o limite térmico do alarme.
5. `FORCE_LOG`: Força a gravação imediata no arquivo de auditoria.
6. `STRESS_TEST`: Simula um pico de uso no servidor para demonstrar a Variável de Condição atuando.