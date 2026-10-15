@echo off
rem Fon Analiz: backend (FastAPI, 8000) ve frontend (Vite, 5173) baslatir, ikisi hazir olunca siteyi acar.
rem Internet gerekmez. Kapatmak icin FonAnaliz_Durdur.bat
setlocal
title Fon Analiz - Baslatiliyor
cd /d "%~dp0"
set "PS=powershell -NoProfile -ExecutionPolicy Bypass -Command"

if not exist "backend\.venv\Scripts\python.exe" (
  echo [HATA] backend\.venv bulunamadi. Kurulum: cd backend, python -m venv .venv, .venv\Scripts\pip install -r requirements.txt
  pause
  exit /b 1
)
if not exist "frontend\node_modules" (
  echo [HATA] frontend\node_modules bulunamadi. Internet varken bir kez: cd frontend, npm install
  pause
  exit /b 1
)
if not exist "backend\fon.db" (
  echo [UYARI] Veritabani yok. Yedekten donmek icin: cd backend, .venv\Scripts\python -m scripts.geri_yukle
  echo         ya da internet varken ilk yukleme: .venv\Scripts\python -m scripts.tefas_yukle --limit 0
)

%PS% "try { (New-Object Net.Sockets.TcpClient('127.0.0.1', 8000)).Close(); exit 0 } catch { exit 1 }"
if errorlevel 1 (
  echo Backend baslatiliyor...
  start "FonAnaliz Backend" /min /d "%~dp0backend" .venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
) else (
  echo Backend zaten calisiyor.
)

%PS% "try { (New-Object Net.Sockets.TcpClient('localhost', 5173)).Close(); exit 0 } catch { exit 1 }"
if errorlevel 1 (
  echo Frontend baslatiliyor...
  start "FonAnaliz Frontend" /min /d "%~dp0frontend" cmd /c npm run dev -- --port 5173 --strictPort
) else (
  echo Frontend zaten calisiyor.
)

echo Hazir olmalari bekleniyor (en fazla 2 dakika)...
%PS% "$end = (Get-Date).AddSeconds(120); while ((Get-Date) -lt $end) { try { $a = Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 'http://127.0.0.1:8000/api/health'; $b = Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 'http://localhost:5173/'; if ($a.StatusCode -eq 200 -and $b.StatusCode -eq 200) { exit 0 } } catch {}; Start-Sleep -Milliseconds 700 }; exit 1"
if errorlevel 1 (
  echo [HATA] 2 dakika icinde hazir olmadi. Gorev cubugundaki "FonAnaliz Backend" ve "FonAnaliz Frontend" pencerelerine bakin.
  pause
  exit /b 1
)

start "" "http://localhost:5173/"
echo Site acildi: http://localhost:5173/
echo Kapatmak icin FonAnaliz_Durdur.bat
ping -n 6 127.0.0.1 >nul
