@echo off
setlocal enabledelayedexpansion
title Jarvis AI - Build Automático do Executável

echo =========================================================
echo       JARVIS AI - COMPILACAO AUTOMATICA DO EXECUTAVEL
echo =========================================================
echo.

cd /d "%~dp0"

:: 1. Verifica se o ambiente virtual existe
if not exist ".venv\Scripts\python.exe" (
    echo [!] Ambiente virtual nao encontrado. Criando .venv...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERRO] Falha ao criar ambiente virtual com Python.
        pause
        exit /b 1
    )
)

:: 2. Instala/atualiza dependencias necessarias para o build
echo [*] Verificando dependencias essenciais de build...
.\.venv\Scripts\python.exe -m pip install --upgrade pip >nul 2>&1
.\.venv\Scripts\python.exe -m pip install pyinstaller >nul 2>&1

:: 3. Limpa builds anteriores
echo [*] Limpando pastas de build anteriores (build/ e dist/)...
if exist "build" rd /s /q "build"
if exist "dist" rd /s /q "dist"

:: 4. Executa a compilacao pelo PyInstaller
echo [*] Compilando executavel nativo JarvisAI.exe via PyInstaller...
echo     (Isso pode levar de 1 a 2 minutos)...
.\.venv\Scripts\pyinstaller.exe jarvis.spec --noconfirm

if errorlevel 1 (
    echo.
    echo [ERRO] A compilacao falhou. Verifique os logs acima.
    pause
    exit /b 1
)

:: 5. Verifica se o executavel foi gerado com sucesso
if exist "dist\JarvisAI\JarvisAI.exe" (
    echo.
    echo =========================================================
    echo   [SUCESSO] EXECUTAVEL COMPILADO COM SUCESSO!
    echo =========================================================
    echo Localizacao: %~dp0dist\JarvisAI\JarvisAI.exe
    echo.
    echo Voce pode rodar diretamente o executavel da pasta dist\JarvisAI\
    echo.
) else (
    echo.
    echo [AVISO] O processo finalizou, mas o executavel nao foi encontrado.
)

echo Pressione qualquer tecla para fechar esta janela...
pause >nul
