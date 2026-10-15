@echo off
rem Fon Analiz: 8000 (backend) ve 5173 (frontend) portlarini dinleyen islemleri ve pencerelerini kapatir.
setlocal
title Fon Analiz - Durduruluyor
%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$found = $false; foreach ($p in 8000, 5173) { Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { $found = $true; Write-Host ('Port ' + $p + ': islem ' + $_ + ' kapatiliyor'); taskkill /PID $_ /T /F | Out-Null } }; if (-not $found) { Write-Host 'Calisan Fon Analiz bulunamadi.' }"
taskkill /FI "WINDOWTITLE eq FonAnaliz Backend*" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq FonAnaliz Frontend*" /T /F >nul 2>&1
echo Fon Analiz durduruldu.
ping -n 4 127.0.0.1 >nul
