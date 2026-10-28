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
1. Seja direto, conciso e natural na fala. Responda em no máximo duas ou três frases bem articuladas.
2. Quando houver contexto recuperado da memória (RAG), use-o para responder com conhecimento prévio.
3. Se o usuário pedir para lembrar de algo, confirme brevemente que a memória foi gravada.
4. Responda sempre em português brasileiro fluente.
"""

class JarvisAssistant:
    """
    Núcleo unificado do Jarvis. 
    Utiliza o motor Local LLM (Qwen 2.5 1.5B 100% offline) por padrão ou AGY se configurado.
    """

    def __init__(self):
        self.rag = JarvisRAG()
        self.tools = SystemTools()
        self.provider_type = config.AI_PROVIDER
        
        if self.provider_type == "local":
            logger.info("Inicializando Jarvis com Motor de IA Local (100% Offline)...")
            self.llm = LocalLLMProvider(config.LOCAL_MODEL_PATH)
        else:
            logger.info("Inicializando Jarvis com Motor AGY CLI...")
            self.llm = AgyProvider()

    def ask(self, user_prompt: str, with_rag: bool = True) -> str:
        """Processa a pergunta utilizando o cérebro local e RAG com resposta ultra rápida."""
        lower = user_prompt.lower()

        # ⚡ Fast-Path de Bluetooth nativo (resposta em milissegundos)
        if "bluetooth" in lower:
            return self.tools.get_bluetooth_devices()

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
        if any(w in lower for w in ["atualização", "atualizações", "atualizacao", "atualizacoes", "atualizar", "atualize", "update", "nova versão", "nova versao"]):
            from jarvis.core.updater import JarvisUpdater
            updater = JarvisUpdater()
            info = updater.check_for_update()
            if not info:
                return f"O Jarvis já está em sua versão mais recente ({updater.current_version}). Nenhuma atualização pendente."
            
            tag = info.get("tag_name", "")
            if "instalar" in lower or "atualize" in lower or "sim" in lower:
                success = updater.download_and_install_update(info)
                if success:
                    return f"A versão {tag} foi baixada e o instalador foi iniciado para atualizar o sistema."
                else:
                    return f"Encontrei a versão {tag}, mas ocorreu uma falha ao tentar baixar o instalador."
            else:
                return f"Uma nova versão ({tag}) está disponível no GitHub. Peça para eu atualizar para instalar automaticamente."

        # RAG Context Retrieval
        rag_context = ""
        if with_rag:
            memories = self.rag.query(user_prompt, n_results=2)
            if memories:
                rag_context = "Contexto da Memória:\n"
                for i, m in enumerate(memories, 1):
                    rag_context += f"- {m['content']}\n"
                rag_context += "\n"

        prompt_with_context = f"{rag_context}Pergunta do usuário: {user_prompt}"

        # Memorização automática
        if any(trigger in lower for trigger in ["aprenda que", "lembre-se que", "guarde isso", "grave isso", "salve que"]):
            self.rag.add_knowledge(text=user_prompt, category="aprendizado_usuario")

        # Inferência
        return self.llm.generate(
            prompt=prompt_with_context,
            system_instruction=JARVIS_SYSTEM_PROMPT
        )

    def learn(self, title_or_category: str, content: str) -> str:
        doc_id = self.rag.add_knowledge(text=content, category=title_or_category)
        return f"Aprendizado registrado com sucesso na memória persistente (ID: {doc_id})."
