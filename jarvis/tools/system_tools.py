import os
import json
import subprocess
import webbrowser
import datetime
import psutil
from typing import Dict, Any, List

class SystemTools:
    """
    Ferramentas operacionais nativas do Jarvis executadas diretamente em Python (ultra-rápidas).
    """

    @staticmethod
    def get_system_status() -> Dict[str, Any]:
        """Retorna o uso de CPU, memória e status do sistema."""
        cpu = psutil.cpu_percent(interval=0.2)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('C:')
        
        return {
            "cpu_percent": f"{cpu}%",
            "ram_used_gb": f"{mem.used / (1024**3):.1f} GB ({mem.percent}%)",
            "ram_total_gb": f"{mem.total / (1024**3):.1f} GB",
            "disk_free_gb": f"{disk.free / (1024**3):.1f} GB livres",
            "timestamp": datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        }

    @staticmethod
    def get_bluetooth_devices() -> str:
        """
        Consulta rápida de dispositivos Bluetooth conectados no Windows.
        Retorna uma frase clara em português pronta para o Jarvis falar.
        """
        ps_cmd = (
            'Get-PnpDevice -Class "Bluetooth" | '
            'Select-Object Status, FriendlyName | '
            'ConvertTo-Json -Compress'
        )
        try:
            res = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            if res.returncode != 0 or not res.stdout.strip():
                return "Não consegui obter o status do Bluetooth no momento."

            raw_data = json.loads(res.stdout)
            if isinstance(raw_data, dict):
                raw_data = [raw_data]

            connected = []
            for d in raw_data:
                name = d.get("FriendlyName")
                status = d.get("Status")
                if not name or "Enumerador" in name or "Adapter" in name or "Transporte" in name or "RFCOMM" in name:
                    continue
                if status == "OK" and name not in connected:
                    connected.append(name)

            if connected:
                nomes = ", ".join(connected)
                return f"Dispositivos Bluetooth conectados no momento: {nomes}."
            else:
                return "Nenhum dispositivo Bluetooth de áudio ou periférico está conectado no momento."
        except Exception as e:
            return f"Erro ao verificar dispositivos Bluetooth: {e}"

    @staticmethod
    def open_application(app_name: str) -> str:
        """Abre aplicativos comuns ou URLs."""
        apps = {
            "notepad": "notepad.exe",
            "calculadora": "calc.exe",
            "terminal": "powershell.exe",
            "code": "code",
            "navegador": "https://google.com"
        }
        
        target = apps.get(app_name.lower(), app_name)
        if target.startswith("http"):
            webbrowser.open(target)
            return f"Abrindo {target} no navegador."
        else:
            try:
                subprocess.Popen(target, shell=True)
                return f"Aplicativo '{app_name}' iniciado com sucesso."
            except Exception as e:
                return f"Falha ao iniciar '{app_name}': {e}"
