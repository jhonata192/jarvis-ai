import os
import json
import logging
from typing import List, Dict, Any, Callable, Optional, Tuple
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
            "check_for_updates": mcp_system.check_for_updates,
            "install_latest_update": mcp_system.install_latest_update
        }

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """Retorna os esquemas de ferramentas compatíveis com Tool Calling do Qwen / LLaMA."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "get_bluetooth_devices",
                    "description": "Retorna os dispositivos Bluetooth conectados, pareados e o nível de bateria de cada um.",
                    "intents": [
                        "listar aparelhos bluetooth conectados",
                        "quais dispositivos bluetooth estão pareados",
                        "ver lista de aparelhos bluetooth",
                        "fones bluetooth conectados"
                    ],
                    "parameters": {"type": "object", "properties": {}, "required": []}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "set_bluetooth_radio_state",
                    "description": "Liga ou desliga o rádio ou antena Bluetooth do computador.",
                    "intents": [
                        "ligar o bluetooth",
                        "desligar o bluetooth",
                        "ativar bluetooth",
                        "desativar bluetooth",
                        "liga bluetooth",
                        "desliga bluetooth",
                        "desconecte o bluetooth"
                    ],
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
                    "description": "Ajusta o volume do áudio do computador de 0 a 100 porcento ou silencia o som.",
                    "intents": [
                        "ajustar volume",
                        "aumentar o som",
                        "abaixar volume",
                        "mutar áudio",
                        "colocar som no mudo",
                        "definir volume em porcentagem"
                    ],
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
                    "intents": [
                        "nível da bateria",
                        "porcentagem de carga da bateria",
                        "como está a bateria",
                        "quanto de bateria tem",
                        "computador está na tomada"
                    ],
                    "parameters": {"type": "object", "properties": {}, "required": []}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_hardware_telemetry",
                    "description": "Retorna uso da CPU, memória RAM em GB e espaço livre em disco.",
                    "intents": [
                        "status do hardware",
                        "uso de memória ram e processador cpu",
                        "desempenho da máquina",
                        "telemetria do sistema e computador"
                    ],
                    "parameters": {"type": "object", "properties": {}, "required": []}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "open_app_or_website",
                    "description": "Abre aplicativos locais (bloco de notas, calculadora, vscode) ou sites da web.",
                    "intents": [
                        "abrir bloco de notas",
                        "abrir calculadora",
                        "abrir navegador",
                        "abrir aplicativo ou programa",
                        "abrir vscode",
                        "abrir site na internet"
                    ],
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
                    "intents": [
                        "verificar se há atualizações",
                        "checar se tem versão nova",
                        "tem update disponível",
                        "verifique atualizações disponíveis"
                    ],
                    "parameters": {"type": "object", "properties": {}, "required": []}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "install_latest_update",
                    "description": "Baixa e instala a atualização ou nova versão do Jarvis AI.",
                    "intents": [
                        "instalar atualização",
                        "atualize",
                        "atualizar agora",
                        "baixar nova versão",
                        "baixe a nova versão",
                        "fazer update do sistema",
                        "baixe a atualização"
                    ],
                    "parameters": {"type": "object", "properties": {}, "required": []}
                }
            }
        ]

    def match_tool_semantically(self, user_query: str, threshold: float = 0.52) -> Optional[Tuple[str, Dict[str, Any]]]:
        """
        Roteador Semântico MCP (Padrão Claude Code / Embeddings):
        Analisa a intenção da fala do usuário contra as descrições em linguagem natural
        e intenções exemplares de TODAS as ferramentas MCP registradas.
        Retorna (tool_name, arguments) se houver correspondência semântica clara acima de conversação.
        """
        import re
        q_clean = user_query.strip()
        q_lower = q_clean.lower()
        if not q_clean:
            return None

        # 1. Resolução semântica via Embedding ONNX
        best_tool = None
        best_score = -1.0
        chat_score = -1.0

        try:
            from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2
            import numpy as np

            if not hasattr(self, "_embed_fn") or self._embed_fn is None:
                self._embed_fn = ONNXMiniLM_L6_V2()

            if not hasattr(self, "_tools_embeddings"):
                # Pré-calcula os vetores semânticos das ferramentas cadastradas
                self._tools_embeddings = {}
                schemas = self.get_tool_schemas()
                for s in schemas:
                    fn = s["function"]
                    texts_to_embed = [f"{fn['name']}: {fn['description']}"]
                    if "intents" in fn and isinstance(fn["intents"], list):
                        texts_to_embed.extend(fn["intents"])

                    vecs = [np.array(v, dtype=np.float32) for v in self._embed_fn(texts_to_embed)]
                    self._tools_embeddings[fn["name"]] = (fn, vecs)

                # Âncoras conversacionais gerais para evitar falsos positivos em saudações ou papo comum
                chat_anchors = [
                    "olá assistente bom dia",
                    "tudo bem como vai você",
                    "quem é você e o que faz",
                    "me conte uma história ou curiosidade",
                    "responda esta minha pergunta por favor",
                    "qual a sua opinião sobre isso",
                    "como está o seu dia hoje"
                ]
                self._chat_anchors_vecs = [np.array(v, dtype=np.float32) for v in self._embed_fn(chat_anchors)]

            q_vec = np.array(self._embed_fn([q_clean])[0], dtype=np.float32)
            q_norm = np.linalg.norm(q_vec)

            if q_norm > 0:
                # Pontuação de conversa geral
                chat_score = max(
                    float(np.dot(q_vec, cv) / (q_norm * np.linalg.norm(cv)))
                    for cv in self._chat_anchors_vecs
                )

                # Pontuação das ferramentas MCP
                for t_name, (fn_meta, t_vecs) in self._tools_embeddings.items():
                    for t_vec in t_vecs:
                        t_norm = np.linalg.norm(t_vec)
                        if t_norm > 0:
                            sim = float(np.dot(q_vec, t_vec) / (q_norm * t_norm))
                            if sim > best_score:
                                best_score = sim
                                best_tool = t_name

        except Exception as e:
            logger.debug(f"Roteador semântico ONNX operando em modo padrão: {e}")

        # Se atingiu o limiar de similaridade semântica e superou a âncora de conversa livre
        if best_tool and best_score >= threshold and best_score > chat_score:
            logger.info(f"[Semantic MCP Router] Intenção mapeada para '{best_tool}' (similaridade: {best_score:.3f}, chat: {chat_score:.3f})")
            args = self._infer_arguments_for_tool(best_tool, q_lower)
            return (best_tool, args)

        return None

    def _infer_arguments_for_tool(self, tool_name: str, query: str) -> Dict[str, Any]:
        """Extrai argumentos dinâmicos (como percentual de volume ou on/off) para a ferramenta MCP."""
        import re
        args = {}

        if tool_name == "set_system_volume":
            vol_match = re.search(r'(\d+)', query)
            if vol_match:
                args["level_percent"] = max(0, min(100, int(vol_match.group(1))))
            elif any(w in query for w in ["mudo", "mute", "silenci", "zero"]):
                args["level_percent"] = 0
            elif any(w in query for w in ["aument", "mais", "alto", "suba"]):
                args["level_percent"] = 80
            elif any(w in query for w in ["abaix", "menos", "baixo", "diminu"]):
                args["level_percent"] = 30
            else:
                args["level_percent"] = 50

        elif tool_name == "set_bluetooth_radio_state":
            if any(w in query for w in ["deslig", "desativ", "apag", "desconect", "off"]):
                args["state"] = "off"
            else:
                args["state"] = "on"

        elif tool_name == "open_app_or_website":
            # Extrai o nome do aplicativo ou site
            for app in ["notepad", "bloco de notas", "calc", "calculadora", "code", "vscode", "terminal", "powershell"]:
                if app in query:
                    args["target"] = app
                    break
            if "target" not in args:
                # Procura por URLs ou termos comuns
                url_match = re.search(r'(https?://\S+)', query)
                if url_match:
                    args["target"] = url_match.group(1)
                elif "google" in query:
                    args["target"] = "https://www.google.com"
                elif "youtube" in query:
                    args["target"] = "https://www.youtube.com"
                elif "github" in query:
                    args["target"] = "https://www.github.com"
                else:
                    words = query.split()
                    args["target"] = words[-1] if words else "notepad"

        return args

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

