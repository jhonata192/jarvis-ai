# Base de Conhecimento e Aprendizados do Jarvis

## Projeto Jarvis AI
- Arquitetura: Desenvolvido em Python 3.11 com modularização em `jarvis/`.
- Provedor de IA: Antigravity CLI (`agy`) operando via execução de processos subprocess com modo `--dangerously-skip-permissions` para automação total de ferramentas.
- Memória Vetorial (RAG): ChromaDB persistente em `jarvis/memory_data/chromadb`.
- Embeddings: Modelo Google GenAI text-embedding-004 com fallback local determinístico para operação autônoma sem chave.
- Síntese de Voz (TTS): Edge-TTS com voz `pt-BR-AntonioNeural` (alta fidelidade e realismo) e pyttsx3 como contingência local.
- Reconhecimento de Fala (STT): SpeechRecognition integrado para captura por microfone.
- Daemon em Background: Monitoramento global de teclas com `pynput` no atalho `Ctrl + Alt + J`.

## Funções Disponíveis
1. `status do sistema` / `status do pc`: Consulta CPU, uso de RAM em GB e espaço livre no disco em tempo real via `psutil`.
2. Memorização contínua: Qualquer frase contendo "aprenda que", "lembre-se que" ou "grave que" é indexada automaticamente na base vetorial.
3. Leitura e indexação automática de arquivos markdown em `data/learnings/`.
