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
    Suporta Piper TTS (offline neural de alta qualidade), Edge-TTS e fallback SAPI.
    """

    def __init__(self):
        self.tts_engine = config.TTS_ENGINE
        self.piper_voice = None
        self.whisper_model = None
        self._sound_cache = {}
        self._noise_calibrated = False

        # Pré-inicializa o mixer de áudio para evitar recriação e latência nas falas
        try:
            import pygame
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=22050, size=-16, channels=1, buffer=1024)
        except Exception as e:
            logger.debug(f"Aviso ao inicializar pygame mixer: {e}")

    def reload_piper(self):
        """Força o recarregamento da voz neural Piper (por exemplo após o término do download)."""
        self.piper_voice = None
        return self.get_piper_voice()

    def get_piper_voice(self):
        """Inicializa Piper TTS sob demanda (lazy loading)."""
        if self.piper_voice is None:
            model_path = Path(config.PIPER_MODEL_PATH)
            config_path = Path(config.PIPER_CONFIG_PATH)
            if model_path.exists() and config_path.exists():
                try:
                    from piper import PiperVoice
                    logger.info(f"Carregando voz neural Piper ({config.PIPER_MODEL_NAME})...")
                    self.piper_voice = PiperVoice.load(model_path, config_path)
                    logger.info("Voz neural Piper carregada com sucesso.")
                except (OSError, Exception) as e:
                    logger.warning(f"Voz neural Piper não suportada nesta CPU ({e}). Usando síntese de voz alternativa.")
                    self.piper_voice = False
            else:
                # Arquivos ainda não existem (em download); não define False definitivo
                return None
        return self.piper_voice if self.piper_voice is not False else None

    def get_whisper_model(self):
        """Inicializa o modelo Whisper sob demanda (lazy loading) com fallback seguro para qualquer CPU."""
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
            except (OSError, Exception) as e:
                logger.warning(f"Whisper local indisponível para esta CPU ({e}). Usando reconhecimento de fala universal.")
                self.whisper_model = False
        return self.whisper_model if self.whisper_model is not False else None

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

        # 1. Tenta Piper TTS (offline neural instantâneo)
        if self.tts_engine == "piper":
            if self._speak_piper(clean_text):
                return
            logger.debug("Voz Piper em inicialização ou indisponível. Tentando Edge-TTS/SAPI...")

        # 2. Tenta Edge-TTS (online de altíssima qualidade se conectado à internet)
        if self.tts_engine == "edge-tts" or self.tts_engine == "piper":
            try:
                asyncio.run(self._speak_edge(clean_text))
                return
            except Exception as e:
                logger.warning(f"Edge-TTS indisponível ({e}). Tentando fallback nativo.")

        # 3. Fallback nativo Windows SAPI SpVoice
        self._speak_sapi(clean_text)

    def _speak_piper(self, text: str) -> bool:
        """Sintetiza áudio via Piper TTS em memória e reproduz via pygame com cache de frases curtas."""
        import pygame
        # Reutiliza som pré-sintetizado se já estiver em cache
        if text in self._sound_cache:
            try:
                sound = self._sound_cache[text]
                sound.play()
                while pygame.mixer.get_busy():
                    pygame.time.Clock().tick(25)
                return True
            except Exception:
                pass

        voice = self.get_piper_voice()
        if not voice:
            return False
        try:
            import wave
            buf = io.BytesIO()
            with wave.open(buf, 'wb') as wav_file:
                voice.synthesize_wav(text, wav_file)
            buf.seek(0)
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            sound = pygame.mixer.Sound(buf)
            # Salva no cache se for frase curta recorrente (< 60 caracteres)
            if len(text) < 60:
                self._sound_cache[text] = sound
            sound.play()
            while pygame.mixer.get_busy():
                pygame.time.Clock().tick(25)
            return True
        except (OSError, Exception) as e:
            logger.warning(f"Erro na síntese do Piper TTS ({e}). Alternando para sintetizador universal.")
            self.piper_voice = False
            return False

    def _speak_sapi(self, text: str):
        """Fallback leve via SAPI SpVoice nativo do Windows sem travar."""
        try:
            import win32com.client
            voice = win32com.client.Dispatch("SAPI.SpVoice")
            voice.Rate = 1
            voice.Speak(text)
        except Exception as e:
            logger.error(f"Falha no fallback SAPI: {e}")

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
        recognizer.energy_threshold = config.MIC_ENERGY_THRESHOLD
        recognizer.dynamic_energy_threshold = False  # Evita que o limiar suba sozinho enquanto você fala
        recognizer.pause_threshold = config.MIC_PAUSE_THRESHOLD          # Espera 2.0s de silêncio para fechar
        recognizer.non_speaking_duration = config.MIC_NON_SPEAKING_DURATION

        t_out = timeout or config.MIC_LISTEN_TIMEOUT
        limit = phrase_time_limit or config.MIC_PHRASE_TIME_LIMIT

        try:
            with sr.Microphone() as source:
                # Calibra ruído apenas uma vez para não atrasar a abertura do microfone a cada chamada
                if not self._noise_calibrated:
                    recognizer.adjust_for_ambient_noise(source, duration=0.2)
                    self._noise_calibrated = True

                # Garante que o limiar de energia nunca fique alto demais (cortando voz suave)
                if recognizer.energy_threshold > 250:
                    recognizer.energy_threshold = 250
                elif recognizer.energy_threshold < 100:
                    recognizer.energy_threshold = 100

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
            text = None
            if model:
                try:
                    wav_data = io.BytesIO(audio.get_wav_data())
                    segments, info = model.transcribe(
                        wav_data,
                        language="pt",
                        beam_size=1,
                        vad_filter=True
                    )
                    text = " ".join([segment.text for segment in segments]).strip()
                    logger.info(f"Whisper transcreveu: '{text}'")
                except (OSError, Exception) as e:
                    logger.warning(f"Transcrição Whisper falhou ({e}). Recorrendo ao reconhecedor universal.")
                    self.whisper_model = False
                    text = None

            if not text:
                try:
                    text = recognizer.recognize_google(audio, language="pt-BR")
                except Exception as e:
                    logger.warning(f"Reconhecimento Google falhou: {e}")
                    text = None

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
