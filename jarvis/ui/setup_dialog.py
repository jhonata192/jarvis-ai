import os
import sys
import time
import json
import logging
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Optional, Callable

from jarvis.config import config, USER_DATA_DIR, CACHE_DIR, load_settings, save_settings

logger = logging.getLogger("Jarvis.SetupUI")

OLLAMA_INSTALLER_URL = "https://ollama.com/download/OllamaSetup.exe"
OLLAMA_DEFAULT_MODEL = "qwen2.5:1.5b"

def is_ollama_installed() -> bool:
    """Verifica se o Ollama está instalado no sistema Windows."""
    if shutil.which("ollama"):
        return True
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        base = Path(local_app_data) / "Programs" / "Ollama"
        if (base / "ollama.exe").exists() or (base / "ollama app.exe").exists():
            return True
    return False

def is_ollama_server_running() -> bool:
    """Verifica se a API local do Ollama está respondendo."""
    import urllib.request
    try:
        req = urllib.request.Request("http://127.0.0.1:11434/api/tags", headers={"User-Agent": "JarvisAI"})
        with urllib.request.urlopen(req, timeout=2) as resp:
            return resp.status == 200
    except Exception:
        return False

def start_ollama_service() -> bool:
    """Inicia o processo do Ollama em segundo plano."""
    if is_ollama_server_running():
        return True

    local_app_data = os.environ.get("LOCALAPPDATA")
    target_exe = None
    if local_app_data:
        base = Path(local_app_data) / "Programs" / "Ollama"
        for candidate in ["ollama app.exe", "ollama.exe"]:
            p = base / candidate
            if p.exists():
                target_exe = p
                break

    if not target_exe and shutil.which("ollama"):
        target_exe = Path(shutil.which("ollama"))

    if not target_exe:
        return False

    try:
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        if "app.exe" in target_exe.name.lower():
            subprocess.Popen([str(target_exe)])
        else:
            subprocess.Popen([str(target_exe), "serve"], creationflags=flags)

        t0 = time.time()
        while time.time() - t0 < 15:
            time.sleep(1)
            if is_ollama_server_running():
                return True
    except Exception as e:
        logger.warning(f"Erro ao iniciar Ollama: {e}")

    return False


