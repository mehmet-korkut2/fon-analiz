@echo off
title Fon Analiz - Backend
cd /d "%~dp0backend"
call .venv\Scripts\activate.bat
echo Backend baslatiliyor... Durdurmak icin Ctrl+C
uvicorn app.main:app --reload
pause
