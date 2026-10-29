import os
from pathlib import Path
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

# Diretório base do repositório/código
BASE_DIR = Path(__file__).resolve().parent.parent

# No Windows instalado (ex: C:\Program Files\Jarvis AI), não podemos gravar lá dentro sem privilégio de admin.
# Usamos %LOCALAPPDATA%\JarvisAI para gravar dados dinâmicos (logs, modelos GGUF, memória ChromaDB).
LOCAL_APPDATA = os.environ.get("LOCALAPPDATA")
if LOCAL_APPDATA:
    USER_DATA_DIR = Path(LOCAL_APPDATA) / "Jarvis AI"
else:
    USER_DATA_DIR = Path.home() / "Jarvis AI"

# Se o repositório local tiver a pasta models/ com permissão de escrita e existir, podemos usar localmente;
# caso contrário, sempre usa USER_DATA_DIR seguro.
def get_storage_path(subfolder: str) -> Path:
    p = USER_DATA_DIR / subfolder
    p.mkdir(parents=True, exist_ok=True)
    return p

LOGS_DIR = get_storage_path("logs")
MODELS_DIR = get_storage_path("models")
MEMORY_DIR = get_storage_path("memory_data") / "chromadb"
PIPER_DIR = MODELS_DIR / "piper"

class JarvisConfig(BaseSettings):
    # Motor de IA: 'local' (offline ultra-leve) ou 'agy' (Antigravity CLI)
    AI_PROVIDER: str = "local"
    
    # Provedor Local (100% Offline Hermes 3 - Llama 3.2 3B via llama-cpp-python)
    # Procura primeiro se existe no repo local, se não aponta para a pasta do usuário em AppData
    LOCAL_MODEL_PATH: str = str((BASE_DIR / "models" / "Hermes-3-Llama-3.2-3B-Q4_K_M.gguf") if (BASE_DIR / "models" / "Hermes-3-Llama-3.2-3B-Q4_K_M.gguf").exists() else (MODELS_DIR / "Hermes-3-Llama-3.2-3B-Q4_K_M.gguf"))

    
    # Provedor AGY (opcional como fallback)
    AGY_BIN_PATH: str = "agy"
    AGY_TIMEOUT: int = 60
    AGY_DANGEROUSLY_SKIP_PERMISSIONS: bool = True
    AGY_MODEL: str = "gemini-3.8-flash-low"
    AGY_EFFORT: str = "low"
    
    # ChromaDB RAG (100% Offline com ONNX all-MiniLM-L6-v2)
    CHROMA_PERSIST_DIR: str = str(MEMORY_DIR)
    LEARNINGS_DIR: str = str(BASE_DIR / "data" / "learnings")
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    
    # Voice Config (TTS)
    TTS_ENGINE: str = "piper"  # 'piper' (offline neural ultra-rápido) ou 'edge-tts' (online)
    TTS_VOICE_PT: str = "pt-BR-AntonioNeural"
    TTS_RATE: str = "+10%"
    TTS_VOLUME: str = "+0%"
    
    # Piper TTS Config (100% Offline, Neural, Natural e Rápido)
    PIPER_MODEL_NAME: str = "pt_BR-faber-medium"
    PIPER_MODEL_PATH: str = str((BASE_DIR / "models" / "piper" / "pt_BR-faber-medium.onnx") if (BASE_DIR / "models" / "piper" / "pt_BR-faber-medium.onnx").exists() else (PIPER_DIR / "pt_BR-faber-medium.onnx"))
    PIPER_CONFIG_PATH: str = str((BASE_DIR / "models" / "piper" / "pt_BR-faber-medium.onnx.json") if (BASE_DIR / "models" / "piper" / "pt_BR-faber-medium.onnx.json").exists() else (PIPER_DIR / "pt_BR-faber-medium.onnx.json"))
    
    # Whisper STT Config (Modelo Small: alta precisão para termos técnicos e português)
    STT_ENGINE: str = "whisper"
    WHISPER_MODEL_SIZE: str = "small"
    WHISPER_DEVICE: str = "cpu"
    WHISPER_COMPUTE_TYPE: str = "default"  # 'default' funciona em 100% dos processadores x86/x64
    
    # Configurações do Microfone (Tolerância ampla para pausas naturais na fala sem cortar o usuário)
    MIC_PAUSE_THRESHOLD: float = 2.0      # Espera 2.0s de silêncio contínuo para considerar que a fala terminou
    MIC_NON_SPEAKING_DURATION: float = 0.8 # Janela de silêncio exigida após falar
    MIC_ENERGY_THRESHOLD: int = 150       # Sensibilidade alta para microfones mais baixos
    MIC_PHRASE_TIME_LIMIT: int = 45       # Permite comandos longos sem interrupção
    MIC_LISTEN_TIMEOUT: int = 10          # Tempo para começar a falar
    
    # Daemon / Shortcuts
    HOTKEY_LISTEN: str = "ctrl+alt+j"
    HOTKEY_QUIT: str = "ctrl+alt+q"
    
    class Config:
        arbitrary_types_allowed = True

config = JarvisConfig()
