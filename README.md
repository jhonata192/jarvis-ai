# Jarvis AI - Assistente Virtual Pessoal 100% Offline

Assistente virtual de elite em Python com arquitetura inspirada no JARVIS, operando **100% offline** com inteligência artificial local (**Qwen 2.5 1.5B via llama-cpp com template ChatML nativo**), orquestração de **Ferramentas MCP (Model Context Protocol)**, reconhecimento de voz **Faster-Whisper**, síntese neural ultrarrealista **Piper TTS** e memória vetorial persistente de longo prazo (**RAG 100% Offline via ChromaDB + ONNX all-MiniLM-L6-v2**).

---

## 🌟 Recursos Principais

1. **Inteligência Artificial 100% Offline com Tool Calling Autônomo**:
   - Motor baseado em **Qwen 2.5 1.5B Instruct GGUF** rodando em CPU/GPU local via `llama-cpp-python`.
   - **Formato ChatML Nativo**: Suporte direto ao protocolo de ferramentas MCP sem depender de palavras-chave engessadas no código. A LLM avalia a intenção do usuário em linguagem natural e decide quando chamar ferramentas de hardware e sistema.
   - Respostas geradas em 1 a 2 segundos com detecção dinâmica de threads de CPU (`optimal_threads`) e `n_batch=512`.

2. **Síntese Neural de Voz Offline de Alta Qualidade (Piper TTS)**:
   - Voz neural natural em português brasileiro (**`pt_BR-faber-medium`**) rodando 100% offline via ONNX runtime.
   - **Cache de Áudio em Memória**: Frases curtas e recorrentes (ex: *"Pois não, senhor?"*, *"Sistemas Jarvis operacionais."*) com resposta instantânea de 0ms de latência.
   - Fallback inteligente para Edge-TTS e SAPI nativo do Windows caso necessário.

3. **Reconhecimento de Voz Whisper (`faster-whisper`)**:
   - Modelo **Whisper Base** quantizado (`int8`) com alta acurácia fonética para português do Brasil (~3x mais rápido que modelos pesados).
   - Efeitos sonoros sutis de abertura e fechamento do microfone (`listen_start.wav` e `listen_stop.wav`).
   - Calibração de ruído ambiente inteligente executada uma única vez no boot, garantindo abertura imediata do microfone sem atrasos.
   - Tolerância de pausas naturais (`pause_threshold = 2.0s`) para falar com calma sem interrupções.

4. **Memória de Longo Prazo e RAG 100% Offline (ChromaDB + ONNX)**:
   - Base vetorial persistente local usando o modelo neural **`all-MiniLM-L6-v2` em formato ONNX** (sem chamadas a APIs na nuvem e sem exigir chaves externas).
   - Leitura e sincronização automática de documentos e diretrizes em `data/learnings/`.
   - Memorização automática ao falar *"aprenda que..."*, *"lembre-se que..."* ou *"grave isso..."*.
   - Bypass inteligente de RAG em comandos diretos de ação (ex: abrir programas, alterar volume) para poupar ~150ms por interação.

5. **Servidor MCP do Windows (`jarvis_system`)**:
   - Controle direto do sistema operacional via ferramentas padronizadas MCP:
     - `get_bluetooth_devices`: Lista periféricos conectados e reporta nível de bateria (GATT) com cache inteligente de 15s.
     - `set_bluetooth_radio_state`: Liga ou desliga a antena Bluetooth por comando de voz.
     - `set_system_volume`: Ajusta o volume do áudio de 0 a 100%.
     - `get_battery_status`: Porcentagem da bateria e status de carregamento na tomada.
     - `get_hardware_telemetry`: Monitoramento de CPU, memória RAM e espaço em disco.
     - `open_app_or_website`: Abre programas locais ou sites no navegador.
     - `check_for_updates`: Consulta releases do GitHub e verifica se há novas versões disponíveis.

6. **Auto-Update e Instalador Oficial Inno Setup**:
   - O Jarvis avisa por voz quando há nova versão disponível no GitHub e pode ser atualizado por comando de voz (*"atualizar versão"*).
   - Download da atualização com feedback sonoro contínuo da porcentagem.
   - Instalador Inno Setup (`JarvisAI-Setup.exe`) silencioso, que encerra o processo antigo, atualiza os arquivos e reinicia o Jarvis automaticamente em segundo plano.

