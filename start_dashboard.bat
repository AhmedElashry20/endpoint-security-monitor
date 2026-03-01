@echo off
chcp 65001 >nul 2>&1
title 🛡️ Admin Dashboard

echo.
echo  🛡️  جاري تشغيل لوحة المراقبة...
echo.

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  [!] Python مطلوب - حمله من python.org
    pause & exit /b 1
)

pip install flask flask-socketio gevent gevent-websocket --quiet 2>nul

echo  [✓] افتح المتصفح: http://localhost:5000
echo.

python "%~dp0dashboard_server.py"
pause
