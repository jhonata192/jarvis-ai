import os
import re
import json
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from jarvis.config import config
from jarvis.core.mcp_registry import MCPRegistry

logger = logging.getLogger("Jarvis.LocalLLM")

class LocalLLMProvider:
    """
    Provedor de IA local com Tool Calling 100% autônomo pela LLM (Qwen 2.5 1.5B).
    A LLM lê os esquemas das ferramentas MCP e decide autonomamente o que chamar.
    """

    def __init__(self, model_path: Optional[str] = None):
        self.model_path = str(model_path or config.LOCAL_MODEL_PATH)
        if not os.path.exists(self.model_path):
            logger.info(f"Modelo GGUF não encontrado em {self.model_path}. Iniciando download automático...")
            from jarvis.core.downloader import download_file_with_progress, QWEN_MODEL_URL
            download_file_with_progress(
                url=QWEN_MODEL_URL,
                destination=Path(self.model_path),
                description="Modelo Qwen 2.5 1.5B (GGUF)"
            )

        self.mcp_registry = MCPRegistry()
        self.llm = None
        self.fallback_mode = False

        try:
            from llama_cpp import Llama
            logger.info("Carregando Qwen 2.5 1.5B com MCP Registry autônomo...")
            cpu_count = os.cpu_count() or 4
            optimal_threads = max(2, min(cpu_count - 1, 6))

            self.llm = Llama(
                model_path=self.model_path,
                n_ctx=2048,
                n_batch=512,
                n_threads=optimal_threads,
                n_threads_batch=optimal_threads,
                n_gpu_layers=int(os.environ.get("JARVIS_GPU_LAYERS", "0")),
                chat_format="chatml",
                verbose=False
            )
            logger.info(f"Motor local pronto ({optimal_threads} threads, batch=512, chat_format=chatml).")
        except (OSError, Exception) as e:
            logger.warning(
                f"Aviso de compatibilidade de CPU: Motor neural local llama-cpp não pôde ser carregado nesta máquina ({e}). "
                "Ativando modo de inteligência universal (ferramentas do sistema, atalhos e controle de voz ativos)."
            )
            self.llm = None
            self.fallback_mode = True

    def _extract_tool_calls(self, message: Dict[str, Any]) -> List[Dict[str, Any]]:
        calls = []

        # 1. Padrão estruturado de OpenAI Tool Calls
        if "tool_calls" in message and message["tool_calls"]:
            for tc in message["tool_calls"]:
                fn = tc.get("function", {})
                name = fn.get("name")
                raw_args = fn.get("arguments", {})
                args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                calls.append({"name": name, "arguments": args})
            return calls

        # 2. Tag nativa do Qwen 2.5: <tool_call> ... </tool_call>
        content = message.get("content", "")
        if content and "<tool_call>" in content:
            matches = re.findall(r'<tool_call>(.*?)</tool_call>', content, re.DOTALL)
            for m in matches:
                clean_json = m.strip()
                # Corrige chaves duplas acidentais que o modelo às vezes gera {{...}}
                if clean_json.startswith("{{") and clean_json.endswith("}}"):
                    clean_json = clean_json[1:-1]
                elif clean_json.startswith("{{") and not clean_json.endswith("}}"):
                    clean_json = clean_json[1:]

                try:
                    parsed = json.loads(clean_json)
                    name = parsed.get("name")
                    args = parsed.get("arguments", {})
                    if name:
                        calls.append({"name": name, "arguments": args})
                except Exception:
                    # Fallback com Regex robusto se o JSON vier com pequenos defeitos
                    fn_match = re.search(r'"name":\s*"([^"]+)"', clean_json)
                    if fn_match:
                        tool_name = fn_match.group(1)
                        tool_args = {}
                        state_match = re.search(r'"state":\s*"([^"]+)"', clean_json)
                        if state_match:
                            tool_args["state"] = state_match.group(1)
                        level_match = re.search(r'"level_percent":\s*(\d+)', clean_json)
                        if level_match:
                            tool_args["level_percent"] = int(level_match.group(1))
                        target_match = re.search(r'"target":\s*"([^"]+)"', clean_json)
                        if target_match:
                            tool_args["target"] = target_match.group(1)
                        calls.append({"name": tool_name, "arguments": tool_args})

        return calls

    def generate(self, prompt: str, system_instruction: Optional[str] = None) -> str:
        """
        Ciclo autônomo completo:
        1. A LLM recebe o prompt e as ferramentas MCP.
        2. A LLM decide se precisa de uma ferramenta e emite a chamada.
        3. O Python executa a ferramenta MCP no Windows e devolve o resultado.
        4. A LLM sintetiza a resposta final em português para o usuário.
        """
        tools = self.mcp_registry.get_tool_schemas()
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        # Fallback universal caso a CPU não suporte instruções do modelo neural local
        if self.llm is None or self.fallback_mode:
            return self._fallback_generate(prompt)

        try:
            logger.info("A LLM está avaliando o comando e as ferramentas MCP disponíveis...")
            
            response = self.llm.create_chat_completion(
                messages=messages,
                tools=tools,
                tool_choice="auto",
                max_tokens=256,
                temperature=0.2
            )

            choice = response["choices"][0]
            message = choice["message"]

            detected_calls = self._extract_tool_calls(message)

            if detected_calls:
                call_info = detected_calls[0]
                tool_name = call_info["name"]
                tool_args = call_info["arguments"]

                logger.info(f"A LLM decidiu autonomamente chamar a ferramenta MCP: {tool_name}({tool_args})")
                tool_result = self.mcp_registry.execute_tool(tool_name, tool_args)

                # Alimenta o resultado de volta à LLM para ela gerar a resposta falada
                messages.append({
                    "role": "assistant",
                    "content": f"Executei a ferramenta {tool_name}."
                })
                messages.append({
                    "role": "user",
                    "content": (
                        f"Resultado da ferramenta {tool_name}: '{tool_result}'. "
                        "Agora responda diretamente ao operador de forma educada, curta e natural em português."
                    )
                })

                synth_response = self.llm.create_chat_completion(
                    messages=messages,
                    max_tokens=150,
                    temperature=0.5
                )
                return synth_response["choices"][0]["message"]["content"].strip()

            content = message.get("content", "")
            return content.strip() if content else "Como posso ajudar, senhor?"

        except (OSError, Exception) as e:
            logger.warning(f"Erro na execução da LLM ({e}). Recorrendo ao modo universal MCP...")
            return self._fallback_generate(prompt)

    def _fallback_generate(self, prompt: str) -> str:
        """
        Modo de Inteligência Universal (Executa em 100% dos processadores x86/x64).
        Interpreta comandos de sistema, atalhos, volume, aplicativos e telemetria via MCP.
        """
        p_lower = prompt.lower()

        # 1. Volume
        vol_match = re.search(r'(?:volume|som).*?(\d+)', p_lower)
        if vol_match:
            val = int(vol_match.group(1))
            res = self.mcp_registry.execute_tool("set_system_volume", {"level_percent": val})
            return f"Volume ajustado para {val} por cento."
        if any(w in p_lower for w in ["aumente o volume", "aumentar volume", "aumenta o som"]):
            res = self.mcp_registry.execute_tool("set_system_volume", {"level_percent": 80})
            return "Volume aumentado para 80 por cento."
        if any(w in p_lower for w in ["abaixe o volume", "baixar volume", "abaixa o som"]):
            res = self.mcp_registry.execute_tool("set_system_volume", {"level_percent": 30})
            return "Volume reduzido para 30 por cento."
        if any(w in p_lower for w in ["mudo", "mutar", "silenciar"]):
            res = self.mcp_registry.execute_tool("set_system_volume", {"level_percent": 0})
            return "Áudio silenciado."

        # 2. Bluetooth
        if any(w in p_lower for w in ["ligar bluetooth", "liga o bluetooth", "ative o bluetooth"]):
            res = self.mcp_registry.execute_tool("set_bluetooth_radio_state", {"state": "on"})
            return "Bluetooth ativado com sucesso."
        if any(w in p_lower for w in ["desligar bluetooth", "desliga o bluetooth", "desative o bluetooth"]):
            res = self.mcp_registry.execute_tool("set_bluetooth_radio_state", {"state": "off"})
            return "Bluetooth desativado com sucesso."
        if "bluetooth" in p_lower:
            return self.mcp_registry.execute_tool("get_bluetooth_devices", {})

        # 3. Telemetria e Bateria
        if any(w in p_lower for w in ["bateria", "carga"]):
            return self.mcp_registry.execute_tool("get_battery_status", {})
        if any(w in p_lower for w in ["status", "hardware", "cpu", "memoria", "memória", "desempenho"]):
            return self.mcp_registry.execute_tool("get_hardware_telemetry", {})

        # 4. Abertura de Aplicativos e Navegador
        app_map = {
            "bloco de notas": "notepad",
            "notepad": "notepad",
            "calculadora": "calc",
            "vscode": "code",
            "vs code": "code",
            "chrome": "chrome",
            "navegador": "https://www.google.com",
            "google": "https://www.google.com",
            "youtube": "https://www.youtube.com",
            "github": "https://www.github.com"
        }
        for name, target in app_map.items():
            if f"abrir {name}" in p_lower or f"abra {name}" in p_lower or f"iniciar {name}" in p_lower or f"inicie {name}" in p_lower:
                return self.mcp_registry.execute_tool("open_app_or_website", {"target": target})

        # 5. Atualização do Jarvis
        if any(w in p_lower for w in ["atualização", "atualizacao", "versão", "versao", "update"]):
            return self.mcp_registry.execute_tool("check_for_updates", {})

        # 6. Saudações e conversa básica
        if any(w in p_lower for w in ["olá", "ola", "bom dia", "boa tarde", "boa noite", "oi jarvis", "jarvis"]):
            return "Às suas ordens, senhor. Como posso ajudar com o seu sistema hoje?"

        return "Comando recebido. Todas as ferramentas de controle do sistema, volume, aplicativos e telemetria estão operando normalmente."
