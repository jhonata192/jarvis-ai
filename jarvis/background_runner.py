import os
import sys
import time
import logging
import threading
from pathlib import Path
import keyboard

from jarvis.core.agent import JarvisAssistant
from jarvis.voice.engine import VoiceEngine

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "jarvis_background.log"

logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    encoding="utf-8"
)

logger = logging.getLogger("Jarvis.BackgroundDaemon")

HOTKEY = "ctrl+alt+j"

class SilentJarvisDaemon:
    """
    Executa o Jarvis de forma 100% invisível em background.
    Fala fluida, contínua e natural sem pausas artificiais.
    """

    def __init__(self):
        logger.info("Iniciando Jarvis Daemon (modo fala natural contínua)...")
        self.agent = JarvisAssistant()
        self.voice = VoiceEngine()
        self.is_processing = False
        self.running = True

    def trigger_hotkey(self):
        if self.is_processing:
            logger.warning("Ativação ignorada: Jarvis já está processando.")
            return

        threading.Thread(target=self._process_interaction, daemon=True).start()

    def _process_interaction(self):
        self.is_processing = True
        logger.info("Atalho global detectado (Ctrl+Alt+J). Iniciando atendimento por voz...")

        try:
            self.voice.speak("Pois não, senhor?")
            # Microfone com tolerância para falar calmamente
            user_text = self.voice.listen()

            if user_text:
                logger.info(f"Comando recebido: {user_text}")
                
                # Gera a resposta com AGY + RAG
                response = self.agent.ask(user_text)
                logger.info(f"Resposta gerada: {response[:100]}...")
                
                # Fala a resposta completa de uma só vez com ritmo natural
                self.voice.speak(response)
            else:
                logger.info("Nenhuma fala detectada pelo microfone.")
        except Exception as e:
            logger.exception(f"Erro durante atendimento de voz: {e}")
            try:
                self.voice.speak("Desculpe, ocorreu uma instabilidade momentânea.")
            except Exception:
                pass
        finally:
            self.is_processing = False

    def run(self):
        keyboard.add_hotkey(HOTKEY, self.trigger_hotkey, suppress=False)
        logger.info(f"Atalho {HOTKEY} registrado com sucesso.")

        try:
            self.voice.speak("Sistemas Jarvis operacionais.")
        except Exception as e:
            logger.warning(f"Falha no áudio de inicialização: {e}")

        while self.running:
            time.sleep(1)

if __name__ == "__main__":
    daemon = SilentJarvisDaemon()
    daemon.run()
