@echo off
:: ============================================================
::  Endpoint Monitor - Connection Diagnostic Tool
::  شغّل هذا الملف على جهاز الموظف لتشخيص المشكلة
:: ============================================================
chcp 65001 >nul 2>&1
title Endpoint Monitor - Diagnostic

echo.
echo ============================================================
echo   Endpoint Monitor - Connection Diagnostic
echo ============================================================
echo.

:: Check 1: Is Python installed?
echo [1/6] Checking Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo       [FAIL] Python is NOT installed!
    echo       Solution: Run install_windows.bat as Admin
    goto :end
)
for /f "tokens=*" %%i in ('python --version 2^>^&1') do echo       [OK] %%i

:: Check 2: Are packages installed?
echo.
echo [2/6] Checking packages...
python -c "import socketio; print('       [OK] socketio:', socketio.__version__)" 2>nul
if %errorlevel% neq 0 (
    echo       [FAIL] socketio not installed!
    echo       Fixing: Installing now...
    python -m pip install "python-socketio[client]" websocket-client --quiet
)
python -c "import PIL; print('       [OK] Pillow installed')" 2>nul
if %errorlevel% neq 0 (
    echo       [FAIL] Pillow not installed!
    python -m pip install Pillow --quiet
)

:: Check 3: Do the agent files exist?
echo.
echo [3/6] Checking agent files...
if exist "C:\EndpointMonitor\agent.py" (
    echo       [OK] agent.py found in C:\EndpointMonitor
) else (
    echo       [FAIL] agent.py NOT found in C:\EndpointMonitor!
    echo       Solution: Run install_windows.bat as Admin
)
if exist "C:\EndpointMonitor\stream_client.py" (
    echo       [OK] stream_client.py found
) else (
    echo       [FAIL] stream_client.py NOT found!
)
if exist "C:\EndpointMonitor\config.json" (
    echo       [OK] config.json found
) else (
    echo       [FAIL] config.json NOT found!
)

:: Check 4: Check config dashboard_url
echo.
echo [4/6] Checking config...
python -c "import json; c=json.load(open(r'C:\EndpointMonitor\config.json')); print('       Dashboard URL:', c.get('live_stream',{}).get('dashboard_url','NOT SET'))" 2>nul
if %errorlevel% neq 0 (
    echo       [FAIL] Cannot read config.json
)

:: Check 5: Network connectivity
echo.
echo [5/6] Checking network to dashboard (192.168.100.210)...
ping -n 1 -w 2000 192.168.100.210 >nul 2>&1
if %errorlevel% equ 0 (
    echo       [OK] Can reach 192.168.100.210
) else (
    echo       [FAIL] Cannot reach 192.168.100.210!
    echo       This machine might be on a different network.
    echo       Check: ipconfig to see your IP address
)

:: Check port 5000
echo       Testing port 5000...
python -c "import socket; s=socket.socket(); s.settimeout(3); s.connect(('192.168.100.210',5000)); print('       [OK] Port 5000 is open'); s.close()" 2>nul
if %errorlevel% neq 0 (
    echo       [FAIL] Cannot connect to port 5000!
)

:: Check 6: Is the agent running?
echo.
echo [6/6] Checking if agent is running...
tasklist /FI "IMAGENAME eq python.exe" /FO CSV /NH 2>nul | findstr /i "python" >nul 2>&1
if %errorlevel% equ 0 (
    echo       [OK] Python process is running
) else (
    echo       [FAIL] Agent is NOT running!
    echo       Starting agent now...
    if exist "C:\EndpointMonitor\run_hidden.vbs" (
        wscript.exe "C:\EndpointMonitor\run_hidden.vbs"
        echo       Agent started!
    ) else (
        echo       run_hidden.vbs not found. Run install_windows.bat
    )
)

:: Check scheduled task
schtasks /query /tn "EndpointSecurityMonitor" >nul 2>&1
if %errorlevel% equ 0 (
    echo       [OK] Scheduled task exists (auto-start on login)
) else (
    echo       [FAIL] Scheduled task NOT found!
    echo       Solution: Run install_windows.bat as Admin
)

:end
echo.
echo ============================================================
echo   Diagnostic complete. Share these results with admin.
echo ============================================================
echo.
pause
