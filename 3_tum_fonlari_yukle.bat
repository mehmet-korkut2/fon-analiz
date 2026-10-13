@echo off
title Fon Analiz - TEFAS veri yukleme
cd /d "%~dp0backend"
call .venv\Scripts\activate.bat
echo Tum fonlar yukleniyor, 10-15 dakika surebilir...
python -m scripts.tefas_yukle --limit 0
pause
