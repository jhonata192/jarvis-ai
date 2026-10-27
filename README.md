# Jarvis AI - Assistente Virtual Pessoal Offline

Assistente virtual avançado em Python com arquitetura inspirada no JARVIS, operando **100% offline** com inteligência artificial local (Qwen 2.5 1.5B via llama-cpp), suporte a **Ferramentas MCP (Model Context Protocol)**, reconhecimento de voz **OpenAI Whisper**, síntese neural de voz e memória vetorial persistente (**RAG com ChromaDB**).

---

## 🌟 Recursos Principais

1. **Inteligência Artificial 100% Offline (Sem Dependência de Nuvem)**:
   - Motor baseado em **Qwen 2.5 1.5B Instruct GGUF** rodando diretamente em memória RAM via `llama-cpp-python`.
   - **Tool Calling Autônomo**: A LLM analisa o pedido em linguagem natural e decide autonomamente quando e como chamar as ferramentas MCP.
   - Respostas instantâneas em 1 a 2 segundos no CPU.

2. **Servidor MCP do Windows (`jarvis-system`)**:
   - Controle total de hardware e sistema via ferramentas padronizadas MCP:
     - `get_bluetooth_devices`: Lista periféricos conectados e reporta nível de bateria (GATT).
     - `set_bluetooth_radio_state`: Liga ou desliga a antena Bluetooth por comando de voz.
     - `set_system_volume`: Ajusta o volume do som de 0 a 100%.
     - `get_battery_status`: Porcentagem da bateria do PC e status de carregamento.
     - `get_hardware_telemetry`: Monitoramento em tempo real de CPU, RAM e armazenamento em disco.
     - `open_app_or_website`: Abre programas locais ou sites no navegador.

3. **Reconhecimento de Voz Whisper (`faster-whisper`)**:
   - Modelo **Whisper Small** quantizado (`int8`) com alta acurácia fonética para português do Brasil.
   - Sinais sonoros sutis de abertura (beep ascendente) e fechamento (beep descendente) do microfone.
   - Tolerância de pausa adaptativa para falar confortavelmente sem ser cortado.

4. **Síntese de Voz Ultra Realista (TTS)**:
   - Voz neural em português (`pt-BR-AntonioNeural`) via Edge-TTS com fala contínua, fluida e natural (e fallback local via `pyttsx3`).

5. **Memória de Longo Prazo e Aprendizado Contínuo (RAG)**:
   - Base vetorial persistente com **ChromaDB**.
   - Leitura automática de documentos de projetos em `data/learnings/`.
   - Memorização instantânea ao falar *"aprenda que..."*, *"lembre-se que..."* ou *"grave isso..."*.

6. **Modo Background Daemon 100% Invisível**:
   - Início sem janelas de terminal via [`iniciar.bat`](file:///c:/Users/fjhon/jarvis_ai/iniciar.bat) (`pythonw.exe`).
   - Acionamento por atalho global **`Ctrl + Alt + J`**.
   - **Compatibilidade total com NVDA / Leitores de Tela**: threads desacopladas sem travamento do teclado.

---

## 📁 Estrutura do Projeto

```
jarvis_ai/
├── data/
│   └── learnings/              # Documentos .md/.txt indexados pelo RAG
│       └── jarvis_capabilities.md
├── jarvis/
│   ├── assets/sounds/          # Efeitos sonoros do microfone (start/stop)
│   ├── core/
│   │   ├── agent.py            # Orquestrador Jarvis unificado
│   │   ├── local_llm_provider.py # Motor LLM offline com Tool Calling autônomo
│   │   ├── mcp_registry.py     # Registro e despacho de ferramentas MCP
│   │   └── agy_provider.py     # Adaptador opcional para o Antigravity CLI
│   ├── rag/
│   │   └── memory.py           # Gerenciador ChromaDB e Embeddings
│   ├── voice/
│   │   └── engine.py           # Whisper STT e Edge-TTS
│   ├── tools/
│   │   └── system_tools.py     # Métricas locais de sistema
│   ├── config.py               # Configurações centrais do sistema
│   └── background_runner.py    # Runner em background sem console
├── mcp_servers/
│   └── jarvis_system/
│       └── server.py           # Servidor MCP de ferramentas do Windows
├── models/                     # Modelos GGUF locais (Qwen 2.5)
├── logs/                       # Logs de execução
├── test_jarvis.py              # Suíte de testes de integração
├── iniciar.bat                 # Script para iniciar em background
├── parar.bat                   # Script para encerrar o Jarvis
├── requirements.txt            # Dependências Python
└── README.md
```

---

## 🚀 Como Executar

### 1. Clonar o Repositório e Criar Ambiente
```powershell
git clone https://github.com/jhonata192/jarvis-ai.git
cd jarvis-ai
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2. Instalar as Dependências
```powershell
pip install -r requirements.txt
pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu
```

### 3. Baixar o Modelo Qwen 2.5 (1.5B) GGUF
```powershell
python -c "from huggingface_hub import hf_hub_download; hf_hub_download(repo_id='Qwen/Qwen2.5-1.5B-Instruct-GGUF', filename='qwen2.5-1.5b-instruct-q4_k_m.gguf', local_dir='models')"
```

### 4. Iniciar o Jarvis
Dê dois cliques em **`iniciar.bat`** (ou execute via prompt):
```powershell
.\iniciar.bat
```

Pressione **`Ctrl + Alt + J`** em qualquer janela do Windows para conversar com o Jarvis!

Para encerrar os processos em segundo plano:
```powershell
.\parar.bat
```
