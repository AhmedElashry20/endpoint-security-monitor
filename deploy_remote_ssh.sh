#!/bin/bash
# ╔══════════════════════════════════════════════════════════╗
# ║     سكريبت النشر عن بُعد - macOS / Linux                 ║
# ║     يثبّت الوكيل على أجهزة الشبكة عبر SSH                 ║
# ╚══════════════════════════════════════════════════════════╝

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REMOTE_INSTALL_DIR="/opt/endpoint-monitor"
COMPUTERS_FILE="$SCRIPT_DIR/computers.txt"
LOG_FILE="$SCRIPT_DIR/deployment_log_$(date +%Y%m%d_%H%M%S).txt"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
GRAY='\033[0;37m'
NC='\033[0m'

log() {
    local msg="$1"
    local color="${2:-$NC}"
    echo -e "  ${color}${msg}${NC}"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $msg" >> "$LOG_FILE"
}

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║     سكريبت النشر عن بُعد (SSH) - macOS / Linux          ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# ============================================
#   طلب بيانات SSH
# ============================================
read -p "  اسم المستخدم SSH (مثلاً root أو admin): " SSH_USER
read -sp "  كلمة المرور (أو Enter لو تستخدم SSH Key): " SSH_PASS
echo ""
echo ""

# دالة تنفيذ أمر عن بُعد
remote_exec() {
    local host="$1"
    local cmd="$2"

    if [ -n "$SSH_PASS" ]; then
        sshpass -p "$SSH_PASS" ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 "${SSH_USER}@${host}" "$cmd" 2>/dev/null
    else
        ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 "${SSH_USER}@${host}" "$cmd" 2>/dev/null
    fi
}

# دالة نسخ ملفات عن بُعد
remote_copy() {
    local host="$1"
    local src="$2"
    local dst="$3"

    if [ -n "$SSH_PASS" ]; then
        sshpass -p "$SSH_PASS" scp -o StrictHostKeyChecking=no -o ConnectTimeout=10 "$src" "${SSH_USER}@${host}:${dst}" 2>/dev/null
    else
        scp -o StrictHostKeyChecking=no -o ConnectTimeout=10 "$src" "${SSH_USER}@${host}:${dst}" 2>/dev/null
    fi
}

