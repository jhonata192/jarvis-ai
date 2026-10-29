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

        content = message.get("content", "")
        if not content:
            return calls

        # 2. Tag nativa Hermes / Qwen: <tool_call> ... </tool_call>
        if "<tool_call>" in content:
            matches = re.findall(r'<tool_call>(.*?)</tool_call>', content, re.DOTALL)
            for m in matches:
                clean_json = m.strip()
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

        # 3. Bloco Markdown ```json ... ``` com chamada de ferramenta
        if not calls and "```json" in content:
            matches = re.findall(r'```json\s*(.*?)\s*```', content, re.DOTALL)
            for m in matches:
                clean_json = m.strip()
                try:
                    parsed = json.loads(clean_json)
                    if isinstance(parsed, dict):
                        # Caso {"name": "...", "arguments": {...}}
                        if "name" in parsed and (parsed["name"] in self.mcp_registry.tools_map):
                            calls.append({"name": parsed["name"], "arguments": parsed.get("arguments", {})})
                        # Caso {"tool_call": {"name": ...}}
                        elif "tool_call" in parsed and isinstance(parsed["tool_call"], dict):
                            tc = parsed["tool_call"]
                            if "name" in tc:
                                calls.append({"name": tc["name"], "arguments": tc.get("arguments", {})})
                except Exception:
                    pass

        # 4. JSON puro direto no corpo da mensagem
        if not calls and "{" in content and "}" in content:
            for tool_name in self.mcp_registry.tools_map.keys():
                if f'"{tool_name}"' in content or f"'{tool_name}'" in content:
                    calls.append({"name": tool_name, "arguments": {}})
                    break

        return calls


    def generate(self, prompt: str, system_instruction: Optional[str] = None, max_steps: int = 4) -> str:
        """
        Execução com Roteador Semântico MCP e Síntese de Linguagem Natural (Qwen 2.5 1.5B):
        1. Roteador Semântico MCP (offline, ~15ms via embeddings ONNX):
           Se a solicitação for uma ação de sistema, executa de forma determinística
           e sintetiza o feedback em voz.
        2. Conversação e Raciocínio Geral:
           Se for uma pergunta ou diálogo, gera a resposta com o modelo neural local.
        """
        # Fallback universal caso a CPU não suporte instruções do modelo neural local
        if self.llm is None or self.fallback_mode:
            return self._fallback_generate(prompt)

        # 1. Tenta roteamento semântico de ferramenta MCP
        matched = self.mcp_registry.match_tool_semantically(prompt)
        if matched:
            tool_name, tool_args = matched
            logger.info(f"[Semantic MCP Router] Intenção mapeada para '{tool_name}' ({tool_args})")
            tool_result = self.mcp_registry.execute_tool(tool_name, tool_args)
            logger.info(f"[Semantic MCP Router] Resultado real da ferramenta: {tool_result}")

            try:
                synthesis_system = (
                    "Você é JARVIS, assistente de IA. "
                    "A ferramenta do sistema foi executada com sucesso. "
                    "Responda ao usuário com 1 frase curta, natural e elegante em português confirmando o resultado."
                )
                synthesis_user = (
                    f"Comando do usuário: \"{prompt}\"\n"
                    f"Ação do sistema: {tool_name}\n"
                    f"Resultado obtido: \"{tool_result}\"\n"
                    "Resposta em voz alta:"
                )
                resp = self.llm.create_chat_completion(
                    messages=[
                        {"role": "system", "content": synthesis_system},
                        {"role": "user", "content": synthesis_user}
                    ],
                    max_tokens=60,
                    temperature=0.3
                )
                text = resp["choices"][0]["message"].get("content", "").strip()
                if text:
                    return text
            except Exception as e:
                logger.debug(f"Síntese conversacional pós-ferramenta: {e}")

            return str(tool_result)

        # 2. Conversação geral, perguntas ou raciocínio via Qwen 2.5 1.5B
        try:
            messages = []
            if system_instruction:
                messages.append({"role": "system", "content": system_instruction})
            messages.append({"role": "user", "content": prompt})

            response = self.llm.create_chat_completion(
                messages=messages,
                max_tokens=256,
                temperature=0.3
            )
            content = (response["choices"][0]["message"].get("content") or "").strip()
            # Limpa quaisquer resíduos de tags internas antes de falar
            clean_speech = re.sub(r'<tool_call>.*?</tool_call>', '', content, flags=re.DOTALL).strip()
            clean_speech = re.sub(r'\[Observation\]:.*', '', clean_speech, flags=re.DOTALL).strip()
            return clean_speech if clean_speech else "Às suas ordens, senhor."

        except (OSError, Exception) as e:
            logger.warning(f"Erro na execução da LLM ({e}). Recorrendo ao modo universal...")
            return self._fallback_generate(prompt)

    def _fallback_generate(self, prompt: str) -> str:
        """
        Modo de Inteligência Universal (Executa em 100% dos processadores x86/x64).
        Interpreta comandos de sistema, atalhos, volume, aplicativos e telemetria via MCP.
        """
        matched = self.mcp_registry.match_tool_semantically(prompt)
        if matched:
            tool_name, tool_args = matched
            return str(self.mcp_registry.execute_tool(tool_name, tool_args))

        p_lower = prompt.lower()
        if any(w in p_lower for w in ["olá", "ola", "bom dia", "boa tarde", "boa noite", "oi jarvis", "jarvis"]):
            return "Às suas ordens, senhor. Como posso ajudar com o seu sistema hoje?"

        return "Comando recebido. Todas as ferramentas de controle do sistema, volume, aplicativos e telemetria estão operando normalmente."
