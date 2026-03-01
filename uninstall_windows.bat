@echo off
chcp 65001 >nul 2>&1
title إزالة Endpoint Security Monitor

echo.
echo  ╔══════════════════════════════════════════════════════════╗
echo  ║     🔐 إزالة Endpoint Security Monitor                  ║
echo  ║     يحتاج كلمة مرور المسؤول                             ║
echo  ╚══════════════════════════════════════════════════════════╝
echo.

net session >nul 2>&1
if %errorlevel% neq 0 (
    echo  [!] يجب تشغيل كـ Administrator
    pause & exit /b 1
)

set INSTALL_DIR=C:\EndpointMonitor

if not exist "%INSTALL_DIR%\self_protection.py" (
    echo  [!] البرنامج غير مثبت
    pause & exit /b 1
)

echo  ⚠️  هذا الإجراء يحتاج كلمة مرور الإزالة
echo  (الكلمة اللي تم تعيينها أثناء التثبيت)
echo.

python "%INSTALL_DIR%\self_protection.py" --uninstall

if %errorlevel% equ 0 (
    echo.
    echo  [i] جاري حذف الملفات...
    rmdir /s /q "%INSTALL_DIR%" 2>nul
    echo  [✓] تمت الإزالة
) else (
    echo.
    echo  [!] فشلت الإزالة - كلمة المرور خاطئة
)

echo.
pause