7. **Modo Background Daemon 100% Invisível**:
   - Execução silenciosa sem consoles abertos via atalho global configurável (**`Ctrl + Alt + J`**).
   - Gerenciamento dinâmico de downloads na primeira execução: se os modelos locais (LLM, Whisper, Piper ou Embedding) estiverem ausentes, o Jarvis avisa por voz e faz o download automático informando o progresso.

---

## 📁 Estrutura do Projeto

```
jarvis_ai/
├── .github/workflows/
│   └── release.yml             # Pipeline de CI/CD para compilação e release no GitHub
├── data/
│   └── learnings/              # Documentos .md/.txt indexados pelo RAG
│       └── jarvis_capabilities.md
├── jarvis/
│   ├── assets/sounds/          # Sons de ativação/desativação do microfone
│   ├── core/
│   │   ├── agent.py            # Orquestrador JarvisAssistant
│   │   ├── downloader.py       # Download atômico com relatório de porcentagem
│   │   ├── local_llm_provider.py # Motor LLM offline com ChatML e Tool Calling
│   │   ├── mcp_registry.py     # Registro e despacho dinâmico de ferramentas MCP
│   │   ├── updater.py          # Verificador e aplicador de atualizações via GitHub Releases
│   │   └── agy_provider.py     # Provedor alternativo via Antigravity CLI
│   ├── rag/
│   │   └── memory.py           # Memória vetorial 100% offline (ONNX all-MiniLM-L6-v2)
│   ├── tools/
│   │   └── system_tools.py     # Métricas locais de sistema com cache
│   ├── voice/
│   │   └── engine.py           # Whisper STT, Piper TTS neural e cache de áudio
│   ├── config.py               # Configurações globais e diretórios do usuário (%LOCALAPPDATA%)
│   └── background_runner.py    # Daemon em segundo plano com atalho global
├── mcp_servers/
│   └── jarvis_system/
│       └── server.py           # Servidor MCP com ferramentas nativas do Windows
├── installer.iss               # Script Inno Setup do instalador oficial
├── jarvis.spec                 # Especificação PyInstaller para gerar o executável
├── build.bat                   # Script para compilação local
├── iniciar.bat                 # Script para inicialização em segundo plano
├── parar.bat                   # Script para encerramento de processos do Jarvis
├── requirements.txt            # Dependências Python
├── version.py                  # Versão oficial do projeto
└── README.md
```

---

## 🛠️ Como Compilar o Instalador / Executável

Para gerar a compilação local do executável com um clique:
1. Execute **`build.bat`**.
2. O script validará o ambiente virtual, instalará os requisitos e acionará o PyInstaller usando as diretrizes de [jarvis.spec](file:///c:/Users/fjhon/jarvis_ai/jarvis.spec).
3. O executável standalone será gerado em **`dist\JarvisAI\JarvisAI.exe`**.

> **Nota:** As releases oficiais (`.exe` de setup e `.zip` portátil) são geradas automaticamente pelo GitHub Actions a cada alteração de versão no arquivo [version.py](file:///c:/Users/fjhon/jarvis_ai/version.py).

---

## 🚀 Como Executar em Desenvolvimento

### 1. Clonar o Repositório e Criar Ambiente Virtual
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

### 3. Primeira Execução e Download dos Modelos
Você não precisa baixar os modelos manualmente. Na primeira execução, o Jarvis detecta os modelos ausentes, avisa por áudio e baixa automaticamente:
- O modelo LLM **Qwen 2.5 1.5B Instruct GGUF**;
- A voz neural **Piper TTS** em português;
- Os pesos do **Faster-Whisper**;
- O modelo de **Embedding ONNX** do ChromaDB.

### 4. Iniciar o Jarvis
Dê dois cliques em **`iniciar.bat`** ou execute via PowerShell:
```powershell
.\iniciar.bat
```

- Pressione **`Ctrl + Alt + J`** em qualquer janela do Windows para falar com o Jarvis.
- Para encerrar o assistente em segundo plano, execute:
```powershell
.\parar.bat
```
