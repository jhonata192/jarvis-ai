import os
import json
import hashlib
import logging
import asyncio
import concurrent.futures
from pathlib import Path
from typing import List, Dict, Any, Callable, Optional, Tuple
from jarvis.config import CACHE_DIR
from mcp_servers.jarvis_system import server as mcp_system

logger = logging.getLogger("Jarvis.MCPRegistry")

class MCPRegistry:
    """
    Host / Hub MCP do Jarvis (Padrão Claude Desktop / Cursor / Crush).
    1. Orquestra ferramentas internas nativas (Python, latência zero).
    2. Descobre e executa servidores MCP externos (Node.js via npx, Python via uvx/python) configurados em mcp_servers.json.
    3. Roteia dinamicamente chamadas via embeddings vetoriais locais (all-MiniLM-L6-v2 ONNX) sem limites de ferramentas.
    """

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = self._resolve_config_path(config_path)
        self.internal_tools: Dict[str, Callable] = {
            "get_bluetooth_devices": mcp_system.get_bluetooth_devices,
            "set_bluetooth_radio_state": mcp_system.set_bluetooth_radio_state,
            "set_system_volume": mcp_system.set_system_volume,
            "get_battery_status": mcp_system.get_battery_status,
            "get_hardware_telemetry": mcp_system.get_hardware_telemetry,
            "open_app_or_website": mcp_system.open_app_or_website,
            "check_for_updates": mcp_system.check_for_updates,
            "install_latest_update": mcp_system.install_latest_update
        }
        self.tools_map = self.internal_tools
        self.external_servers: Dict[str, Dict[str, Any]] = {}
        self.external_tools: Dict[str, Dict[str, Any]] = {}
        self._load_mcp_config()

    def _resolve_config_path(self, override_path: Optional[str] = None) -> Path:
        if override_path:
            return Path(override_path)

        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            app_dir = Path(local_app_data) / "Jarvis AI"
            app_dir.mkdir(parents=True, exist_ok=True)
            app_cfg = app_dir / "mcp_servers.json"
            if app_cfg.exists():
                return app_cfg
            default_target = app_cfg
        else:
            default_target = Path("mcp_servers.json")

        local_cfg = Path("mcp_servers.json")
        if local_cfg.exists():
            return local_cfg.resolve()

        try:
            default_content = {
                "mcpServers": {
                    "system": {
                        "command": "internal",
                        "description": "Ferramentas nativas de hardware, volume, bluetooth, bateria e atualizações do Jarvis"
                    }
                }
            }
            with open(default_target, "w", encoding="utf-8") as f:
                json.dump(default_content, f, indent=2, ensure_ascii=False)
            return default_target
        except Exception as e:
            logger.warning(f"Não foi possível criar mcp_servers.json padrão: {e}")
            return Path("mcp_servers.json")

    def _load_mcp_config(self):
        """Lê o arquivo mcp_servers.json e registra servidores externos."""
        if not self.config_path.exists():
            return

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            servers = data.get("mcpServers", {})
            for name, cfg in servers.items():
                cmd = cfg.get("command")
                if cmd == "internal" or name == "system":
                    continue
                self.external_servers[name] = cfg
                logger.info(f"[MCP Hub] Servidor MCP externo registrado: '{name}' ({cmd})")
                self._discover_server_tools(name, cfg)
        except Exception as e:
            logger.warning(f"Erro ao carregar mcp_servers.json ({self.config_path}): {e}")

    def _discover_server_tools(self, server_name: str, cfg: Dict[str, Any]):
        """Executa handshake MCP via stdio e lista as ferramentas fornecidas pelo servidor externo."""
        cmd = cfg.get("command")
        args = cfg.get("args", [])
        env = cfg.get("env")

        async def _async_discover():
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
            params = StdioServerParameters(command=cmd, args=args, env=env)
            async with stdio_client(params) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    res = await session.list_tools()
                    return res.tools

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                tools = executor.submit(asyncio.run, _async_discover()).result(timeout=10)
                for t in tools:
                    self.external_tools[t.name] = {
                        "server_name": server_name,
                        "tool": t,
                        "cfg": cfg,
                        "description": t.description or "",
                        "inputSchema": getattr(t, "input_schema", getattr(t, "inputSchema", {}))
                    }
                    logger.info(f"[MCP Hub] Ferramenta externa descoberta: '{t.name}' (de {server_name})")
        except Exception as e:
            logger.warning(f"[MCP Hub] Falha ao descobrir ferramentas do servidor '{server_name}': {e}")

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """Retorna os esquemas de ferramentas compatíveis com Tool Calling do Qwen / LLaMA."""
        schemas = [
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
                    "description": "Retorna uso da CPU, memória RAM em GB e espaço de armazenamento livre em disco, HD ou SSD.",
                    "intents": [
                        "status do hardware",
                        "uso de memória ram e processador cpu",
                        "como está o uso da cpu",
                        "uso do processador",
                        "consumo de memória e processador",
                        "desempenho da máquina",
                        "telemetria do sistema e computador",
                        "quanto de armazenamento tem disponível no meu HD",
                        "espaço livre em disco",
                        "armazenamento disponível",
                        "quanto espaço tem no HD",
                        "espaço no SSD ou disco rígido",
                        "capacidade e armazenamento livre"
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

        # Acrescenta esquemas das ferramentas externas descobertas via stdio MCP
        for name, meta in self.external_tools.items():
            schemas.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": meta["description"],
                    "parameters": meta["inputSchema"] if meta["inputSchema"] else {"type": "object", "properties": {}, "required": []}
                }
            })

        return schemas

    def _ensure_embeddings(self):
        """
        Carrega ou calcula os vetores semânticos das ferramentas com persistência em disco.
        Se existir em CACHE_DIR / 'tools_embeddings_cache.json' e o hash for idêntico,
        carrega instantaneamente (0ms) sem chamar o modelo ONNX.
        """
        if hasattr(self, "_tools_embeddings") and self._tools_embeddings:
            return

        import numpy as np

        schemas = self.get_tool_schemas()
        chat_anchors = [
            "olá assistente bom dia",
            "tudo bem como vai você",
            "quem é você e o que faz",
            "me conte uma história ou curiosidade",
            "responda esta minha pergunta por favor",
            "qual a sua opinião sobre isso",
            "como está o seu dia hoje"
        ]

        # Gera chave de hash única baseada nos esquemas e âncoras
        serialized = json.dumps({"schemas": schemas, "anchors": chat_anchors}, sort_keys=True, ensure_ascii=False)
        content_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()

        cache_file = CACHE_DIR / "tools_embeddings_cache.json"

        # 1. Tenta carregar do cache em disco
        if cache_file.exists():
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    cache_data = json.load(f)
                if cache_data.get("hash") == content_hash:
                    self._tools_embeddings = {}
                    for fn_name, item in cache_data.get("tools", {}).items():
                        fn_meta = item["fn"]
                        vecs = [np.array(v, dtype=np.float32) for v in item["vecs"]]
                        self._tools_embeddings[fn_name] = (fn_meta, vecs)
                    self._chat_anchors_vecs = [np.array(v, dtype=np.float32) for v in cache_data.get("chat_anchors", [])]
                    logger.debug("[Semantic MCP Router] Vetores carregados do cache em disco (0ms).")
                    return
            except Exception as e:
                logger.debug(f"[Semantic MCP Router] Falha ao ler cache em disco: {e}")

        # 2. Se não houver cache ou se os esquemas mudaram, calcula via ONNX
        from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2
        if not hasattr(self, "_embed_fn") or self._embed_fn is None:
            self._embed_fn = ONNXMiniLM_L6_V2()

        logger.info("[Semantic MCP Router] Calculando vetores semânticos das ferramentas...")
        self._tools_embeddings = {}
        serializable_tools = {}

        for s in schemas:
            fn = s["function"]
            texts_to_embed = [f"{fn['name']}: {fn['description']}"]
            if "intents" in fn and isinstance(fn["intents"], list):
                texts_to_embed.extend(fn["intents"])

            raw_vecs = self._embed_fn(texts_to_embed)
            vecs = [np.array(v, dtype=np.float32) for v in raw_vecs]
            self._tools_embeddings[fn["name"]] = (fn, vecs)
            serializable_tools[fn["name"]] = {
                "fn": fn,
                "vecs": [v.tolist() for v in vecs]
            }

        raw_chat_vecs = self._embed_fn(chat_anchors)
        self._chat_anchors_vecs = [np.array(v, dtype=np.float32) for v in raw_chat_vecs]

        # 3. Salva em disco para inicialização imediata nas próximas vezes
        try:
            cache_payload = {
                "hash": content_hash,
                "tools": serializable_tools,
                "chat_anchors": [v.tolist() for v in self._chat_anchors_vecs]
            }
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(cache_payload, f)
            logger.info(f"[Semantic MCP Router] Cache de embeddings salvo em {cache_file}")
        except Exception as e:
            logger.debug(f"Não foi possível salvar cache de embeddings em disco: {e}")

    def warmup(self):
        """Pré-aquece o roteador semântico e a função de embeddings ONNX."""
        try:
            self._ensure_embeddings()
            if not hasattr(self, "_embed_fn") or self._embed_fn is None:
                from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2
                self._embed_fn = ONNXMiniLM_L6_V2()
            _ = self._embed_fn(["aquecimento"])
        except Exception as e:
            logger.debug(f"Aviso no warmup do MCPRegistry: {e}")

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
            import numpy as np

            self._ensure_embeddings()

            if not hasattr(self, "_embed_fn") or self._embed_fn is None:
                from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2
                self._embed_fn = ONNXMiniLM_L6_V2()

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
        """Executa a ferramenta MCP (interna ou externa via stdio) e retorna o resultado em string."""
        # 1. Ferramentas Internas do Sistema Windows (Zero latência)
        if tool_name in self.internal_tools:
            func = self.internal_tools[tool_name]
            try:
                logger.info(f"Executando ferramenta MCP nativa: {tool_name} com args {arguments}")
                if arguments:
                    return str(func(**arguments))
                return str(func())
            except Exception as e:
                logger.exception(f"Erro ao executar ferramenta interna {tool_name}: {e}")
                return f"Erro na execução da ferramenta: {e}"

        # 2. Ferramentas Externas via MCP Client stdio
        if tool_name in self.external_tools:
            meta = self.external_tools[tool_name]
            cfg = meta["cfg"]
            server_name = meta["server_name"]
            logger.info(f"Executando ferramenta MCP externa '{tool_name}' no servidor '{server_name}'...")
            return self._call_external_tool(cfg, tool_name, arguments)

        return f"Ferramenta '{tool_name}' não encontrada no catálogo MCP."

    def _call_external_tool(self, cfg: Dict[str, Any], tool_name: str, arguments: Dict[str, Any]) -> str:
        """Invoca uma ferramenta em servidor MCP externo via stdio JSON-RPC."""
        cmd = cfg.get("command")
        args = cfg.get("args", [])
        env = cfg.get("env")

        async def _async_call():
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
            params = StdioServerParameters(command=cmd, args=args, env=env)
            async with stdio_client(params) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    res = await session.call_tool(tool_name, arguments)
                    texts = [c.text for c in res.content if hasattr(c, "text")]
                    return "\n".join(texts) if texts else "Operação concluída com sucesso pelo servidor MCP."

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                return executor.submit(asyncio.run, _async_call()).result(timeout=20)
        except Exception as e:
            logger.exception(f"Erro ao chamar ferramenta MCP externa {tool_name}: {e}")
            return f"Erro na execução da ferramenta externa: {e}"

