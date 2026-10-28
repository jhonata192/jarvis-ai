import os
import sys
import logging
import urllib.request
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger("Jarvis.Downloader")

QWEN_MODEL_URL = "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf"

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
        status_callback(f"Iniciando download de {description}...")
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
                        status_callback(msg, int(pct), current_mb, (total_bytes / (1024*1024)) if total_bytes else 0)

        # Move o arquivo temporário para o destino final atomicamente
        if temp_destination.exists():
            if destination.exists():
                destination.unlink()
            temp_destination.rename(destination)
        
        logger.info(f"{description} baixado com sucesso em: {destination}")
        if status_callback:
            status_callback(f"{description} instalado com sucesso!")

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
    status_callback: Optional[Callable[[str], None]] = None
):
    """
    Verifica se a LLM local e o modelo Faster-Whisper estão presentes.
    Caso não estejam, faz o download automático antes do Jarvis iniciar.
    """
    # 1. Verificar e baixar o modelo LLM GGUF
    if not llm_model_path.exists():
        logger.info(f"Modelo LLM não encontrado em: {llm_model_path}")
        if status_callback:
            status_callback("O modelo de inteligência artificial não foi encontrado. Iniciando download automático...")
        download_file_with_progress(
            url=QWEN_MODEL_URL,
            destination=llm_model_path,
            description="Modelo Qwen 2.5 1.5B (IA Local)",
            status_callback=status_callback
        )
    else:
        logger.info(f"Modelo LLM verificado: {llm_model_path}")

    # 2. Verificar e baixar o modelo Faster-Whisper
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
