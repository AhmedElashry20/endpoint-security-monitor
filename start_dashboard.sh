#!/bin/bash
echo ""
echo " 🛡️  جاري تشغيل لوحة المراقبة..."
echo ""

pip3 install flask flask-socketio gevent gevent-websocket --quiet 2>/dev/null

echo " [✓] افتح المتصفح: http://localhost:5000"
echo ""

python3 "$(dirname "$0")/dashboard_server.py"
