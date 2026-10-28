import os
import re
import json
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from llama_cpp import Llama
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

        logger.info(f"Carregando Qwen 2.5 1.5B com MCP Registry autônomo...")
        import os
        cpu_count = os.cpu_count() or 4
        optimal_threads = max(2, min(cpu_count - 1, 6))

        self.llm = Llama(
            model_path=self.model_path,
            n_ctx=2048,
            n_batch=512,
            n_threads=optimal_threads,
            n_threads_batch=optimal_threads,
            n_gpu_layers=int(os.environ.get("JARVIS_GPU_LAYERS", "0")),
            verbose=False
        )
        self.mcp_registry = MCPRegistry()
        logger.info(f"Motor local pronto ({optimal_threads} threads, batch=512).")

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

        except Exception as e:
            logger.exception(f"Erro no ciclo de Tool Calling autônomo da LLM: {e}")
            return f"Ocorreu uma falha no processamento: {e}"
