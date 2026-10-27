@echo off
title Jarvis Launcher
cd /d "%~dp0"

:: Executa em segundo plano sem janela usando pythonw do ambiente virtual
start "" "%~dp0.venv\Scripts\pythonw.exe" -m jarvis.background_runner

exit
