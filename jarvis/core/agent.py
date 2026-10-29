import logging
from typing import Optional, Dict, Any
from jarvis.core.agy_provider import AgyProvider
from jarvis.core.local_llm_provider import LocalLLMProvider
from jarvis.rag.memory import JarvisRAG
from jarvis.tools.system_tools import SystemTools
from jarvis.config import config

logger = logging.getLogger("Jarvis.Agent")

JARVIS_SYSTEM_PROMPT = """Você é JARVIS, um agente autônomo de inteligência artificial de elite, proativo, direto e altamente eficiente.
Você opera no computador do usuário como um guardião inteligente do sistema (Warden / Agentic Loop).

Diretrizes Operacionais de Agente (Padrão ReAct / Hermes):
1. **Prioridade Absoluta de Ação (Tools/MCP):** Você tem acesso a ferramentas de sistema via MCP. Sempre que a solicitação do operador exigir consultar dados do sistema, alterar estados, verificar atualizações ou baixar/instalar programas, você DEVE emitir a chamada de ferramenta correspondente (<tool_call>).
2. **Proibição de Simulação Conversacional:** NUNCA responda dizendo apenas "estou pronto para baixar", "vou verificar", "aqui está" ou "posso fazer isso" sem emitir a chamada de ferramenta. Falar sem agir é estritamente proibido.
3. **Loop de Observação:** Após a execução de uma ferramenta, você receberá a [Observation] com o resultado real. Analise o resultado e, se o objetivo foi concluído, responda ao usuário de forma natural, curta e conclusiva.
4. **Variações Fonéticas de Voz:** Transcrições de voz podem sofrer pequenas variações (ex: 'blotuf', 'blutuf', 'blutuff', 'bluetuf' = Bluetooth; 'atuali', 'atuallize' = atualizar). Identifique a intenção e execute a ferramenta correta.
5. **Comunicação por Voz:** Mantenha as respostas finais concisas (1 a 2 frases), profissionais e sempre em português brasileiro fluente.
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
        """
        Processa a solicitação do usuário delegando 100% da decisão para a IA (LLM).
        A LLM avalia autonomamente as ferramentas MCP disponíveis e decide quando chamá-las.
        """
        lower = user_prompt.lower()

        # RAG Context Retrieval (Ignorado em comandos curtos de ação direta para economizar tempo)
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
            from jarvis.core.mcp_registry import MCPRegistry
            dummy = LocalLLMProvider.__new__(LocalLLMProvider)
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
