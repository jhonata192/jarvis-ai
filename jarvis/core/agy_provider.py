import subprocess
import shutil
import logging
import sys
import json
from typing import Optional, Generator
from jarvis.config import config

logger = logging.getLogger("Jarvis.AgyProvider")

class AgyProvider:
    """
    Interface otimizada para o Antigravity CLI (agy) de alta velocidade com suporte a Streaming de tokens.
    """

    def __init__(self, bin_path: Optional[str] = None):
        self.bin_path = bin_path or config.AGY_BIN_PATH
        self._check_binary()

    def _check_binary(self):
        resolved = shutil.which(self.bin_path)
        if not resolved:
            raise FileNotFoundError(
                f"O executável '{self.bin_path}' não foi encontrado no PATH do sistema. "
                "Certifique-se de que a CLI agy está instalada."
            )

    def generate_stream(self, prompt: str, system_instruction: Optional[str] = None, timeout: Optional[int] = None) -> Generator[str, None, None]:
        """
        Executa o agy com output stream-json gerando tokens de texto em tempo real assim que são produzidos.
        """
        full_prompt = prompt
        if system_instruction:
            full_prompt = f"System: {system_instruction}\n\nUser: {prompt}"

        cmd = [
            self.bin_path,
            "-p",
            full_prompt,
            "--output-format", "stream-json",
            "--model", config.AGY_MODEL,
            "--effort", config.AGY_EFFORT
        ]

        if config.AGY_DANGEROUSLY_SKIP_PERMISSIONS:
            cmd.append("--dangerously-skip-permissions")

        creationflags = 0
        startupinfo = None
        if sys.platform == "win32":
            creationflags = subprocess.CREATE_NO_WINDOW
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE

        process = None
        try:
            logger.info(f"Iniciando stream com AGY ({config.AGY_MODEL})...")
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=creationflags,
                startupinfo=startupinfo,
                bufsize=1
            )

            for line in process.stdout:
                line_str = line.strip()
                if not line_str:
                    continue
                try:
                    data = json.loads(line_str)
                    event_type = data.get("event")
                    if event_type == "step_update":
                        step = data.get("step_update", {})
                        delta = step.get("text_delta")
                        if delta:
                            yield delta
                except json.JSONDecodeError:
                    continue

            process.wait()

        except Exception as e:
            logger.exception(f"Erro durante streaming do agy: {e}")
            yield f"Desculpe, ocorreu uma instabilidade: {e}"
        finally:
            if process and process.poll() is None:
                try:
                    process.terminate()
                except Exception:
                    pass

    def generate(self, prompt: str, system_instruction: Optional[str] = None, timeout: Optional[int] = None) -> str:
        """Coleta o stream completo como fallback síncrono."""
        tokens = []
        for t in self.generate_stream(prompt, system_instruction, timeout):
            tokens.append(t)
        return "".join(tokens).strip()