class WxSetupDialog:
    """Interface gráfica wxPython para escolha do motor de IA na primeira execução."""

    def __init__(self):
        import wx
        self.wx = wx
        self.app = wx.App(False)
        self.selected_engine = "llama_cpp"
        self.setup_finished = False

        self.dialog = wx.Dialog(
            None,
            title="Jarvis AI - Configuração Inicial de IA",
            size=(560, 480),
            style=wx.DEFAULT_DIALOG_STYLE | wx.CENTER | wx.STAY_ON_TOP
        )
        self.dialog.SetBackgroundColour(wx.Colour(245, 247, 250))

        self._build_ui()
        self.dialog.Centre()

    def _build_ui(self):
        wx = self.wx
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # 1. Cabeçalho com Título e Instruções
        header_panel = wx.Panel(self.dialog)
        header_panel.SetBackgroundColour(wx.Colour(30, 41, 59))  # Slate dark
        header_sizer = wx.BoxSizer(wx.VERTICAL)

        title_lbl = wx.StaticText(header_panel, label="🤖 Jarvis AI — Seleção do Motor Neural")
        title_font = wx.Font(13, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        title_lbl.SetFont(title_font)
        title_lbl.SetForegroundColour(wx.Colour(255, 255, 255))
        header_sizer.Add(title_lbl, 0, wx.ALL, 12)

        sub_lbl = wx.StaticText(
            header_panel,
            label="Selecione como deseja executar os modelos de inteligência artificial offline no seu sistema:"
        )
        sub_lbl.SetForegroundColour(wx.Colour(203, 213, 225))
        header_sizer.Add(sub_lbl, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
        header_panel.SetSizer(header_sizer)

        main_sizer.Add(header_panel, 0, wx.EXPAND)

        # 2. Área de Opções (Radio Buttons)
        content_sizer = wx.BoxSizer(wx.VERTICAL)
        content_sizer.AddSpacer(12)

        # Opção 1: llama.cpp embutido
        self.rb_llama = wx.RadioButton(
            self.dialog,
            label="  🚀 Motor Padrão Embutido (llama.cpp)",
            style=wx.RB_GROUP
        )
        rb_font = wx.Font(10, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        self.rb_llama.SetFont(rb_font)
        self.rb_llama.SetValue(True)
        content_sizer.Add(self.rb_llama, 0, wx.LEFT | wx.RIGHT | wx.TOP, 16)

        desc_llama = wx.StaticText(
            self.dialog,
            label="     100% integrado e independente. Roda diretamente dentro do Jarvis sem\n     necessidade de instalar programas externos. Ultraleve e pronto para uso."
        )
        desc_llama.SetForegroundColour(wx.Colour(100, 116, 139))
        content_sizer.Add(desc_llama, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 16)

        content_sizer.AddSpacer(8)

        # Opção 2: Ollama
        self.rb_ollama = wx.RadioButton(
            self.dialog,
            label="  🦙 Ollama (Gerenciador Externo de IA)"
        )
        self.rb_ollama.SetFont(rb_font)
        content_sizer.Add(self.rb_ollama, 0, wx.LEFT | wx.RIGHT | wx.TOP, 16)

        desc_ollama = wx.StaticText(
            self.dialog,
            label="     Executa modelos via serviço Ollama. Se o Ollama não estiver instalado,\n     o Jarvis fará o download e instalação automática agora mesmo,\n     além de baixar o modelo Qwen 2.5 1.5B."
        )
        desc_ollama.SetForegroundColour(wx.Colour(100, 116, 139))
        content_sizer.Add(desc_ollama, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 16)

        main_sizer.Add(content_sizer, 0, wx.EXPAND | wx.ALL, 8)

        # 3. Barra de Progresso e Status
        progress_sizer = wx.BoxSizer(wx.VERTICAL)

        self.status_lbl = wx.StaticText(self.dialog, label="Selecione uma opção e clique em Continuar.")
        self.status_lbl.SetForegroundColour(wx.Colour(51, 65, 85))
        progress_sizer.Add(self.status_lbl, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)

        self.gauge = wx.Gauge(self.dialog, range=100, style=wx.GA_HORIZONTAL | wx.GA_SMOOTH)
        self.gauge.SetValue(0)
        self.gauge.Hide()
        progress_sizer.Add(self.gauge, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)

        self.detail_lbl = wx.StaticText(self.dialog, label="")
        self.detail_lbl.SetForegroundColour(wx.Colour(100, 116, 139))
        self.detail_lbl.Hide()
        progress_sizer.Add(self.detail_lbl, 0, wx.LEFT | wx.RIGHT, 12)

        main_sizer.Add(progress_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)

        main_sizer.AddStretchSpacer()

        # 4. Botões de Ação
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        btn_sizer.AddStretchSpacer()

        self.btn_confirm = wx.Button(self.dialog, label="Continuar com a Seleção", size=(190, 36))
        self.btn_confirm.SetBackgroundColour(wx.Colour(14, 165, 233))
        self.btn_confirm.SetForegroundColour(wx.Colour(255, 255, 255))
        self.btn_confirm.SetFont(wx.Font(10, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        self.btn_confirm.Bind(wx.EVT_BUTTON, self._on_confirm_click)
        btn_sizer.Add(self.btn_confirm, 0, wx.ALL, 16)

        main_sizer.Add(btn_sizer, 0, wx.EXPAND)

        self.dialog.SetSizer(main_sizer)

    def _update_progress(self, percent: int, status_text: str, detail_text: str = ""):
        """Atualização de UI thread-safe chamada pelo worker via wx.CallAfter."""
        self.gauge.Show()
        self.detail_lbl.Show()
        self.gauge.SetValue(max(0, min(100, percent)))
        self.status_lbl.SetLabel(status_text)
        self.detail_lbl.SetLabel(detail_text)
        self.dialog.Layout()

    def _on_confirm_click(self, event):
        if self.rb_llama.GetValue():
            # Motor padrão llama.cpp selecionado
            self.selected_engine = "llama_cpp"
            save_settings({"ai_engine": "llama_cpp", "setup_completed": True})
            logger.info("Motor padrão (llama.cpp) selecionado pelo usuário.")
            self.dialog.EndModal(wx.ID_OK)
        else:
            # Ollama selecionado: inicia processo de verificação/instalação/pull
            self.selected_engine = "ollama"
            self.rb_llama.Disable()
            self.rb_ollama.Disable()
            self.btn_confirm.Disable()
            self.btn_confirm.SetLabel("Instalando...")

            threading.Thread(target=self._run_ollama_setup_pipeline, daemon=True).start()

    def _run_ollama_setup_pipeline(self):
        """Worker em segundo plano para verificação, download, instalação e pull do modelo no Ollama."""
        wx = self.wx
        try:
            # 1. Verifica se o Ollama já está instalado
            if not is_ollama_installed():
                wx.CallAfter(self._update_progress, 5, "Ollama não encontrado. Baixando instalador oficial...", "Conectando ao servidor...")
                installer_path = CACHE_DIR / "OllamaSetup.exe"
                CACHE_DIR.mkdir(parents=True, exist_ok=True)

                self._download_ollama_installer(installer_path)

                wx.CallAfter(self._update_progress, 40, "Instalando o Ollama no Windows...", "Aguarde a conclusão da instalação silenciosa...")
                res = subprocess.run([str(installer_path), "/silent"], capture_output=True, text=True)
                logger.info(f"Instalação do Ollama concluída (código {res.returncode}).")

                # Remove instalador temporário para economizar espaço
                try:
                    installer_path.unlink(missing_ok=True)
                except Exception:
                    pass

            # 2. Inicia o serviço do Ollama
            wx.CallAfter(self._update_progress, 50, "Iniciando serviço do Ollama...", "Verificando porta 11434...")
            if not start_ollama_service():
                wx.CallAfter(self._update_progress, 50, "Aguardando inicialização do Ollama...", "Tentando estabelecer conexão...")
                time.sleep(3)

            if not is_ollama_server_running():
                wx.CallAfter(self._update_progress, 0, "Aviso: Não foi possível iniciar o serviço do Ollama.", "Tentaremos conectar na inicialização do daemon.")

            # 3. Baixar o modelo Qwen 2.5 1.5B no Ollama
            wx.CallAfter(self._update_progress, 60, f"Verificando modelo {OLLAMA_DEFAULT_MODEL} no Ollama...", "")
            self._ensure_ollama_model_pulled(OLLAMA_DEFAULT_MODEL)

            # 4. Finalizado com sucesso
            wx.CallAfter(self._update_progress, 100, "Configuração concluída com sucesso!", "Iniciando o Jarvis...")
            save_settings({"ai_engine": "ollama", "setup_completed": True, "ollama_model": OLLAMA_DEFAULT_MODEL})
            time.sleep(1.5)
            wx.CallAfter(self.dialog.EndModal, wx.ID_OK)

        except Exception as e:
            logger.exception(f"Erro durante configuração do Ollama: {e}")
            wx.CallAfter(self._update_progress, 0, f"Erro: {e}", "Recorrendo ao motor padrão...")
            save_settings({"ai_engine": "llama_cpp", "setup_completed": True})
            time.sleep(2)
            wx.CallAfter(self.dialog.EndModal, wx.ID_OK)

    def _download_ollama_installer(self, dest: Path):
        """Baixa o instalador do Ollama com acompanhamento de porcentagem."""
        import urllib.request
        wx = self.wx
        req = urllib.request.Request(OLLAMA_INSTALLER_URL, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            total_size = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            chunk_size = 1024 * 512

            with open(dest, "wb") as f:
                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)

                    if total_size > 0:
                        pct = int((downloaded / total_size) * 35) + 5  # Mapeia de 5% a 40%
                        mb_down = downloaded / (1024 * 1024)
                        mb_tot = total_size / (1024 * 1024)
                        wx.CallAfter(self._update_progress, pct, "Baixando instalador do Ollama...", f"{mb_down:.1f} MB de {mb_tot:.1f} MB ({int(downloaded/total_size*100)}%)")

    def _ensure_ollama_model_pulled(self, model_name: str):
        """Verifica se o modelo já existe no Ollama e faz pull com progresso se necessário."""
        import urllib.request
        wx = self.wx

        # Verifica se já está na lista de modelos locais
        try:
            req = urllib.request.Request("http://127.0.0.1:11434/api/tags")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                existing = [m.get("name", "").split(":")[0] for m in data.get("models", [])]
                if model_name.split(":")[0] in existing or model_name in [m.get("name", "") for m in data.get("models", [])]:
                    logger.info(f"Modelo {model_name} já disponível no Ollama.")
                    return
        except Exception as e:
            logger.debug(f"Verificação de tags do Ollama: {e}")

        # Faz o pull com streaming de progresso
        logger.info(f"Iniciando pull do modelo {model_name} no Ollama...")
        pull_url = "http://127.0.0.1:11434/api/pull"
        payload = json.dumps({"name": model_name, "stream": True}).encode("utf-8")
        req = urllib.request.Request(pull_url, data=payload, headers={"Content-Type": "application/json"}, method="POST")

        with urllib.request.urlopen(req, timeout=3600) as resp:
            for raw_line in resp:
                line_str = raw_line.decode("utf-8").strip()
                if not line_str:
                    continue
                try:
                    event = json.loads(line_str)
                    status = event.get("status", "")
                    completed = event.get("completed", 0)
                    total = event.get("total", 0)

                    if total > 0:
                        ratio = completed / total
                        pct = 60 + int(ratio * 38)  # Mapeia de 60% a 98%
                        mb_comp = completed / (1024 * 1024)
                        mb_tot = total / (1024 * 1024)
                        wx.CallAfter(
                            self._update_progress,
                            pct,
                            f"Baixando modelo {model_name} no Ollama...",
                            f"{status} — {mb_comp:.1f} MB de {mb_tot:.1f} MB ({int(ratio*100)}%)"
                        )
                    else:
                        wx.CallAfter(self._update_progress, 70, f"Baixando modelo {model_name} no Ollama...", status)
                except Exception:
                    pass

    def run(self) -> str:
        """Executa a janela modal wxPython e retorna o motor escolhido."""
        self.dialog.ShowModal()
        self.dialog.Destroy()
        self.app.Destroy()
        return self.selected_engine


def _fallback_tkinter_setup() -> str:
    """Fallback simples com tkinter caso wxPython falhe na inicialização."""
    import tkinter as tk
    from tkinter import messagebox

    root = tk.Tk()
    root.title("Jarvis AI - Configuração Inicial")
    root.geometry("460x300")
    root.eval('tk::PlaceWindow . center')

    choice_var = tk.StringVar(value="llama_cpp")

    lbl = tk.Label(root, text="Selecione o Motor de IA do Jarvis:", font=("Helvetica", 12, "bold"))
    lbl.pack(pady=15)

    r1 = tk.Radiobutton(root, text="Motor Padrão Embutido (llama.cpp) — Recomendado", variable=choice_var, value="llama_cpp", font=("Helvetica", 10))
    r1.pack(anchor="w", padx=30, pady=8)

    r2 = tk.Radiobutton(root, text="Ollama (Gerenciador Externo)", variable=choice_var, value="ollama", font=("Helvetica", 10))
    r2.pack(anchor="w", padx=30, pady=8)

    selected = ["llama_cpp"]

    def on_ok():
        selected[0] = choice_var.get()
        save_settings({"ai_engine": selected[0], "setup_completed": True})
        root.destroy()

    btn = tk.Button(root, text="Continuar", command=on_ok, width=18, bg="#0ea5e9", fg="white", font=("Helvetica", 10, "bold"))
    btn.pack(pady=25)

    root.mainloop()
    return selected[0]


def check_and_run_first_time_setup() -> str:
    """
    Verifica se a configuração inicial já foi realizada.
    Se for a primeira execução (ou se chamada explicitamente), exibe a janela de escolha.
    Retorna o motor selecionado: 'llama_cpp' ou 'ollama'.
    """
    settings = load_settings()
    if settings.get("setup_completed", False):
        return settings.get("ai_engine", "llama_cpp")

    logger.info("Primeira execução detectada. Abrindo assistente gráfico de seleção de motor...")

    try:
        dialog = WxSetupDialog()
        engine = dialog.run()
        return engine
    except Exception as e:
        logger.warning(f"Não foi possível abrir janela wxPython ({e}). Usando fallback...")
        try:
            return _fallback_tkinter_setup()
        except Exception as e2:
            logger.warning(f"Fallback gráfico indisponível ({e2}). Adotando motor padrão.")
            save_settings({"ai_engine": "llama_cpp", "setup_completed": True})
            return "llama_cpp"


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    chosen = check_and_run_first_time_setup()
    print("Motor escolhido:", chosen)
