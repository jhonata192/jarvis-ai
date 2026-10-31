import os
import json
import logging
import subprocess
import webbrowser
import psutil
from typing import Dict, Any, List

logger = logging.getLogger("Jarvis.MCPServer")

try:
    from mcp.server.mcpserver import MCPServer
except ImportError:
    logger.warning("SDK 'mcp' indisponivel: servidor MCP externo desativado, ferramentas internas seguem ativas.")

    class MCPServer:
        def __init__(self, name: str):
            self.name = name

        def tool(self, name: str, description: str):
            def decorator(func):
                func.__mcp_tool__ = {"name": name, "description": description}
                return func
            return decorator

        async def run_stdio_async(self):
            raise RuntimeError("Modulo 'mcp' ausente: impossivel iniciar o servidor MCP via stdio.")

mcp_server = MCPServer("jarvis-system")

@mcp_server.tool(name="get_bluetooth_devices", description="Retorna os dispositivos Bluetooth conectados, pareados e o nível de bateria de cada um.")
def get_bluetooth_devices() -> str:
    """
    Retorna com exatidão quais dispositivos Bluetooth estão conectados ou pareados no Windows.
    Informa também o nível de bateria se o dispositivo reportar via GATT.
    """
    ps_cmd = (
        "$adapters = Get-PnpDevice -Class 'Bluetooth' -ErrorAction SilentlyContinue | "
        "Where-Object { $_.InstanceId -notlike 'BTHENUM\\*' -and $_.Status -eq 'OK' }; "
        "if (-not $adapters) { "
        "  [PSCustomObject]@{ HasAdapter = $false; Devices = @() } | ConvertTo-Json -Compress; "
        "} else { "
        "  $devs = Get-PnpDevice -Class 'Bluetooth' -ErrorAction SilentlyContinue | "
        "  Where-Object { $_.InstanceId -like 'BTHENUM\\DEV_*' } | "
        "  ForEach-Object { "
        "    $conn = (Get-PnpDeviceProperty -InstanceId $_.InstanceId -KeyName '{83DA6326-97A6-4088-9453-A1923F573B29} 15' -ErrorAction SilentlyContinue).Data; "
        "    $bat = (Get-PnpDeviceProperty -InstanceId $_.InstanceId -KeyName '{104EA319-6EE2-4701-BD47-8DDBF425BBE5} 2' -ErrorAction SilentlyContinue).Data; "
        "    [PSCustomObject]@{ Name = $_.FriendlyName; Connected = ($conn -eq $true); Battery = $bat } "
        "  }; "
        "  [PSCustomObject]@{ HasAdapter = $true; Devices = @($devs) } | ConvertTo-Json -Compress; "
        "}"
    )
    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=12,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        if res.returncode != 0 or not res.stdout.strip():
            return "Não foi possível consultar os dispositivos Bluetooth no momento."

        result_data = json.loads(res.stdout)
        if not result_data.get("HasAdapter", False):
            return "Este computador não possui nenhuma placa ou adaptador Bluetooth conectado ou ativado."

        raw_devs = result_data.get("Devices", [])
        if isinstance(raw_devs, dict):
            raw_devs = [raw_devs]

        connected = []
        paired = []

        for d in raw_devs:
            name = d.get("Name")
            is_conn = d.get("Connected", False)
            bat = d.get("Battery")
            if not name:
                continue

            info = name
            if bat is not None:
                info += f" ({bat}% de bateria)"

            if is_conn:
                if info not in connected:
                    connected.append(info)
            else:
                if name not in paired:
                    paired.append(name)

        if connected:
            nomes = ", ".join(connected)
            return f"Dispositivos Bluetooth conectados no momento: {nomes}."
        elif paired:
            nomes = ", ".join(paired)
            return f"Nenhum dispositivo Bluetooth está conectado no momento. Dispositivos pareados desligados: {nomes}."
        else:
            return "O adaptador Bluetooth está ativo, mas não há nenhum dispositivo Bluetooth pareado neste computador."
    except Exception as e:
        return f"Erro ao verificar Bluetooth: {e}"

@mcp_server.tool(name="set_bluetooth_radio_state", description="Liga ou desliga o rádio ou antena Bluetooth do computador.")
def set_bluetooth_radio_state(state: str) -> str:
    """
    Liga ('on') ou Desliga ('off') o rádio Bluetooth do computador Windows.
    """
    desired = state.lower().strip()
    target_state = "On" if desired in ["on", "ligar", "ativar", "true", "1"] else "Off"
    
    ps_cmd = (
        "Add-Type -AssemblyName System.Runtime.WindowsRuntime; "
        "$asTask = ([System.WindowsRuntimeSystemExtensions].GetMethods() | "
        "Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]; "
        "[Windows.Devices.Radios.Radio,Windows.System.Devices,ContentType=WindowsRuntime] | Out-Null; "
        "$op = [Windows.Devices.Radios.Radio]::GetRadiosAsync(); "
        "$t = $asTask.MakeGenericMethod([System.Collections.Generic.IReadOnlyList[Windows.Devices.Radios.Radio]]).Invoke($null, @($op)); "
        "$t.Wait(); "
        "$bt = $t.Result | Where-Object { $_.Kind -eq [Windows.Devices.Radios.RadioKind]::Bluetooth }; "
        "if (-not $bt) { Write-Output 'NO_RADIO'; exit }; "
        f"$setOp = $bt.SetStateAsync([Windows.Devices.Radios.RadioState]::{target_state}); "
        "$tSet = $asTask.MakeGenericMethod([Windows.Devices.Radios.RadioAccessStatus]).Invoke($null, @($setOp)); "
        "$tSet.Wait(); "
        "Write-Output $tSet.Result.ToString()"
    )
    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=8,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        out = res.stdout.strip()
        if "NO_RADIO" in out:
            return "Nenhum rádio Bluetooth foi encontrado neste computador."
        if "Allowed" in out:
            estado_pt = "ativado" if target_state == "On" else "desativado"
            return f"O rádio Bluetooth do computador foi {estado_pt} com sucesso."
        return f"Não foi possível alterar o estado do Bluetooth: {out}"
    except Exception as e:
        return f"Erro ao alterar rádio Bluetooth: {e}"

