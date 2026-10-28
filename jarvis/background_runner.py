import os
import sys
import time
import logging
import threading
from pathlib import Path
import keyboard

from jarvis.config import config, LOGS_DIR
from jarvis.voice.engine import VoiceEngine, START_SOUND

LOG_FILE = LOGS_DIR / "jarvis_background.log"

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

        # 3. Inicializa o assistente e IA sob demanda
        from jarvis.core.agent import JarvisAssistant
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
            logger.info("Modelo de IA não encontrado. Emitindo aviso sonoro imediato...")
            # Som de aviso imediato para dar feedback instantâneo ao usuário
            self.voice.play_sound(START_SOUND)
            try:
                # Usa pyttsx3 se disponível para resposta em 0.1s ou edge-tts
                offline = self.voice.get_offline_engine()
                if offline:
                    offline.say("Detectei que é a sua primeira execução. Vou baixar os modelos de inteligência artificial necessários. Por favor, aguarde alguns instantes.")
                    offline.runAndWait()
                else:
                    self.voice.speak("Detectei que é a sua primeira execução. Vou baixar os modelos de inteligência artificial necessários. Por favor, aguarde alguns instantes.")
            except Exception as e:
                logger.warning(f"Falha ao falar aviso inicial: {e}")

        # Controle de anúncio da porcentagem por voz a cada 5 segundos
        last_spoken_time = [0.0]
        last_spoken_pct = [-1]

        def on_progress(msg: str, pct: int = 0, current_mb: float = 0.0, total_mb: float = 0.0):
            logger.info(f"[Download Status]: {msg}")
            if not needs_llm or pct <= 0:
                return

            now = time.time()
            # Fala se passaram 5 segundos desde a última fala e o percentual mudou
            if now - last_spoken_time[0] >= 5.0 and pct != last_spoken_pct[0]:
                last_spoken_time[0] = now
                last_spoken_pct[0] = pct
                phrase = f"{pct} por cento concluído."
                try:
                    offline = self.voice.get_offline_engine()
                    if offline:
                        offline.say(phrase)
                        offline.runAndWait()
                    else:
                        self.voice.speak(phrase)
                except Exception as e:
                    logger.debug(f"Erro ao falar porcentagem: {e}")

        ensure_models_available(
            llm_model_path=llm_path,
            whisper_model_size=config.WHISPER_MODEL_SIZE,
            status_callback=on_progress
        )

        if needs_llm:
            try:
                offline = self.voice.get_offline_engine()
                if offline:
                    offline.say("Download concluído com sucesso. Finalizando a inicialização.")
                    offline.runAndWait()
                else:
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

        # Verifica atualizações silenciosamente em segundo plano após inicializar
        threading.Thread(target=self._check_for_updates_background, daemon=True).start()

        while self.running:
            time.sleep(1)

    def _check_for_updates_background(self):
        """Verifica se há nova versão no GitHub após 5 segundos da inicialização."""
        time.sleep(5)
        try:
            from jarvis.core.updater import JarvisUpdater
            updater = JarvisUpdater()
            update_info = updater.check_for_update()
            if update_info:
                tag = update_info.get("tag_name", "")
                logger.info(f"Nova versão encontrada em background: {tag}")
                self.voice.speak(f"Senhor, uma nova versão do Jarvis, a {tag}, está disponível para atualização.")
        except Exception as e:
            logger.debug(f"Verificação em background de atualização falhou: {e}")

if __name__ == "__main__":
    daemon = SilentJarvisDaemon()
    daemon.run()
