# src/common/protocol.py

class Protocol:
    # Comandos Cliente -> Servidor
    GET_STATUS = "GET_STATUS"
    FAN_ON = "FAN_ON"
    FAN_OFF = "FAN_OFF"
    SET_TEMP_LIMIT = "SET_TEMP_LIMIT"
    FORCE_LOG = "FORCE_LOG"
    STRESS_TEST = "STRESS_TEST"

    # Respostas Servidor -> Cliente (Chaves do JSON)
    KEY_CPU = "cpu"
    KEY_RAM = "ram"
    KEY_TEMP = "temp"
    KEY_FAN = "fan_status"
    KEY_MSG = "message"