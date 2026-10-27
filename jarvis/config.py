import os
from pathlib import Path
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

class JarvisConfig(BaseSettings):
    # Motor de IA: 'local' (offline ultra-leve) ou 'agy' (Antigravity CLI)
    AI_PROVIDER: str = "local"
    
    # Provedor Local (100% Offline Qwen 2.5 1.5B via llama-cpp-python)
    LOCAL_MODEL_PATH: str = str(BASE_DIR / "models" / "qwen2.5-1.5b-instruct-q4_k_m.gguf")
    
    # Provedor AGY (opcional como fallback)
    AGY_BIN_PATH: str = "agy"
    AGY_TIMEOUT: int = 60
    AGY_DANGEROUSLY_SKIP_PERMISSIONS: bool = True
    AGY_MODEL: str = "gemini-3.8-flash-low"
    AGY_EFFORT: str = "low"
    
    # ChromaDB RAG
    CHROMA_PERSIST_DIR: str = str(BASE_DIR / "jarvis" / "memory_data" / "chromadb")
    LEARNINGS_DIR: str = str(BASE_DIR / "data" / "learnings")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    EMBEDDING_MODEL: str = "text-embedding-004"
    
    # Voice Config (TTS)
    TTS_ENGINE: str = "edge-tts"  # 'edge-tts' ou 'pyttsx3'
    TTS_VOICE_PT: str = "pt-BR-AntonioNeural"
    TTS_RATE: str = "+10%"
    TTS_VOLUME: str = "+0%"
    
    # Whisper STT Config (Modelo Small: alta precisão fonética em português)
    STT_ENGINE: str = "whisper"
    WHISPER_MODEL_SIZE: str = "small"
    WHISPER_DEVICE: str = "cpu"
    WHISPER_COMPUTE_TYPE: str = "int8"
    
    # Configurações do Microfone (Tolerância confortável para pausas na fala)
    MIC_PAUSE_THRESHOLD: float = 1.4      # Espera 1.4s de silêncio para ter certeza que encerrou
    MIC_PHRASE_TIME_LIMIT: int = 30       # Permite frases longas e complexas
    MIC_LISTEN_TIMEOUT: int = 8           # Tempo para iniciar a fala
    
    # Daemon / Shortcuts
    HOTKEY_LISTEN: str = "ctrl+alt+j"
    HOTKEY_QUIT: str = "ctrl+alt+q"
    
    class Config:
        arbitrary_types_allowed = True

config = JarvisConfig()
