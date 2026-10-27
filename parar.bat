@echo off
title Encerrar Jarvis
echo Encerrando processos do Jarvis em segundo plano...

powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name = 'pythonw.exe'\" | Where-Object { $_.CommandLine -like '*jarvis*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"

echo Jarvis finalizado com sucesso.
