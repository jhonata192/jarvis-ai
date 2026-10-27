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
        # 1. Inicia voz primeiro para poder falar avisos ao usuário se necessário
        self.voice = VoiceEngine()
        
        # 2. Verifica se os modelos precisam ser baixados
        self._check_and_download_models()

        # 3. Inicializa o assistente e IA
        self.agent = JarvisAssistant()
        self.is_processing = False
        self.running = True

    def _check_and_download_models(self):
        """Verifica se o modelo da IA e o Whisper estão baixados, avisando o usuário por voz."""
        from jarvis.config import config
        from jarvis.core.downloader import ensure_models_available

        llm_path = Path(config.LOCAL_MODEL_PATH)
        needs_llm = not llm_path.exists() and config.AI_PROVIDER == "local"

        if needs_llm:
            logger.info("Modelo de IA não encontrado. Falando com o usuário...")
            try:
                self.voice.speak("Detectei que é a sua primeira execução. Vou baixar os modelos de inteligência artificial necessários. Por favor, aguarde alguns instantes.")
            except Exception:
                pass

        def on_progress(msg: str):
            logger.info(f"[Download Status]: {msg}")

        ensure_models_available(
            llm_model_path=llm_path,
            whisper_model_size=config.WHISPER_MODEL_SIZE,
            status_callback=on_progress
        )

        if needs_llm:
            try:
                self.voice.speak("Download concluído com sucesso. Finalizando a inicialização.")
            except Exception:
                pass

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
