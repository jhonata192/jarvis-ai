import os
import json
import logging
import hashlib
from typing import List, Dict, Any, Optional
from pathlib import Path
import chromadb
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings

from jarvis.config import config

logger = logging.getLogger("Jarvis.RAG")

class GeminiEmbeddingFunction(EmbeddingFunction):
    """
    Função de embedding usando Google GenAI com fallback para representações nativas
    quando a API Key não for fornecida.
    """
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or config.GEMINI_API_KEY
        self.model = model or config.EMBEDDING_MODEL
        self.client = None
        
        if self.api_key:
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
                logger.info("Cliente Google GenAI configurado com sucesso para embeddings.")
            except Exception as e:
                logger.warning(f"Não foi possível inicializar o cliente Google GenAI: {e}")

    def __call__(self, input: Documents) -> Embeddings:
        if self.client:
            try:
                response = self.client.models.embed_content(
                    model=self.model,
                    contents=input
                )
                embeddings = [e.values for e in response.embeddings]
                return embeddings
            except Exception as e:
                logger.error(f"Erro na API de Embeddings do Gemini: {e}. Usando fallback local.")

        # Fallback local determinístico e leve (se não houver chave de API configurada no momento)
        embeddings = []
        for text in input:
            vec = self._deterministic_vector(text, dim=768)
            embeddings.append(vec)
        return embeddings

    def _deterministic_vector(self, text: str, dim: int = 768) -> List[float]:
        # Hash SHA-256 expandido para criar um vetor de teste sem travar
        seed = int(hashlib.md5(text.encode('utf-8')).hexdigest(), 16)
        import random
        rng = random.Random(seed)
        return [rng.uniform(-1.0, 1.0) for _ in range(dim)]


class JarvisRAG:
    """
    Sistema de Memória RAG do Jarvis.
    Armazena aprendizados, tarefas concluídas, notas, comandos e histórico.
    """

    def __init__(self):
        persist_path = Path(config.CHROMA_PERSIST_DIR)
        persist_path.mkdir(parents=True, exist_ok=True)
        
        self.chroma_client = chromadb.PersistentClient(path=str(persist_path))
        self.embedding_fn = GeminiEmbeddingFunction()
        
        self.collection = self.chroma_client.get_or_create_collection(
            name="jarvis_memory",
            embedding_function=self.embedding_fn,
            metadata={"description": "Memória de aprendizados, histórico e funções do Jarvis"}
        )
        
        # Sincroniza arquivos de aprendizado se existirem
        self.sync_learnings_dir()

    def add_knowledge(self, text: str, category: str = "aprendizado", metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Adiciona um novo conhecimento ou aprendizado à memória persistente.
        """
        doc_id = hashlib.sha256(f"{category}:{text}".encode('utf-8')).hexdigest()[:16]
        meta = metadata or {}
        meta.update({
            "category": category,
            "created_at": str(os.path.getmtime(config.CHROMA_PERSIST_DIR) if os.path.exists(config.CHROMA_PERSIST_DIR) else "now")
        })

        self.collection.upsert(
            documents=[text],
            metadatas=[meta],
            ids=[doc_id]
        )
        logger.info(f"Conhecimento indexado com sucesso [{category}] ID: {doc_id}")
        return doc_id

    def query(self, query_text: str, n_results: int = 3, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Pesquisa itens semanticamente relevantes para a consulta do usuário.
        """
        where_filter = {"category": category} if category else None
        
        try:
            results = self.collection.query(
                query_texts=[query_text],
                n_results=n_results,
                where=where_filter
            )

            retrieved = []
            if results and results.get("documents") and results["documents"][0]:
                for doc, meta, distance in zip(
                    results["documents"][0],
                    results["metadatas"][0],
                    results["distances"][0] if "distances" in results and results["distances"] else [0]*len(results["documents"][0])
                ):
                    retrieved.append({
                        "content": doc,
                        "metadata": meta,
                        "distance": distance
                    })
            return retrieved
        except Exception as e:
            logger.error(f"Erro ao consultar memória RAG: {e}")
            return []

    def sync_learnings_dir(self):
        """
        Lê arquivos .md ou .txt em data/learnings/ e indexa automaticamente na memória.
        """
        learn_path = Path(config.LEARNINGS_DIR)
        learn_path.mkdir(parents=True, exist_ok=True)

        for file_path in learn_path.glob("*.*"):
            if file_path.suffix.lower() in [".md", ".txt", ".json"]:
                try:
                    content = file_path.read_text(encoding="utf-8")
                    if content.strip():
                        # Adiciona chunks do arquivo
                        self.add_knowledge(
                            text=content,
                            category="arquivo_aprendizado",
                            metadata={"source_file": file_path.name}
                        )
                except Exception as e:
                    logger.warning(f"Falha ao ler {file_path}: {e}")
