#!/usr/bin/env python3
"""
اختبار التثبيت - يتحقق من جاهزية كل شي
"""
import sys
import os
import json
import socket
import platform
from pathlib import Path

OK = "✅"
FAIL = "❌"
WARN = "⚠️"
errors = 0

print()
print("╔══════════════════════════════════════════════════════════╗")
print("║     🔍 اختبار التثبيت - Endpoint Security Monitor      ║")
print("╚══════════════════════════════════════════════════════════╝")
print()

# 1. Python version
v = sys.version_info
if v.major >= 3 and v.minor >= 8:
    print(f"  {OK} Python {v.major}.{v.minor}.{v.micro}")
else:
    print(f"  {FAIL} Python {v.major}.{v.minor} — يحتاج 3.8+")
    errors += 1

# 2. Core files
base = Path(__file__).parent
core_files = ["agent.py", "config.json", "access_control.py", "stream_client.py",
              "activity_monitor.py", "advanced_protection.py", "dashboard_server.py",
              "self_protection.py", "remote_access_remover.py", "intruder_tracker.py"]
for f in core_files:
    if (base / f).exists():
        print(f"  {OK} {f}")
    else:
        print(f"  {FAIL} {f} — غير موجود!")
        errors += 1

# 3. Config
print()
config_path = base / "config.json"
if config_path.exists():
    with open(config_path, 'r') as f:
        cfg = json.load(f)

    email = cfg.get("email", {})
    sender = email.get("sender_email", "")
    password = email.get("sender_password", "")
    dashboard = cfg.get("live_stream", {}).get("dashboard_url", "")

    if sender and "your" not in sender and "@" in sender:
        print(f"  {OK} الإيميل: {sender}")
    else:
        print(f"  {WARN} الإيميل غير معدّل في config.json")

    if password and "xxxx" not in password:
        print(f"  {OK} كلمة المرور: مضبوطة")
    else:
        print(f"  {WARN} كلمة المرور غير معدّلة في config.json")

    if dashboard and "192.168.1.100" not in dashboard:
        print(f"  {OK} الداشبورد: {dashboard}")
    else:
        print(f"  {WARN} عنوان الداشبورد غير معدّل: {dashboard}")

# 4. Employee registration
print()
emp_file = base / "employee.json"
if emp_file.exists():
    with open(emp_file, 'r') as f:
        emp = json.load(f)
    print(f"  {OK} الموظف: {emp.get('employee_name', '?')} ({emp.get('employee_id', '?')})")
else:
    print(f"  {WARN} الموظف غير مسجل — شغّل: python access_control.py --register")

# 5. Python libraries
print()
libs = {
    "flask": "Dashboard",
    "flask_socketio": "Dashboard WebSocket",
    "socketio": "Agent ↔ Dashboard",
    "PIL": "Screenshots",
    "mss": "Screenshots (fast)",
}
for lib, desc in libs.items():
    try:
        __import__(lib)
        print(f"  {OK} {desc} ({lib})")
    except ImportError:
        print(f"  {WARN} {desc} ({lib}) — pip install {lib.replace('PIL','Pillow').replace('socketio','python-socketio[client]')}")

# 6. Network
print()
hostname = socket.gethostname()
try:
    local_ip = socket.gethostbyname(hostname)
    print(f"  {OK} الجهاز: {hostname} ({local_ip})")
except:
    print(f"  {OK} الجهاز: {hostname}")

print(f"  {OK} النظام: {platform.system()} {platform.release()}")

# 7. Dashboard connectivity
if dashboard:
    try:
        host = dashboard.replace("http://", "").replace("https://", "").split(":")[0]
        port = int(dashboard.split(":")[-1].replace("/", ""))
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(3)
        result = s.connect_ex((host, port))
        s.close()
        if result == 0:
            print(f"  {OK} الداشبورد متصل: {dashboard}")
        else:
            print(f"  {WARN} الداشبورد غير متصل: {dashboard} — شغّله أولاً")
    except:
        print(f"  {WARN} تعذر فحص الداشبورد")

# Summary
print()
print("══════════════════════════════════════════════════════════")
if errors == 0:
    print(f"  {OK} كل شي جاهز!")
else:
    print(f"  {FAIL} فيه {errors} مشاكل لازم تنحل")
print("══════════════════════════════════════════════════════════")
print()