# ============================================
#   تثبيت على جهاز واحد
# ============================================
install_on_host() {
    local host="$1"
    local host_name="$2"

    # التحقق من الاتصال
    if ! ping -c 1 -W 2 "$host" &>/dev/null; then
        log "❌ $host_name ($host): غير متصل" "$RED"
        return 1
    fi

    # التحقق من SSH
    if ! remote_exec "$host" "echo ok" &>/dev/null; then
        log "❌ $host_name ($host): فشل اتصال SSH" "$RED"
        return 1
    fi

    # اكتشاف النظام
    local os_type=$(remote_exec "$host" "uname -s" 2>/dev/null)

    # إنشاء المجلد
    remote_exec "$host" "sudo mkdir -p $REMOTE_INSTALL_DIR" 2>/dev/null

    # نسخ الملفات
    remote_copy "$host" "$SCRIPT_DIR/agent.py" "/tmp/agent.py"
    remote_copy "$host" "$SCRIPT_DIR/config.json" "/tmp/config.json"
    for f in activity_monitor.py stream_client.py access_control.py advanced_protection.py; do
        if [ -f "$SCRIPT_DIR/$f" ]; then
            remote_copy "$host" "$SCRIPT_DIR/$f" "/tmp/$f"
        fi
    done

    remote_exec "$host" "sudo cp /tmp/agent.py /tmp/config.json $REMOTE_INSTALL_DIR/ 2>/dev/null; for f in activity_monitor.py stream_client.py access_control.py advanced_protection.py; do [ -f /tmp/\$f ] && sudo cp /tmp/\$f $REMOTE_INSTALL_DIR/; done; sudo chmod +x $REMOTE_INSTALL_DIR/agent.py"

    # التحقق من Python
    local python_check=$(remote_exec "$host" "which python3 2>/dev/null || which python 2>/dev/null")
    if [ -z "$python_check" ]; then
        log "⚠️ $host_name: Python غير موجود، جاري التثبيت..." "$YELLOW"
        if [ "$os_type" = "Linux" ]; then
            remote_exec "$host" "sudo apt-get install -y python3 python3-pip 2>/dev/null || sudo yum install -y python3 python3-pip 2>/dev/null || sudo dnf install -y python3 python3-pip 2>/dev/null"
        elif [ "$os_type" = "Darwin" ]; then
            remote_exec "$host" "brew install python3 2>/dev/null"
        fi
    fi

    # تثبيت المكتبات
    remote_exec "$host" "pip3 install Pillow mss 'python-socketio[client]' websocket-client --quiet 2>/dev/null"

    # إنشاء الخدمة
    if [ "$os_type" = "Linux" ]; then
        # systemd service
        remote_exec "$host" "cat > /tmp/endpoint-monitor.service << 'SVCEOF'
[Unit]
Description=Endpoint Security Monitor Agent
After=network.target

[Service]
Type=simple
ExecStart=$(which python3 || echo /usr/bin/python3) ${REMOTE_INSTALL_DIR}/agent.py
WorkingDirectory=${REMOTE_INSTALL_DIR}
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
SVCEOF
sudo cp /tmp/endpoint-monitor.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable endpoint-monitor
sudo systemctl start endpoint-monitor"

    elif [ "$os_type" = "Darwin" ]; then
        # launchd plist
        remote_exec "$host" "cat > /tmp/com.security.endpointmonitor.plist << 'PLISTEOF'
<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<!DOCTYPE plist PUBLIC \"-//Apple//DTD PLIST 1.0//EN\" \"http://www.apple.com/DTDs/PropertyList-1.0.dtd\">
<plist version=\"1.0\">
<dict>
    <key>Label</key>
    <string>com.security.endpointmonitor</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>${REMOTE_INSTALL_DIR}/agent.py</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>WorkingDirectory</key>
    <string>${REMOTE_INSTALL_DIR}</string>
</dict>
</plist>
PLISTEOF
cp /tmp/com.security.endpointmonitor.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.security.endpointmonitor.plist"
    fi

    # التحقق
    local verify=$(remote_exec "$host" "test -f $REMOTE_INSTALL_DIR/agent.py && echo 'OK'")
    if [ "$verify" = "OK" ]; then
        log "✅ $host_name ($host): تم التثبيت بنجاح [$os_type]" "$GREEN"
        return 0
    else
        log "❌ $host_name ($host): فشل التثبيت" "$RED"
        return 1
    fi
}

# ============================================
#   إزالة من جهاز
# ============================================
uninstall_from_host() {
    local host="$1"

    remote_exec "$host" "
        sudo systemctl stop endpoint-monitor 2>/dev/null
        sudo systemctl disable endpoint-monitor 2>/dev/null
        sudo rm -f /etc/systemd/system/endpoint-monitor.service 2>/dev/null
        sudo systemctl daemon-reload 2>/dev/null
        launchctl unload ~/Library/LaunchAgents/com.security.endpointmonitor.plist 2>/dev/null
        rm -f ~/Library/LaunchAgents/com.security.endpointmonitor.plist 2>/dev/null
        sudo rm -rf $REMOTE_INSTALL_DIR
    "
    log "✅ تمت الإزالة من $host" "$GREEN"
}

