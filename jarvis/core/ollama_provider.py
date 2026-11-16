import os
import re
import json
import logging
import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional, List, Dict, Any
from jarvis.config import config, USER_DATA_DIR
from jarvis.core.mcp_registry import MCPRegistry

logger = logging.getLogger("Jarvis.Ollama")

OLLAMA_DEFAULT_HOST = "http://127.0.0.1:11434"
OLLAMA_DEFAULT_MODEL = "qwen2.5:1.5b"

class OllamaProvider:
    """
    Provedor de IA com Ollama como gerenciador externo e local (100% offline).
    Comunica via API REST local (OpenAI Compatible em http://127.0.0.1:11434).
    """

    def __init__(self, model: Optional[str] = None, host: Optional[str] = None):
        self.model = model or OLLAMA_DEFAULT_MODEL
        self.host = (host or OLLAMA_DEFAULT_HOST).rstrip("/")
        self.mcp_registry = MCPRegistry()
        self.fallback_mode = False

        logger.info(f"Inicializando Provedor Ollama ({self.model} em {self.host})...")
        if not self.is_running():
            logger.info("Serviço do Ollama não detectado ativo. Tentando iniciar automaticamente...")
            self.ensure_running()

        if self.is_running():
            logger.info(f"Ollama pronto e operacional ({self.host}).")
        else:
            logger.warning("Não foi possível conectar ao Ollama no momento. Modo de contingência universal ativo.")
            self.fallback_mode = True

    def _find_ollama_executable(self) -> Optional[Path]:
        """Localiza o binário ou aplicativo do Ollama no sistema Windows."""
        which_path = shutil.which("ollama")
        if which_path:
            return Path(which_path)

        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            base = Path(local_app_data) / "Programs" / "Ollama"
            app_exe = base / "ollama app.exe"
            if app_exe.exists():
                return app_exe
            cli_exe = base / "ollama.exe"
            if cli_exe.exists():
                return cli_exe

        program_files = os.environ.get("ProgramFiles")
        if program_files:
            p_exe = Path(program_files) / "Ollama" / "ollama.exe"
            if p_exe.exists():
                return p_exe

        return None

    def is_running(self) -> bool:
        """Verifica se o servidor do Ollama está respondendo na porta 11434."""
        import urllib.request
        try:
            req = urllib.request.Request(f"{self.host}/api/tags", headers={"User-Agent": "JarvisAI"})
            with urllib.request.urlopen(req, timeout=2) as resp:
                return resp.status == 200
        except Exception:
            return False

    def ensure_running(self, timeout_sec: int = 15) -> bool:
        """Inicia o processo do Ollama em segundo plano se ainda não estiver rodando."""
        if self.is_running():
            self.fallback_mode = False
            return True

        exe_path = self._find_ollama_executable()
        if not exe_path:
            logger.warning("Executável do Ollama não encontrado nos caminhos padrão do Windows.")
            return False

        try:
            logger.info(f"Iniciando Ollama em background: {exe_path}")
            flags = 0
            if os.name == "nt":
                flags = subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS

            if "app.exe" in exe_path.name.lower():
                subprocess.Popen([str(exe_path)], creationflags=flags)
            else:
                subprocess.Popen([str(exe_path), "serve"], creationflags=flags)

            t0 = time.time()
            while time.time() - t0 < timeout_sec:
                time.sleep(1)
                if self.is_running():
                    logger.info("Ollama iniciado e respondendo na porta 11434 com sucesso.")
                    self.fallback_mode = False
                    return True
        except Exception as e:
            logger.warning(f"Erro ao tentar disparar processo do Ollama: {e}")

        return False

    def create_chat_completion(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 256,
        temperature: float = 0.3
    ) -> Dict[str, Any]:
        """
        Executa chamada de chat completion compatível com OpenAI via endpoint do Ollama.
        POST http://127.0.0.1:11434/v1/chat/completions
        """
        import urllib.request
        import urllib.error

        if not self.is_running():
            self.ensure_running(timeout_sec=5)

        url = f"{self.host}/v1/chat/completions"
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False
        }
        data_bytes = json.dumps(payload).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=data_bytes,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "JarvisAI"
            },
            method="POST"
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
                return resp_data
        except Exception as e:
            logger.warning(f"Erro na requisição ao Ollama ({url}): {e}")
            raise e

    def synthesize_tool_response(self, user_prompt: str, tool_name: str, tool_result: Any) -> str:
        """Sintetiza uma resposta de voz elegante no estilo britânico do JARVIS."""
        raw_result = str(tool_result).strip()
        if not raw_result:
            return "Ação executada com sucesso, senhor."

        synthesis_system = (
            "Você é JARVIS, o assistente virtual pessoal e leal do usuário. "
            "A ação solicitada foi executada no sistema operacional. "
            "Comunique o resultado ao usuário com cortesia britânica (tratando por 'senhor' ou com respeito), "
            "de forma fluida, natural, concisa e elegante (1 frase curta) em português brasileiro. "
            "Nunca soe como um comando técnico de terminal nem mencione nomes de funções ou código."
        )
        synthesis_user = (
            f"Solicitação do usuário: \"{user_prompt}\"\n"
            f"Ação do sistema executada: {tool_name}\n"
            f"Resultado obtido: \"{raw_result}\"\n"
            "Responda ao usuário com elegância e naturalidade:"
        )

        try:
            resp = self.create_chat_completion(
                messages=[
                    {"role": "system", "content": synthesis_system},
                    {"role": "user", "content": synthesis_user}
                ],
                max_tokens=64,
                temperature=0.3
            )
            text = resp["choices"][0]["message"].get("content", "").strip()
            if text:
                return text
        except Exception as e:
            logger.debug(f"Falha na síntese do Ollama pós-ferramenta: {e}")

        return raw_result

    def generate(self, prompt: str, system_instruction: Optional[str] = None, max_steps: int = 4) -> str:
        """
        Gera a resposta do assistente:
        1. Se for comando de sistema direto, executa a ferramenta MCP e sintetiza resposta de áudio com Ollama.
        2. Se for pergunta ou diálogo, gera texto completo via Qwen 2.5 no Ollama.
        3. Caso o Ollama esteja inacessível, recorre ao modo universal de fallback.
        """
        # Se estiver em fallback por indisponibilidade do Ollama
        if self.fallback_mode and not self.is_running():
            return self._fallback_generate(prompt)

        # 1. Tenta roteamento semântico apenas para comandos diretos sem contexto de diálogo agregado
        if "Pergunta atual do operador:" not in prompt and "Diálogo recente imediato:" not in prompt:
            matched = self.mcp_registry.match_tool_semantically(prompt)
            if matched:
                tool_name, tool_args = matched
                logger.info(f"[Semantic MCP Router] Intenção mapeada para '{tool_name}' ({tool_args})")
                tool_result = self.mcp_registry.execute_tool(tool_name, tool_args)
                logger.info(f"[Semantic MCP Router] Resultado real da ferramenta: {tool_result}")
                return self.synthesize_tool_response(prompt, tool_name, tool_result)

        # 2. Conversação geral, perguntas ou raciocínio via Ollama
        try:
            messages = []
            if system_instruction:
                messages.append({"role": "system", "content": system_instruction})
            messages.append({"role": "user", "content": prompt})

            response = self.create_chat_completion(
                messages=messages,
                max_tokens=256,
                temperature=0.3
            )
            content = (response["choices"][0]["message"].get("content") or "").strip()
            # Limpa resíduos de tags internas se houver
            clean_speech = re.sub(r'<tool_call>.*?</tool_call>', '', content, flags=re.DOTALL).strip()
            clean_speech = re.sub(r'\[Observation\]:.*', '', clean_speech, flags=re.DOTALL).strip()
            return clean_speech if clean_speech else "Às suas ordens, senhor."

        except Exception as e:
            logger.warning(f"Erro na geração com Ollama ({e}). Recorrendo ao modo universal...")
            return self._fallback_generate(prompt)

    def _fallback_generate(self, prompt: str) -> str:
        """
        Modo de contingência universal: extrai a fala atual do operador sem contaminação do histórico.
        """
        clean_user_prompt = prompt
        if "Pergunta atual do operador:" in prompt:
            clean_user_prompt = prompt.split("Pergunta atual do operador:")[-1].strip()

        matched = self.mcp_registry.match_tool_semantically(clean_user_prompt)
        if matched:
            tool_name, tool_args = matched
            return str(self.mcp_registry.execute_tool(tool_name, tool_args))

        p_lower = clean_user_prompt.lower()
        if any(w in p_lower for w in ["olá", "ola", "bom dia", "boa tarde", "boa noite", "oi jarvis", "jarvis"]):
            return "Às suas ordens, senhor. Como posso ajudar com o seu sistema hoje?"
        if any(w in p_lower for w in ["como você está", "como voce esta", "como vai", "tudo bem", "como está você"]):
            return "Estou operando perfeitamente e pronto para ajudar, senhor. Em que posso ser útil?"

        return "Comando recebido. Todas as ferramentas de controle do sistema, volume, aplicativos e telemetria estão operando normalmente."
