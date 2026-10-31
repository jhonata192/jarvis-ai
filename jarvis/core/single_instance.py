"""
Módulo de instância única para o Jarvis AI.
Garante que apenas um único processo do Jarvis seja executado simultaneamente no Windows,
utilizando um Named Mutex nativo do kernel do sistema operacional.
"""

import os
import sys
import logging
from typing import Optional

logger = logging.getLogger("Jarvis.SingleInstance")

_global_lock: Optional["SingleInstanceLock"] = None


class SingleInstanceLock:
    """
    Garante que apenas uma única instância do Jarvis AI seja executada por vez.
    Utiliza Named Mutex no Windows (namespace Local da sessão de usuário),
    que é automaticamente liberado pelo kernel caso o processo seja encerrado ou caia.
    """

    def __init__(self, mutex_name: str = "JarvisAI_SingleInstance_Mutex"):
        self.mutex_name = mutex_name
        self.mutex_handle = None
        self.is_already_running = False

    def acquire(self) -> bool:
        """
        Tenta adquirir o bloqueio exclusivo de instância única.
        Retorna True se adquiriu o mutex (primeira instância ativa).
        Retorna False se outra instância já estiver em execução.
        """
        if os.name == "nt":
            import ctypes

            ERROR_ALREADY_EXISTS = 183
            kernel32 = ctypes.windll.kernel32

            full_name = f"Local\\{self.mutex_name}"
            self.mutex_handle = kernel32.CreateMutexW(None, False, full_name)
            last_error = kernel32.GetLastError()

            if last_error == ERROR_ALREADY_EXISTS:
                self.is_already_running = True
                if self.mutex_handle:
                    kernel32.CloseHandle(self.mutex_handle)
                    self.mutex_handle = None
                return False

            return True
        else:
            # Fallback para sistemas POSIX usando flock
            import fcntl
            import tempfile
            from pathlib import Path

            self.lock_file_path = Path(tempfile.gettempdir()) / f"{self.mutex_name}.lock"
            try:
                self.lock_file = open(self.lock_file_path, "w")
                fcntl.flock(self.lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return True
            except (IOError, OSError):
                self.is_already_running = True
                return False

    def get_existing_pid(self) -> Optional[int]:
        """Tenta identificar o PID do Jarvis que já está em execução para o log."""
        try:
            import psutil

            current_pid = os.getpid()
            for proc in psutil.process_iter(["pid", "name", "cmdline"]):
                try:
                    if proc.info["pid"] == current_pid:
                        continue
                    name = (proc.info.get("name") or "").lower()
                    cmdline = " ".join(proc.info.get("cmdline") or []).lower()
                    if "jarvisai" in name or ("python" in name and "background_runner" in cmdline):
                        return proc.info["pid"]
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception:
            pass
        return None

    def release(self):
        """Libera o mutex explicitamente."""
        if os.name == "nt" and self.mutex_handle:
            import ctypes

            ctypes.windll.kernel32.CloseHandle(self.mutex_handle)
            self.mutex_handle = None
        elif hasattr(self, "lock_file") and self.lock_file:
            try:
                import fcntl

                fcntl.flock(self.lock_file, fcntl.LOCK_UN)
                self.lock_file.close()
            except Exception:
                pass


def ensure_single_instance(mutex_name: str = "JarvisAI_SingleInstance_Mutex") -> SingleInstanceLock:
    """
    Verifica se já existe outra instância do Jarvis em execução.
    Se já existir, registra aviso e encerra o processo atual imediatamente (código 0).
    Caso contrário, mantém o bloqueio ativo durante a execução.
    """
    global _global_lock
    if _global_lock is not None and not _global_lock.is_already_running:
        return _global_lock

    lock = SingleInstanceLock(mutex_name)
    if not lock.acquire():
        existing_pid = lock.get_existing_pid()
        pid_info = f" (PID {existing_pid})" if existing_pid else ""
        msg = f"Já existe uma instância do Jarvis AI em execução{pid_info}. Encerrando esta nova tentativa."
        logger.warning(msg)
        print(msg)
        sys.exit(0)

    _global_lock = lock
    logger.info(f"Instância única garantida com sucesso (Mutex: {mutex_name}, PID: {os.getpid()}).")
    return lock