# ============================================
#   فحص حالة جهاز
# ============================================
check_host_status() {
    local host="$1"
    local host_name="$2"

    if ! ping -c 1 -W 2 "$host" &>/dev/null; then
        echo -e "  ⚪ $host_name ($host): غير متصل"
        return
    fi

    local status=$(remote_exec "$host" "
        installed=\$(test -f $REMOTE_INSTALL_DIR/agent.py && echo 'yes' || echo 'no')
        running=\$(pgrep -f 'agent.py' >/dev/null 2>&1 && echo 'yes' || echo 'no')
        echo \"\$installed|\$running\"
    ")

    local installed=$(echo "$status" | cut -d'|' -f1)
    local running=$(echo "$status" | cut -d'|' -f2)

    if [ "$running" = "yes" ]; then
        echo -e "  ${GREEN}🟢 $host_name ($host): مثبت وشغال${NC}"
    elif [ "$installed" = "yes" ]; then
        echo -e "  ${YELLOW}🟡 $host_name ($host): مثبت لكن متوقف${NC}"
    else
        echo -e "  ${RED}🔴 $host_name ($host): غير مثبت${NC}"
    fi
}

# ============================================
#   قراءة قائمة الأجهزة
# ============================================
read_computers() {
    if [ ! -f "$COMPUTERS_FILE" ]; then
        echo ""
        log "ملف computers.txt غير موجود" "$YELLOW"
        log "أنشئ الملف وأضف أسماء/عناوين الأجهزة (سطر لكل جهاز)" "$GRAY"
        return 1
    fi

    local computers=()
    while IFS= read -r line; do
        line=$(echo "$line" | xargs)  # trim
        if [ -n "$line" ] && [[ ! "$line" =~ ^# ]]; then
            computers+=("$line")
        fi
    done < "$COMPUTERS_FILE"

    echo "${computers[@]}"
}

# ============================================
#   القائمة الرئيسية
# ============================================
while true; do
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "  ${YELLOW}القائمة الرئيسية${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "  [1] 📦 تثبيت على جميع الأجهزة (computers.txt)"
    echo "  [2] 📦 تثبيت على جهاز محدد"
    echo "  [3] 📊 فحص حالة الأجهزة"
    echo "  [4] 🗑️  إزالة من جهاز محدد"
    echo "  [5] 🗑️  إزالة من جميع الأجهزة"
    echo "  [0] ❌ خروج"
    echo ""
    read -p "  اختر رقم: " choice

    case $choice in
        1)
            computers=($(read_computers))
            if [ ${#computers[@]} -eq 0 ]; then continue; fi

            log "جاري التثبيت على ${#computers[@]} جهاز..." "$CYAN"
            success=0
            fail=0

            for host in "${computers[@]}"; do
                if install_on_host "$host" "$host"; then
                    ((success++))
                else
                    ((fail++))
                fi
            done

            echo ""
            log "ملخص: نجح $success | فشل $fail | المجموع ${#computers[@]}" "$CYAN"
            ;;

        2)
            read -p "  أدخل اسم الجهاز أو IP: " target
            if [ -n "$target" ]; then
                install_on_host "$target" "$target"
            fi
            ;;

        3)
            computers=($(read_computers))
            if [ ${#computers[@]} -eq 0 ]; then
                read -p "  أدخل اسم الجهاز أو IP: " target
                if [ -n "$target" ]; then
                    check_host_status "$target" "$target"
                fi
            else
                echo ""
                for host in "${computers[@]}"; do
                    check_host_status "$host" "$host"
                done
            fi
            ;;

        4)
            read -p "  أدخل اسم الجهاز أو IP: " target
            if [ -n "$target" ]; then
                read -p "  ⚠️ متأكد من الإزالة؟ (y/n): " confirm
                if [ "$confirm" = "y" ]; then
                    uninstall_from_host "$target"
                fi
            fi
            ;;

        5)
            computers=($(read_computers))
            if [ ${#computers[@]} -eq 0 ]; then continue; fi

            echo -e "  ${RED}⚠️ سيتم الإزالة من ${#computers[@]} جهاز${NC}"
            read -p "  متأكد؟ (y/n): " confirm
            if [ "$confirm" = "y" ]; then
                for host in "${computers[@]}"; do
                    uninstall_from_host "$host"
                done
            fi
            ;;

        0)
            echo ""
            echo "  👋 شكراً!"
            echo ""
            exit 0
            ;;
    esac
done
