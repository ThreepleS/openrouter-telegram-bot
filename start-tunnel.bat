@echo off
REM Запуск бота + публичного HTTPS-туннеля (localhost.run).
powershell -ExecutionPolicy Bypass -File "%~dp0start-with-tunnel.ps1"
