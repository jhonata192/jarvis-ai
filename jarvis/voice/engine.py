import io
import os
import asyncio
import tempfile
import logging
from pathlib import Path
from typing import Optional
from jarvis.config import config

logger = logging.getLogger("Jarvis.Voice")

SOUNDS_DIR = Path(__file__).resolve().parent.parent / "assets" / "sounds"
START_SOUND = SOUNDS_DIR / "listen_start.wav"
STOP_SOUND = SOUNDS_DIR / "listen_stop.wav"

class VoiceEngine:
    """
    Controlador de voz do Jarvis com fala fluida e contínua (sem pausas quebradas).
    """

    def __init__(self):
        self.tts_engine = config.TTS_ENGINE
        self.offline_engine = None
        self.whisper_model = None

    def get_offline_engine(self):
        """Inicializa pyttsx3 somente se for necessário (fallback)."""
        if self.offline_engine is None:
            try:
                import pyttsx3
                self.offline_engine = pyttsx3.init()
                self.offline_engine.setProperty('rate', 190)
            except Exception as e:
                logger.warning(f"Engine pyttsx3 não disponível: {e}")
                self.offline_engine = False
        return self.offline_engine if self.offline_engine is not False else None

    def get_whisper_model(self):
        """Inicializa o modelo Whisper sob demanda (lazy loading) para inicialização instantânea."""
        if self.whisper_model is None and config.STT_ENGINE == "whisper":
            try:
                from faster_whisper import WhisperModel
                logger.info(f"Carregando Whisper ({config.WHISPER_MODEL_SIZE}) em {config.WHISPER_DEVICE}...")
                self.whisper_model = WhisperModel(
                    config.WHISPER_MODEL_SIZE,
                    device=config.WHISPER_DEVICE,
                    compute_type=config.WHISPER_COMPUTE_TYPE
                )
                logger.info("Modelo Whisper pronto.")
            except Exception as e:
                logger.error(f"Falha ao carregar faster-whisper: {e}")
        return self.whisper_model

    def play_sound(self, sound_path: Path):
        """Reproduz um som de efeito (beep) curto via pygame."""
        if not sound_path.exists():
            return
        try:
            import pygame
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            sound = pygame.mixer.Sound(str(sound_path))
            sound.set_volume(0.5)
            sound.play()
            while pygame.mixer.get_busy():
                pygame.time.Clock().tick(25)
        except Exception as e:
            logger.debug(f"Falha ao tocar som {sound_path.name}: {e}")

    def speak(self, text: str):
        """Sintetiza e reproduz o texto de forma fluida, sem picotar em pedaços."""
        clean_text = text.replace("*", "").replace("#", "").strip()
        if not clean_text:
            return

        # Log amigável sem caracteres que quebrem terminais Windows cp1252
        try:
            print(f"\n[Jarvis Fala]: {clean_text}")
        except Exception:
            pass

        if self.tts_engine == "edge-tts":
            try:
                asyncio.run(self._speak_edge(clean_text))
                return
            except Exception as e:
                logger.warning(f"Falha no Edge-TTS ({e}), usando fallback pyttsx3.")

        offline = self.get_offline_engine()
        if offline:
            try:
                offline.say(clean_text)
                offline.runAndWait()
            except Exception as e:
                logger.error(f"Falha no pyttsx3: {e}")

    async def _speak_edge(self, text: str):
        import edge_tts
        import pygame

        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_file:
            temp_path = temp_file.name

        try:
            communicate = edge_tts.Communicate(
                text=text,
                voice=config.TTS_VOICE_PT,
                rate=config.TTS_RATE,
                volume=config.TTS_VOLUME
            )
            await communicate.save(temp_path)

            if not pygame.mixer.get_init():
                pygame.mixer.init()
            pygame.mixer.music.load(temp_path)
            pygame.mixer.music.play()

            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(15)

            pygame.mixer.music.unload()
        finally:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass

    def listen(self, timeout: Optional[int] = None, phrase_time_limit: Optional[int] = None) -> Optional[str]:
        """
        Escuta o microfone do usuário com tempo de pausa confortável para você falar sem ser interrompido.
        """
        import speech_recognition as sr
        recognizer = sr.Recognizer()
        
        # Parâmetros de tolerância para não cortar a fala do usuário
        recognizer.energy_threshold = 280
        recognizer.dynamic_energy_threshold = True
        recognizer.pause_threshold = config.MIC_PAUSE_THRESHOLD          # 1.3 segundos de silêncio para fechar
        recognizer.non_speaking_duration = 0.5

        t_out = timeout or config.MIC_LISTEN_TIMEOUT
        limit = phrase_time_limit or config.MIC_PHRASE_TIME_LIMIT

        try:
            with sr.Microphone() as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.3)

                # Som de abertura
                self.play_sound(START_SOUND)
                try:
                    print("[Jarvis Ouvindo...] Fale no seu tempo:")
                except Exception:
                    pass

                audio = recognizer.listen(source, timeout=t_out, phrase_time_limit=limit)

                # Som de fechamento
                self.play_sound(STOP_SOUND)

            try:
                print("[Jarvis]: Transcrevendo fala...")
            except Exception:
                pass

            model = self.get_whisper_model()
            if model:
                wav_data = io.BytesIO(audio.get_wav_data())
                segments, info = model.transcribe(
                    wav_data,
                    language="pt",
                    beam_size=1,
                    vad_filter=True
                )
                text = " ".join([segment.text for segment in segments]).strip()
                logger.info(f"Whisper transcreveu: '{text}'")
            else:
                text = recognizer.recognize_google(audio, language="pt-BR")

            try:
                print(f"[Voce disse]: {text}")
            except Exception:
                pass
            return text if text else None

        except sr.WaitTimeoutError:
            self.play_sound(STOP_SOUND)
            logger.info("Tempo de escuta esgotado sem início de fala.")
            return None
        except Exception as e:
            self.play_sound(STOP_SOUND)
            logger.error(f"Erro ao capturar/transcrever áudio: {e}")
            return None
