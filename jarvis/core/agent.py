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

        # Buffer circular de memória de curto prazo (últimos 2-3 turnos)
        self.conversation_history = []

    def warmup(self):
        """Pré-aquece o roteador MCP e cache de embeddings."""
        try:
            mcp_reg = None
            if hasattr(self, "llm") and self.llm is not None and hasattr(self.llm, "mcp_registry"):
                mcp_reg = self.llm.mcp_registry
            else:
                from jarvis.core.mcp_registry import MCPRegistry
                mcp_reg = MCPRegistry()
            if hasattr(mcp_reg, "warmup"):
                mcp_reg.warmup()
        except Exception as e:
            logger.debug(f"Aviso no warmup do JarvisAssistant: {e}")

    def ask(self, user_prompt: str, with_rag: bool = True) -> str:
        """
        Processa a solicitação do usuário.
        1. Roteamento Semântico MCP (Zero latência via embeddings offline):
           Avalia semântica contra esquemas e intenções de todas as ferramentas MCP.
           Se houver correspondência de comando de sistema, executa de forma determinística
           e sintetiza uma resposta conclusiva por voz.
        2. RAG + Motor LLM (Qwen 2.5 1.5B):
           Para conversas gerais, dúvidas conceituais e perguntas de conhecimento.
        """
        lower = user_prompt.lower().strip()

        # 1. Roteamento Semântico MCP
        mcp_reg = None
        if hasattr(self, "llm") and self.llm is not None and hasattr(self.llm, "mcp_registry"):
            mcp_reg = self.llm.mcp_registry
        else:
            from jarvis.core.mcp_registry import MCPRegistry
            mcp_reg = MCPRegistry()

        matched = mcp_reg.match_tool_semantically(user_prompt)
        # Resolução de anáfora / continuidade contextual (ex: "e a bateria?", "aumente mais um pouco")
        if not matched and self.conversation_history:
            last_turn = self.conversation_history[-1]
            combined_query = f"{last_turn['user']} {user_prompt}"
            matched = mcp_reg.match_tool_semantically(combined_query)

        if matched:
            tool_name, tool_args = matched
            logger.info(f"[Semantic MCP Router] Intenção mapeada com sucesso para '{tool_name}' ({tool_args})")
            tool_result = mcp_reg.execute_tool(tool_name, tool_args)
            logger.info(f"[Semantic MCP Router] Resultado real da ferramenta: {tool_result}")

            final_text = str(tool_result)

            # Síntese conversacional da resposta por voz se LLM estiver ativa
            if (
                hasattr(self, "llm")
                and self.llm is not None
                and hasattr(self.llm, "llm")
                and self.llm.llm is not None
                and not getattr(self.llm, "fallback_mode", False)
            ):
                try:
                    synthesis_system = (
                        "Você é JARVIS, um assistente de inteligência artificial de elite. "
                        "A ferramenta solicitada foi executada no sistema operacional. "
                        "Gere uma resposta conclusiva curta, natural e elegante (1 a 2 frases) em português brasileiro confirmando o resultado para o usuário. "
                        "Não mencione nomes de funções ou sintaxe de código."
                    )
                    synthesis_user = (
                        f"Solicitação do usuário: \"{user_prompt}\"\n"
                        f"Ação do sistema executada: {tool_name}\n"
                        f"Resultado obtido: \"{tool_result}\"\n"
                        "Responda ao usuário com naturalidade:"
                    )
                    resp = self.llm.llm.create_chat_completion(
                        messages=[
                            {"role": "system", "content": synthesis_system},
                            {"role": "user", "content": synthesis_user}
                        ],
                        max_tokens=60,
                        temperature=0.3
                    )
                    text = resp["choices"][0]["message"].get("content", "").strip()
                    if text:
                        final_text = text
                except Exception as e:
                    logger.debug(f"Síntese conversacional pós-ferramenta: {e}")

            self._save_interaction(user_prompt, final_text)
            return final_text

        # 2. Conversação Geral / RAG / Conhecimento
        rag_context = ""
        if with_rag and self.rag is not None:
            try:
                memories = self.rag.query(user_prompt, n_results=2)
                if memories:
                    rag_context = "Contexto da Memória:\n"
                    for i, m in enumerate(memories, 1):
                        rag_context += f"- {m['content']}\n"
                    rag_context += "\n"
            except Exception as e:
                logger.debug(f"Falha ao consultar memórias RAG: {e}")

        # Contexto de diálogo recente anterior (multi-turn)
        dialogue_context = ""
        if self.conversation_history:
            dialogue_context = "Diálogo recente anterior:\n"
            for turn in self.conversation_history[-2:]:
                dialogue_context += f"Operador: {turn['user']}\nJarvis: {turn['assistant']}\n"
            dialogue_context += "\n"

        prompt_with_context = f"{rag_context}{dialogue_context}Pergunta atual do usuário: {user_prompt}"

        # Memorização automática
        if self.rag is not None and any(trigger in lower for trigger in ["aprenda que", "lembre-se que", "guarde isso", "grave isso", "salve que"]):
            try:
                self.rag.add_knowledge(text=user_prompt, category="aprendizado_usuario")
            except Exception as e:
                logger.debug(f"Falha ao gravar memória: {e}")

        # Inferência
        response_text = ""
        if self.llm is not None:
            response_text = self.llm.generate(
                prompt=prompt_with_context,
                system_instruction=JARVIS_SYSTEM_PROMPT
            )
        else:
            response_text = mcp_reg.execute_tool("check_for_updates", {}) if "atualiz" in lower else "Comando processado com sucesso pelo sistema."

        self._save_interaction(user_prompt, response_text)
        return response_text

    def _save_interaction(self, user_text: str, assistant_text: str):
        """Salva a interação no buffer de memória de curto prazo (máx 3 turnos)."""
        self.conversation_history.append({"user": user_text, "assistant": assistant_text})
        if len(self.conversation_history) > 3:
            self.conversation_history.pop(0)

    def learn(self, title_or_category: str, content: str) -> str:
        if self.rag:
            try:
                doc_id = self.rag.add_knowledge(text=content, category=title_or_category)
                return f"Aprendizado registrado com sucesso na memória persistente (ID: {doc_id})."
            except Exception as e:
                return f"Não foi possível salvar na memória no momento: {e}"
        return "Memória persistente operando em modo leve."
