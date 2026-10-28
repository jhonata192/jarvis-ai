import os
import sys
import json
import logging
import subprocess
import tempfile
import urllib.request
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, Callable

from jarvis.config import config
from version import VERSION as CURRENT_VERSION

logger = logging.getLogger("Jarvis.Updater")

GITHUB_REPO = "jhonata192/jarvis-ai"
RELEASES_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

def parse_version(ver_str: str) -> Tuple[int, ...]:
    """Converte 'v1.2.1' ou '1.2.1' em tupla comparável de inteiros: (1, 2, 1)."""
    clean = ver_str.lower().lstrip("v").strip()
    parts = []
    for p in clean.split("."):
        try:
            parts.append(int(p))
        except ValueError:
            break
    return tuple(parts)

class JarvisUpdater:
    """
    Verifica atualizações no GitHub Releases e aplica silenciosamente no Windows.
    """

    def __init__(self, current_version: str = CURRENT_VERSION):
        self.current_version = current_version

    def check_for_update(self) -> Optional[Dict[str, Any]]:
        """
        Consulta a API do GitHub Releases para descobrir se existe versão mais recente.
        Retorna dicionário com os detalhes da nova versão ou None se já estiver atualizado.
        """
        try:
            req = urllib.request.Request(
                RELEASES_API_URL,
                headers={
                    "User-Agent": "JarvisAI-AutoUpdater/1.0",
                    "Accept": "application/vnd.github.v3+json"
                }
            )
            with urllib.request.urlopen(req, timeout=8) as response:
                if response.status != 200:
                    return None
                data = json.loads(response.read().decode("utf-8"))

            latest_tag = data.get("tag_name", "")
            latest_version_tuple = parse_version(latest_tag)
            current_version_tuple = parse_version(self.current_version)

            logger.info(f"Versão atual: {self.current_version} | Última release no GitHub: {latest_tag}")

            if latest_version_tuple > current_version_tuple:
                # Procura o instalador Setup.exe ou o ZIP portátil
                installer_url = None
                portable_url = None
                for asset in data.get("assets", []):
                    name = asset.get("name", "")
                    download_url = asset.get("browser_download_url", "")
                    if name.endswith("-Setup.exe") or name.endswith("Setup.exe"):
                        installer_url = download_url
                    elif name.endswith(".zip"):
                        portable_url = download_url

                return {
                    "tag_name": latest_tag,
                    "name": data.get("name", latest_tag),
                    "body": data.get("body", ""),
                    "installer_url": installer_url,
                    "portable_url": portable_url
                }

            return None
        except Exception as e:
            logger.warning(f"Não foi possível verificar atualizações no GitHub: {e}")
            return None

    def download_and_install_update(
        self,
        update_info: Dict[str, Any],
        status_callback: Optional[Callable] = None
    ) -> bool:
        """
        Baixa o instalador da nova versão com relatório de progresso e o executa silenciosamente no Windows (/SILENT).
        """
        installer_url = update_info.get("installer_url")
        if not installer_url:
            logger.warning("Instalador Setup.exe não encontrado nos assets da release.")
            return False

        tag = update_info.get("tag_name", "latest")
        logger.info(f"Iniciando download da atualização {tag} a partir de {installer_url}...")

        temp_dir = Path(tempfile.gettempdir())
        installer_file = temp_dir / f"JarvisAI-{tag}-Setup.exe"

        try:
            from jarvis.core.downloader import download_file_with_progress
            download_file_with_progress(
                url=installer_url,
                destination=installer_file,
                description=f"Atualização do Jarvis {tag}",
                status_callback=status_callback
            )

            logger.info(f"Instalador da nova versão baixado com sucesso em: {installer_file}")

            # Executa o instalador Inno Setup no modo silencioso (/SILENT /NORESTART)
            # O Inno Setup fecha qualquer processo residual, substitui os arquivos e reinicia
            cmd = f'start "" "{installer_file}" /SILENT /NORESTART'
            subprocess.Popen(
                cmd,
                shell=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            )
            logger.info("Instalador da atualização disparado. Encerrando processo atual do Jarvis para liberar o .exe...")

            # Dá 6 segundos para a voz concluir a fala de encerramento e o instalador iniciar
            import threading
            def _exit_jarvis():
                import time
                time.sleep(6)
                os._exit(0)

            threading.Thread(target=_exit_jarvis, daemon=True).start()
            return True

        except Exception as e:
            logger.error(f"Erro ao baixar/aplicar atualização do Jarvis: {e}")
            return False
