#!/bin/bash
# ╔══════════════════════════════════════════════════════════╗
# ║     🔐 إزالة Endpoint Security Monitor                  ║
# ║     يحتاج كلمة مرور المسؤول                             ║
# ╚══════════════════════════════════════════════════════════╝

echo ""
echo "  🔐 إزالة Endpoint Security Monitor"
echo "  ⚠️  يحتاج كلمة مرور الإزالة"
echo ""

OS=$(uname -s)

if [ "$OS" = "Darwin" ]; then
    INSTALL_DIR="/usr/local/endpoint-monitor"
elif [ "$OS" = "Linux" ]; then
    INSTALL_DIR="/opt/endpoint-monitor"
fi

if [ ! -f "$INSTALL_DIR/self_protection.py" ]; then
    echo "  [!] البرنامج غير مثبت"
    exit 1
fi

python3 "$INSTALL_DIR/self_protection.py" --uninstall

if [ $? -eq 0 ]; then
    echo ""
    echo "  [i] جاري حذف الملفات..."
    sudo rm -rf "$INSTALL_DIR"
    echo "  [✓] تمت الإزالة"
else
    echo ""
    echo "  [!] فشلت الإزالة"
fi
