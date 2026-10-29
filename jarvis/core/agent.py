import logging
from typing import Optional, Dict, Any
from jarvis.core.agy_provider import AgyProvider
from jarvis.core.local_llm_provider import LocalLLMProvider
from jarvis.rag.memory import JarvisRAG
from jarvis.tools.system_tools import SystemTools
from jarvis.config import config

logger = logging.getLogger("Jarvis.Agent")

JARVIS_SYSTEM_PROMPT = """Você é JARVIS, um assistente de inteligência artificial de elite, proativo, educado e eficiente.
Seu operador é o usuário que está interagindo com você.
Diretrizes:
1. Você tem acesso a um conjunto de ferramentas (tools/MCP). Sempre que a solicitação do usuário puder ser atendida ou envolver uma ação, checagem ou controle do sistema suportado por uma ferramenta, você DEVE acionar a ferramenta correspondente imediatamente via tool_calls. NUNCA diga em texto que 'vai verificar', 'está checando' ou 'posso usar a função' sem realmente acionar a ferramenta.
2. Seja direto, conciso e natural na fala. Responda em no máximo duas ou três frases bem articuladas.
3. Quando houver contexto recuperado da memória (RAG), use-o para responder com conhecimento prévio.
4. Se o usuário pedir para lembrar de algo, confirme brevemente que a memória foi gravada.
5. Responda sempre em português brasileiro fluente.
"""

