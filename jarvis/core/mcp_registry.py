import os
import json
import logging
from typing import List, Dict, Any, Callable
from mcp_servers.jarvis_system import server as mcp_system

logger = logging.getLogger("Jarvis.MCPRegistry")

class MCPRegistry:
    """
    Carrega e orquestra ferramentas de servidores MCP para o modelo local.
    Expõe as ferramentas em formato padrão de OpenAI Function Calling / Tool Calling.
    """

    def __init__(self):
        self.tools_map: Dict[str, Callable] = {
            "get_bluetooth_devices": mcp_system.get_bluetooth_devices,
            "set_bluetooth_radio_state": mcp_system.set_bluetooth_radio_state,
            "set_system_volume": mcp_system.set_system_volume,
            "get_battery_status": mcp_system.get_battery_status,
            "get_hardware_telemetry": mcp_system.get_hardware_telemetry,
            "open_app_or_website": mcp_system.open_app_or_website,
            "check_for_updates": mcp_system.check_for_updates
        }

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """Retorna os esquemas de ferramentas compatíveis com Tool Calling do Qwen / LLaMA."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "get_bluetooth_devices",
                    "description": "Retorna os dispositivos Bluetooth conectados, pareados e o nível de bateria de cada um.",
                    "parameters": {"type": "object", "properties": {}, "required": []}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "set_bluetooth_radio_state",
                    "description": "Liga ou desliga o rádio/antena Bluetooth do computador.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "state": {
                                "type": "string",
                                "enum": ["on", "off"],
                                "description": "'on' para ligar ou 'off' para desligar o Bluetooth."
                            }
                        },
                        "required": ["state"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "set_system_volume",
                    "description": "Ajusta o volume do áudio do computador de 0 a 100 porcento.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "level_percent": {
                                "type": "integer",
                                "description": "Nível desejado de volume de 0 a 100."
                            }
                        },
                        "required": ["level_percent"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_battery_status",
                    "description": "Retorna o nível de porcentagem da bateria e se o computador está conectado na tomada.",
                    "parameters": {"type": "object", "properties": {}, "required": []}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_hardware_telemetry",
                    "description": "Retorna uso da CPU, memória RAM em GB e espaço livre em disco.",
                    "parameters": {"type": "object", "properties": {}, "required": []}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "open_app_or_website",
                    "description": "Abre aplicativos (notepad, calculadora, code) ou URLs no navegador.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "target": {
                                "type": "string",
                                "description": "Nome do app ou URL do site."
                            }
                        },
                        "required": ["target"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "check_for_updates",
                    "description": "Verifica se existe uma nova versão ou atualização do Jarvis AI disponível no GitHub.",
                    "parameters": {"type": "object", "properties": {}, "required": []}
                }
            }
        ]

    def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Executa a ferramenta MCP e retorna o resultado em string."""
        if tool_name not in self.tools_map:
            return f"Ferramenta '{tool_name}' não encontrada."

        func = self.tools_map[tool_name]
        try:
            logger.info(f"Executando ferramenta MCP: {tool_name} com args {arguments}")
            if arguments:
                return str(func(**arguments))
            return str(func())
        except Exception as e:
            logger.exception(f"Erro ao executar ferramenta {tool_name}: {e}")
            return f"Erro na execução da ferramenta: {e}"
