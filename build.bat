@echo off
setlocal enabledelayedexpansion
title Jarvis AI - Build Automático com Controle de Versão

echo =========================================================
echo       JARVIS AI - COMPILACAO AUTOMATICA DO EXECUTAVEL
echo =========================================================
echo.

cd /d "%~dp0"

:: 1. Solicita a versão desejada para o Jarvis
echo Digite a versao do Jarvis para este build.
echo Exemplo: 1.0.0 ou 1.2.0
set /p JARVIS_VERSION="Versao desejada [padrao 1.0.0]: "

if "%JARVIS_VERSION%"=="" (
    set JARVIS_VERSION=1.0.0
)

echo.
echo [*] Configurando build para a versao: %JARVIS_VERSION%

:: 2. Prepara os dados de versão para o executável do Windows
set VER_COMMA=%JARVIS_VERSION:.=,%
powershell -NoProfile -Command "(Get-Content 'version_info.txt.template') -replace '{VER_STR}', '%JARVIS_VERSION%' -replace '{VER_COMMA}', '%VER_COMMA%' | Set-Content 'version_info.txt' -Encoding utf8"

:: 3. Verifica se o ambiente virtual existe
if not exist ".venv\Scripts\python.exe" (
    echo [!] Ambiente virtual nao encontrado. Criando .venv...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERRO] Falha ao criar ambiente virtual com Python.
        pause
        exit /b 1
    )
)

:: 4. Verifica ferramentas essenciais
echo [*] Verificando dependencias essenciais de build...
.\.venv\Scripts\python.exe -m pip install pyinstaller >nul 2>&1

:: 5. Limpa pastas antigas de compilação
echo [*] Limpando pastas de build anteriores...
if exist "build" rd /s /q "build"
if exist "dist" rd /s /q "dist"

:: 6. Executa a compilação pelo PyInstaller
echo [*] Compilando executavel nativo JarvisAI.exe (v%JARVIS_VERSION%)...
echo     (Aguarde de 1 a 2 minutos)...
.\.venv\Scripts\pyinstaller.exe jarvis.spec --noconfirm

if errorlevel 1 (
    echo.
    echo [ERRO] A compilacao falhou. Verifique os logs acima.
    if exist "version_info.txt" del "version_info.txt"
    pause
    exit /b 1
)

:: 7. Remove arquivo temporário de versão
if exist "version_info.txt" del "version_info.txt"

:: 8. Confirmação e resultado
if exist "dist\JarvisAI\JarvisAI.exe" (
    echo.
    echo =========================================================
    echo   [SUCESSO] JARVIS AI v%JARVIS_VERSION% COMPILADO!
    echo =========================================================
    echo Localizacao: %~dp0dist\JarvisAI\JarvisAI.exe
    echo.
    echo A versao %JARVIS_VERSION% foi embutida diretamente nos metadados do executavel.
    echo.
) else (
    echo.
    echo [AVISO] O processo finalizou, mas o executavel nao foi encontrado.
)

echo Pressione qualquer tecla para fechar esta janela...
pause >nul
