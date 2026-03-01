#!/bin/bash
# ╔══════════════════════════════════════════════════════════╗
# ║     Endpoint Security Monitor - macOS Installer          ║
# ╚══════════════════════════════════════════════════════════╝

set -e

INSTALL_DIR="/usr/local/endpoint-monitor"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST_NAME="com.security.endpointmonitor"
PLIST_PATH="$HOME/Library/LaunchAgents/$PLIST_NAME.plist"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║     🛡️  Endpoint Security Monitor - macOS Installer      ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# Check Python
if ! command -v python3 &>/dev/null; then
    echo -e "${RED}[!] Python3 مطلوب${NC}"
    echo "    brew install python3"
    echo "    أو حمّله من: https://python.org"
    exit 1
fi
echo -e "${GREEN}[✓] Python3 موجود: $(python3 --version)${NC}"

# Install dependencies
echo -e "${YELLOW}[i] جاري تثبيت المكتبات...${NC}"
pip3 install Pillow mss "python-socketio[client]" websocket-client --quiet 2>/dev/null
echo -e "${GREEN}[✓] تم تثبيت المكتبات${NC}"

# Create install directory
sudo mkdir -p "$INSTALL_DIR"

# Copy all files
echo -e "${YELLOW}[i] جاري نسخ الملفات...${NC}"
for file in agent.py config.json activity_monitor.py stream_client.py access_control.py advanced_protection.py self_protection.py remote_access_remover.py intruder_tracker.py; do
    if [ -f "$SCRIPT_DIR/$file" ]; then
        sudo cp "$SCRIPT_DIR/$file" "$INSTALL_DIR/"
        echo "    ✓ $file"
    fi
done
sudo chmod +x "$INSTALL_DIR/agent.py"
echo -e "${GREEN}[✓] تم نسخ الملفات${NC}"

# Register employee
echo ""
echo "══════════════════════════════════════════════════════════"
echo "  تسجيل بيانات الموظف"
echo "══════════════════════════════════════════════════════════"
echo ""
python3 "$INSTALL_DIR/access_control.py" --register

# Create LaunchAgent
echo ""
echo -e "${YELLOW}[i] جاري إنشاء خدمة التشغيل التلقائي...${NC}"

mkdir -p "$HOME/Library/LaunchAgents"
cat > "$PLIST_PATH" << PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$PLIST_NAME</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>$INSTALL_DIR/agent.py</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>WorkingDirectory</key>
    <string>$INSTALL_DIR</string>
    <key>StandardOutPath</key>
    <string>$INSTALL_DIR/stdout.log</string>
    <key>StandardErrorPath</key>
    <string>$INSTALL_DIR/stderr.log</string>
</dict>
</plist>
PLISTEOF

launchctl load "$PLIST_PATH" 2>/dev/null || true
echo -e "${GREEN}[✓] تم إنشاء الخدمة${NC}"

echo ""
echo "══════════════════════════════════════════════════════════"
echo -e "  ${GREEN}✅ تم التثبيت بنجاح!${NC}"
echo ""
echo "  المسار: $INSTALL_DIR"
echo "  الأوامر:"
echo "    تشغيل:    python3 $INSTALL_DIR/agent.py"
echo "    إيقاف:    launchctl unload $PLIST_PATH"
echo "    حالة:     launchctl list | grep endpoint"
echo "    سجل:      cat $INSTALL_DIR/monitor.log"
echo ""
echo -e "  ${YELLOW}⚠️  عدّل config.json قبل التشغيل!${NC}"
echo "══════════════════════════════════════════════════════════"
echo ""

read -p "تشغيل المراقبة الآن؟ (y/n): " start_now
if [ "$start_now" = "y" ]; then
    echo -e "${GREEN}[i] جاري التشغيل...${NC}"
    python3 "$INSTALL_DIR/agent.py" &
    echo -e "${GREEN}[✓] شغال (PID: $!)${NC}"
fi
