#!/bin/bash
# ╔══════════════════════════════════════════════════════════╗
# ║     Endpoint Security Monitor - Linux Installer          ║
# ╚══════════════════════════════════════════════════════════╝

set -e

INSTALL_DIR="/opt/endpoint-monitor"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVICE_NAME="endpoint-monitor"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║     🛡️  Endpoint Security Monitor - Linux Installer      ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# Check root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}[!] يجب التشغيل كـ root${NC}"
    echo "    sudo $0"
    exit 1
fi

# Install Python if missing
if ! command -v python3 &>/dev/null; then
    echo -e "${YELLOW}[i] جاري تثبيت Python3...${NC}"
    if command -v apt-get &>/dev/null; then
        apt-get update -qq && apt-get install -y -qq python3 python3-pip
    elif command -v dnf &>/dev/null; then
        dnf install -y python3 python3-pip
    elif command -v yum &>/dev/null; then
        yum install -y python3 python3-pip
    elif command -v pacman &>/dev/null; then
        pacman -Sy --noconfirm python python-pip
    fi
fi
echo -e "${GREEN}[✓] Python3: $(python3 --version)${NC}"

# Install dependencies
echo -e "${YELLOW}[i] جاري تثبيت المكتبات...${NC}"
pip3 install Pillow mss "python-socketio[client]" websocket-client --quiet --break-system-packages 2>/dev/null || \
pip3 install Pillow mss "python-socketio[client]" websocket-client --quiet 2>/dev/null
echo -e "${GREEN}[✓] تم تثبيت المكتبات${NC}"

# Install optional tools
echo -e "${YELLOW}[i] جاري تثبيت أدوات اختيارية...${NC}"
if command -v apt-get &>/dev/null; then
    apt-get install -y -qq scrot xdotool xclip 2>/dev/null || true
elif command -v dnf &>/dev/null; then
    dnf install -y scrot xdotool xclip 2>/dev/null || true
fi

# Create install directory
mkdir -p "$INSTALL_DIR"

# Copy all files
echo -e "${YELLOW}[i] جاري نسخ الملفات...${NC}"
for file in agent.py config.json activity_monitor.py stream_client.py access_control.py advanced_protection.py self_protection.py remote_access_remover.py intruder_tracker.py; do
    if [ -f "$SCRIPT_DIR/$file" ]; then
        cp "$SCRIPT_DIR/$file" "$INSTALL_DIR/"
        echo "    ✓ $file"
    fi
done
chmod +x "$INSTALL_DIR/agent.py"
echo -e "${GREEN}[✓] تم نسخ الملفات${NC}"

# Register employee
echo ""
echo "══════════════════════════════════════════════════════════"
echo "  تسجيل بيانات الموظف"
echo "══════════════════════════════════════════════════════════"
echo ""
python3 "$INSTALL_DIR/access_control.py" --register

# Create systemd service
echo ""
echo -e "${YELLOW}[i] جاري إنشاء خدمة النظام...${NC}"

cat > "/etc/systemd/system/${SERVICE_NAME}.service" << SVCEOF
[Unit]
Description=Endpoint Security Monitor Agent
After=network.target graphical.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=$(which python3) ${INSTALL_DIR}/agent.py
WorkingDirectory=${INSTALL_DIR}
Restart=always
RestartSec=10
Environment=DISPLAY=:0
Environment=XAUTHORITY=/home/$(logname 2>/dev/null || echo root)/.Xauthority

[Install]
WantedBy=multi-user.target
SVCEOF

systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
echo -e "${GREEN}[✓] تم إنشاء الخدمة${NC}"

echo ""
echo "══════════════════════════════════════════════════════════"
echo -e "  ${GREEN}✅ تم التثبيت بنجاح!${NC}"
echo ""
echo "  المسار: $INSTALL_DIR"
echo "  الأوامر:"
echo "    تشغيل:    systemctl start $SERVICE_NAME"
echo "    إيقاف:    systemctl stop $SERVICE_NAME"
echo "    حالة:     systemctl status $SERVICE_NAME"
echo "    سجل:      journalctl -u $SERVICE_NAME -f"
echo ""
echo -e "  ${YELLOW}⚠️  عدّل config.json قبل التشغيل!${NC}"
echo "    nano $INSTALL_DIR/config.json"
echo "══════════════════════════════════════════════════════════"
echo ""

read -p "تشغيل المراقبة الآن؟ (y/n): " start_now
if [ "$start_now" = "y" ]; then
    systemctl start "$SERVICE_NAME"
    echo -e "${GREEN}[✓] الخدمة شغالة${NC}"
    systemctl status "$SERVICE_NAME" --no-pager
fi
