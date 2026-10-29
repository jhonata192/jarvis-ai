import os
import sys
import logging
import urllib.request
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger("Jarvis.Downloader")

QWEN_MODEL_URL = "https://huggingface.co/Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF/resolve/main/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf"
PIPER_MODEL_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/main/pt/pt_BR/faber/medium/pt_BR-faber-medium.onnx"
PIPER_CONFIG_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/main/pt/pt_BR/faber/medium/pt_BR-faber-medium.onnx.json"
EMBEDDING_MODEL_URL = "https://chroma-onnx-models.s3.amazonaws.com/all-MiniLM-L6-v2/onnx.tar.gz"

def download_file_with_progress(
    url: str,
    destination: Path,
    description: str = "Arquivo",
    status_callback: Optional[Callable[[str], None]] = None
):
    """
    Faz o download de um arquivo com relatório de progresso e escrita atômica (.tmp).
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_destination = destination.with_suffix(destination.suffix + ".download")

    if status_callback:
        status_callback(f"Iniciando download de {description}...", 0, 0.0, 0.0, description)
    logger.info(f"Baixando de {url} para {destination}...")

    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "JarvisAI-AutoDownloader/1.0"}
        )
        with urllib.request.urlopen(req) as response, open(temp_destination, "wb") as out_file:
            total_size = response.getheader("Content-Length")
            total_bytes = int(total_size) if total_size else 0
            downloaded = 0
            last_logged_mb = 0

            block_size = 1024 * 1024  # 1MB por bloco
            while True:
                buffer = response.read(block_size)
                if not buffer:
                    break
                downloaded += len(buffer)
                out_file.write(buffer)

                current_mb = downloaded / (1024 * 1024)
                if current_mb - last_logged_mb >= 2 or (total_bytes and downloaded == total_bytes):
                    last_logged_mb = current_mb
                    pct = (downloaded / total_bytes) * 100 if total_bytes else 0
                    if total_bytes:
                        msg = f"Baixando {description}: {current_mb:.1f} MB de {total_bytes / (1024*1024):.1f} MB ({pct:.1f}%)"
                    else:
                        msg = f"Baixando {description}: {current_mb:.1f} MB..."
                    logger.debug(msg)
                    if status_callback:
                        status_callback(msg, int(pct), current_mb, (total_bytes / (1024*1024)) if total_bytes else 0, description)

        # Move o arquivo temporário para o destino final atomicamente
        if temp_destination.exists():
            if destination.exists():
                destination.unlink()
            temp_destination.rename(destination)
        
        logger.info(f"{description} baixado com sucesso em: {destination}")
        if status_callback:
            status_callback(f"{description} instalado com sucesso!", 100, current_mb, current_mb, description)

    except Exception as e:
        logger.error(f"Erro ao baixar {description} de {url}: {e}")
        if temp_destination.exists():
            try:
                temp_destination.unlink()
            except Exception:
                pass
        raise e


def ensure_models_available(
    llm_model_path: Path,
    whisper_model_size: str,
    piper_model_path: Optional[Path] = None,
    piper_config_path: Optional[Path] = None,
    status_callback: Optional[Callable[[str], None]] = None
):
    """
    Verifica se a LLM local, o modelo Faster-Whisper e a voz Piper estão presentes.
    Caso não estejam, faz o download automático antes do Jarvis iniciar.
    """
    # 1. Verificar e baixar a voz Piper TTS (se configurada)
    if piper_model_path and piper_config_path:
        if not piper_model_path.exists() or not piper_config_path.exists():
            logger.info("Voz Piper TTS não encontrada. Baixando modelo neural de voz...")
            download_file_with_progress(
                url=PIPER_MODEL_URL,
                destination=piper_model_path,
                description="Voz Neural em Português",
                status_callback=status_callback
            )
            download_file_with_progress(
                url=PIPER_CONFIG_URL,
                destination=piper_config_path,
                description="Voz Neural em Português",
                status_callback=None
            )
        else:
            logger.info(f"Voz Piper verificada: {piper_model_path}")

    # 2. Verificar e baixar o modelo de Embedding local (all-MiniLM-L6-v2)
    embedding_cache_dir = Path.home() / ".cache" / "chroma" / "onnx_models" / "all-MiniLM-L6-v2"
    extracted_model = embedding_cache_dir / "onnx" / "model.onnx"
    if not extracted_model.exists():
        logger.info(f"Modelo de embedding local não encontrado em: {extracted_model}. Baixando pacote ONNX...")
        archive_path = embedding_cache_dir / "onnx.tar.gz"
        download_file_with_progress(
            url=EMBEDDING_MODEL_URL,
            destination=archive_path,
            description="Modelo de Memória e Embedding",
            status_callback=status_callback
        )
        try:
            import tarfile
            logger.info(f"Descompactando modelo de embedding em {embedding_cache_dir}...")
            with tarfile.open(archive_path, mode="r:gz") as tar:
                if sys.version_info >= (3, 12):
                    tar.extractall(path=embedding_cache_dir, filter="data")
                else:
                    tar.extractall(path=embedding_cache_dir)
            logger.info("Modelo de embedding descompactado com sucesso.")
        except Exception as e:
            logger.error(f"Erro ao descompactar modelo de embedding: {e}")
    else:
        logger.info(f"Modelo de embedding verificado: {extracted_model}")

    # 3. Verificar e baixar o modelo LLM GGUF
    if not llm_model_path.exists():
        logger.info(f"Modelo LLM não encontrado em: {llm_model_path}")
        download_file_with_progress(
            url=QWEN_MODEL_URL,
            destination=llm_model_path,
            description="Modelo de Inteligência Artificial",
            status_callback=status_callback
        )
    else:
        logger.info(f"Modelo LLM verificado: {llm_model_path}")

    # 4. Verificar e baixar o modelo Faster-Whisper
    # O faster_whisper faz cache automático no huggingface hub / cache local
    logger.info(f"Verificando modelo Whisper ({whisper_model_size})...")
    try:
        from faster_whisper import download_model
        if status_callback:
            status_callback(f"Verificando modelo de reconhecimento de voz ({whisper_model_size})...")
        download_model(whisper_model_size)
        logger.info(f"Modelo Whisper ({whisper_model_size}) verificado e pronto.")
    except Exception as e:
        logger.warning(f"Aviso ao pré-carregar modelo Whisper: {e}")
