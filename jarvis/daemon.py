import time
import sys
import threading
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from pynput import keyboard

from jarvis.core.agent import JarvisAssistant
from jarvis.voice.engine import VoiceEngine
from jarvis.config import config

console = Console()

class JarvisDaemon:
    """
    Executa o Jarvis em segundo plano / modo interativo com atalhos globais de teclado (Hotkeys).
    """

    def __init__(self, enable_voice: bool = True):
        self.agent = JarvisAssistant()
        self.voice = VoiceEngine() if enable_voice else None
        self.running = True
        self.is_processing = False

    def on_hotkey_activated(self):
        """Atalho de ativação (Ctrl + Alt + J): escuta pelo microfone ou abre prompt."""
        if self.is_processing:
            return

        self.is_processing = True
        console.print("\n[bold cyan]⚡ Jarvis ativado via Hotkey![/bold cyan]")

        try:
            if self.voice:
                self.voice.speak("Pois não, senhor? Em que posso ajudar?")
                user_text = self.voice.listen(timeout=6, phrase_time_limit=10)
            else:
                user_text = Prompt.ask("[bold green]Comando para o Jarvis[/bold green]")

            if user_text:
                console.print(f"[yellow]Processando com AGY e RAG...[/yellow]")
                response = self.agent.ask(user_text)
                console.print(Panel(response, title="[bold blue]JARVIS[/bold blue]", border_style="cyan"))

                if self.voice:
                    self.voice.speak(response)
        except Exception as e:
            console.print(f"[red]Erro durante atendimento: {e}[/red]")
        finally:
            self.is_processing = False

    def start_hotkey_listener(self):
        """Inicia escuta global de atalhos em uma thread separada."""
        def for_canonical(f):
            return lambda k: f(listener.canonical(k))

        hotkey = keyboard.HotKey(
            keyboard.HotKey.parse(config.HOTKEY_LISTEN),
            self.on_hotkey_activated
        )

        listener = keyboard.Listener(
            on_press=for_canonical(hotkey.press),
            on_release=for_canonical(hotkey.release)
        )
        listener.daemon = True
        listener.start()
        return listener

    def run_interactive_loop(self):
        """Modo loop no terminal mantendo o daemon ativo."""
        console.print(Panel.fit(
            f"[bold cyan]JARVIS ONLINE[/bold cyan]\n"
            f"[dim]Provedor de IA:[/dim] Antigravity CLI (agy)\n"
            f"[dim]Memória:[/dim] ChromaDB RAG Vector Store\n"
            f"[dim]Atalho Global:[/dim] {config.HOTKEY_LISTEN} (Pressione para falar a qualquer momento)\n"
            f"[dim]Digite 'voz' para falar via microfone ou 'sair' para encerrar.[/dim]",
            border_style="green"
        ))

        self.start_hotkey_listener()

        while self.running:
            try:
                user_input = Prompt.ask("\n[bold green]Você[/bold green]")
                if not user_input.strip():
                    continue

                if user_input.lower() in ["sair", "exit", "quit"]:
                    console.print("[yellow]Desconectando sistemas do Jarvis... Até logo, senhor.[/yellow]")
                    break

                if user_input.lower() == "voz":
                    if self.voice:
                        self.voice.speak("Ouvindo, senhor.")
                        spoken = self.voice.listen()
                        if spoken:
                            user_input = spoken
                        else:
                            continue
                    else:
                        console.print("[red]Engine de voz desabilitada.[/red]")
                        continue

                console.print("[dim cyan]Consultando RAG e raciocinando via AGY...[/dim cyan]")
                response = self.agent.ask(user_input)
                console.print(Panel(response, title="[bold blue]JARVIS[/bold blue]", border_style="cyan"))

                if self.voice and "--mute" not in sys.argv:
                    self.voice.speak(response)

            except (KeyboardInterrupt, EOFError):
                break

if __name__ == "__main__":
    from jarvis.core.single_instance import ensure_single_instance
    ensure_single_instance()

    daemon = JarvisDaemon(enable_voice=True)
    daemon.run_interactive_loop()