class JarvisAssistant:
    """
    Núcleo unificado do Jarvis. 
    Utiliza o motor Local LLM (Qwen 2.5 1.5B 100% offline) por padrão ou AGY se configurado.
    """

    def __init__(self, voice=None):
        try:
            self.rag = JarvisRAG()
        except (OSError, Exception) as e:
            logger.warning(f"RAG ChromaDB inicializado em modo reduzido: {e}")
            self.rag = None

        self.tools = SystemTools()
        self.voice = voice
        self.provider_type = config.AI_PROVIDER
        
        if self.provider_type == "local":
            logger.info("Inicializando Jarvis com Motor de IA Local (100% Offline)...")
            try:
                self.llm = LocalLLMProvider(config.LOCAL_MODEL_PATH)
            except (OSError, Exception) as e:
                logger.warning(f"Falha ao instanciar LocalLLMProvider ({e}). Usando modo de compatibilidade universal.")
                self.llm = None
        else:
            logger.info("Inicializando Jarvis com Motor AGY CLI...")
            self.llm = AgyProvider()

    def ask(self, user_prompt: str, with_rag: bool = True) -> str:
        """Processa a pergunta utilizando o cérebro local e RAG com resposta ultra rápida."""
        lower = user_prompt.lower()

        # ⚡ Fast-Path de Bluetooth nativo (resposta em milissegundos)
        if "bluetooth" in lower:
            from mcp_servers.jarvis_system import server as mcp_system
            if any(w in lower for w in ["desligar", "desliga", "desative", "desativar", "apagar", "desconectar"]):
                res = mcp_system.set_bluetooth_radio_state("off")
                return "Bluetooth desligado com sucesso." if "desligado" in res.lower() or "off" in res.lower() else res
            elif any(w in lower for w in ["ligar", "liga", "ative", "ativar", "habilitar"]):
                res = mcp_system.set_bluetooth_radio_state("on")
                return "Bluetooth ativado com sucesso." if "ativado" in res.lower() or "on" in res.lower() else res
            else:
                return mcp_system.get_bluetooth_devices()

        # ⚡ Fast-Path de Status da Máquina
        if "status do sistema" in lower or "status do pc" in lower or "como está a máquina" in lower:
            status = self.tools.get_system_status()
            return (
                f"Status do sistema: "
                f"CPU em {status['cpu_percent']}, "
                f"memória RAM com {status['ram_used_gb']} em uso "
                f"e {status['disk_free_gb']} livres no disco."
            )

        # ⚡ Fast-Path de Atualização do Jarvis
        if any(w in lower for w in [
            "atualização", "atualizações", "atualizacao", "atualizacoes",
            "atualizar", "atualize", "update",
            "nova versão", "nova versao", "novas versões", "novas versoes",
            "novas versão", "novas versao", "nota versão", "nota versao",
            "versões", "versoes", "versão", "versao"
        ]):
            from jarvis.core.updater import JarvisUpdater
            import time
            updater = JarvisUpdater()
            info = updater.check_for_update()
            if not info:
                return f"O Jarvis já está em sua versão mais recente ({updater.current_version}). Nenhuma atualização pendente."
            
            tag = info.get("tag_name", "")
            if "instalar" in lower or "atualize" in lower or "sim" in lower:
                if self.voice:
                    try:
                        self.voice.speak(f"Iniciando download da atualização {tag}. Aguarde um instante.")
                    except Exception:
                        pass

                last_spoken_time = [0.0]
                last_spoken_pct = [-1]

                def on_progress(msg: str, pct: int = 0, current_mb: float = 0.0, total_mb: float = 0.0, description: str = ""):
                    if pct <= 0:
                        return
                    now = time.time()
                    if now - last_spoken_time[0] >= 5.0 and pct != last_spoken_pct[0]:
                        last_spoken_time[0] = now
                        last_spoken_pct[0] = pct
                        if self.voice:
                            try:
                                self.voice.speak(f"Download da atualização: {pct} por cento concluído.")
                            except Exception:
                                pass

                success = updater.download_and_install_update(info, status_callback=on_progress)
                if success:
                    final_msg = f"A versão {tag} foi baixada e o instalador foi iniciado para atualizar o sistema."
                    if self.voice:
                        try:
                            self.voice.speak(final_msg)
                        except Exception:
                            pass
                    return final_msg
                else:
                    return f"Encontrei a versão {tag}, mas ocorreu uma falha ao tentar baixar o instalador."
            else:
                return f"Uma nova versão ({tag}) está disponível no GitHub. Peça para eu atualizar para instalar automaticamente."

        # RAG Context Retrieval (Ignorado em comandos de ação direta para economizar ~150ms)
        is_direct_command = any(lower.startswith(prefix) for prefix in [
            "abra", "abrir", "inicie", "executar", "feche", "fechar", "aumente", "abaixe",
            "volume", "desligue", "ligue", "silencie", "pause", "play", "toque", "coloque"
        ])

        rag_context = ""
        if with_rag and not is_direct_command and self.rag is not None:
            try:
                memories = self.rag.query(user_prompt, n_results=2)
                if memories:
                    rag_context = "Contexto da Memória:\n"
                    for i, m in enumerate(memories, 1):
                        rag_context += f"- {m['content']}\n"
                    rag_context += "\n"
            except Exception as e:
                logger.debug(f"Falha ao consultar memórias RAG: {e}")

        prompt_with_context = f"{rag_context}Pergunta do usuário: {user_prompt}"

        # Memorização automática
        if self.rag is not None and any(trigger in lower for trigger in ["aprenda que", "lembre-se que", "guarde isso", "grave isso", "salve que"]):
            try:
                self.rag.add_knowledge(text=user_prompt, category="aprendizado_usuario")
            except Exception as e:
                logger.debug(f"Falha ao gravar memória: {e}")

        # Inferência
        if self.llm is not None:
            return self.llm.generate(
                prompt=prompt_with_context,
                system_instruction=JARVIS_SYSTEM_PROMPT
            )
        else:
            from jarvis.core.local_llm_provider import LocalLLMProvider
            dummy = LocalLLMProvider.__new__(LocalLLMProvider)
            dummy.mcp_registry = from_agent_mcp() if 'from_agent_mcp' in locals() else None
            from jarvis.core.mcp_registry import MCPRegistry
            dummy.mcp_registry = MCPRegistry()
            return dummy._fallback_generate(user_prompt)

    def learn(self, title_or_category: str, content: str) -> str:
        if self.rag:
            try:
                doc_id = self.rag.add_knowledge(text=content, category=title_or_category)
                return f"Aprendizado registrado com sucesso na memória persistente (ID: {doc_id})."
            except Exception as e:
                return f"Não foi possível salvar na memória no momento: {e}"
        return "Memória persistente operando em modo leve."