@mcp_server.tool(name="set_system_volume", description="Ajusta o volume do áudio do computador Windows de 0 a 100 porcento.")
def set_system_volume(level_percent: int) -> str:
    """Ajusta o volume do áudio do computador Windows de 0 a 100%."""
    try:
        from pycaw.pycaw import AudioUtilities
        devices = AudioUtilities.GetSpeakers()
        clamped = max(0, min(100, int(level_percent)))

        # Compatibilidade com versões novas e legadas de pycaw
        if hasattr(devices, "EndpointVolume"):
            volume = devices.EndpointVolume
        else:
            from ctypes import cast, POINTER
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import IAudioEndpointVolume
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(interface, POINTER(IAudioEndpointVolume))

        volume.SetMasterVolumeLevelScalar(clamped / 100.0, None)
        return f"Volume do sistema ajustado para {clamped}%."
    except Exception as e:
        return f"Não foi possível alterar o volume: {e}"

@mcp_server.tool(name="get_battery_status", description="Retorna a porcentagem atual da bateria do computador e se está na tomada.")
def get_battery_status() -> str:
    """Retorna a porcentagem atual da bateria do computador e se está na tomada."""
    try:
        battery = psutil.sensors_battery()
        if not battery:
            return "Computador sem bateria ou operando em desktop."
        status = "carregando na tomada" if battery.power_plugged else "operando na bateria"
        return f"Bateria em {battery.percent:.0f}%, atualmente {status}."
    except Exception as e:
        return f"Erro ao ler status da bateria: {e}"

@mcp_server.tool(name="get_hardware_telemetry", description="Retorna uso da CPU, memória RAM em GB e espaço livre em disco, armazenamento do HD ou SSD.")
def get_hardware_telemetry() -> str:
    """Retorna o uso atual de CPU, memória RAM em GB e espaço livre em disco."""
    try:
        cpu = psutil.cpu_percent(interval=0.2)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('C:')
        return (
            f"CPU em {cpu}%, "
            f"memória RAM com {mem.used / (1024**3):.1f} GB em uso de {mem.total / (1024**3):.1f} GB, "
            f"e {disk.free / (1024**3):.1f} GB de armazenamento livre no disco C de {disk.total / (1024**3):.1f} GB no total."
        )
    except Exception as e:
        return f"Erro na telemetria: {e}"

@mcp_server.tool(name="open_app_or_website", description="Abre um aplicativo comum ou site pelo navegador.")
def open_app_or_website(target: str) -> str:
    """Abre um aplicativo comum ou site pelo navegador."""
    apps = {
        "notepad": "notepad.exe",
        "bloco de notas": "notepad.exe",
        "calculadora": "calc.exe",
        "terminal": "powershell.exe",
        "code": "code",
        "vs code": "code"
    }
    key = target.lower().strip()
    cmd = apps.get(key, target)
    try:
        if cmd.startswith("http"):
            webbrowser.open(cmd)
            return f"Abrindo {cmd} no navegador."
        subprocess.Popen(cmd, shell=True)
        return f"Aplicativo '{target}' aberto com sucesso."
    except Exception as e:
        return f"Erro ao abrir {target}: {e}"

@mcp_server.tool(name="check_for_updates", description="Verifica se existe uma versão mais recente do Jarvis AI no GitHub.")
def check_for_updates() -> str:
    """Verifica no GitHub se existe uma versão mais recente do Jarvis AI e retorna o status."""
    try:
        from jarvis.core.updater import JarvisUpdater
        updater = JarvisUpdater()
        info = updater.check_for_update()
        if not info:
            return f"O Jarvis já está em sua versão mais recente ({updater.current_version}). Nenhuma atualização pendente."
        tag = info.get("tag_name", "")
        return f"Uma nova versão ({tag}) está disponível no GitHub. A sua versão atual é {updater.current_version}."
    except Exception as e:
        return f"Erro ao verificar atualizações: {e}"

@mcp_server.tool(name="install_latest_update", description="Baixa e instala a versão mais recente do Jarvis AI a partir do GitHub Releases.")
def install_latest_update() -> str:
    """Baixa e instala a versão mais recente do Jarvis AI a partir do GitHub Releases."""
    try:
        from jarvis.core.updater import JarvisUpdater
        updater = JarvisUpdater()
        info = updater.check_for_update()
        if not info:
            return f"O Jarvis já está em sua versão mais recente ({updater.current_version}). Nenhuma atualização necessária."
        tag = info.get("tag_name", "")
        success = updater.download_and_install_update(info)
        if success:
            return f"A versão {tag} foi baixada com sucesso e o instalador foi iniciado para atualizar o sistema."
        else:
            return f"Não foi possível concluir o download da versão {tag}."
    except Exception as e:
        return f"Erro ao instalar atualização: {e}"

if __name__ == "__main__":
    import asyncio
    asyncio.run(mcp_server.run_stdio_async())

