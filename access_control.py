#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║     Access Control Module - نظام التحكم بالوصول              ║
║                                                              ║
║     • كل جهاز مسجل باسم الموظف                               ║
║     • أي تحكم خارجي يحتاج موافقة المسؤول                     ║
║     • الموظف يشتغل عادي بدون أي عوائق                        ║
║     • مراقبة حية على أي اتصال خارجي                          ║
╚══════════════════════════════════════════════════════════════╝
"""

import os
import sys
import json
import time
import socket
import platform
import subprocess
import threading
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("AccessControl")

# ============================================
#   قائمة برامج التحكم عن بُعد
# ============================================
REMOTE_ACCESS_APPS = {
    # Windows process name: {display_name, service_name, kill_method}
    "AnyDesk.exe":              {"name": "AnyDesk",              "service": "AnyDesk"},
    "anydesk.exe":              {"name": "AnyDesk",              "service": "AnyDesk"},
    "TeamViewer.exe":           {"name": "TeamViewer",           "service": "TeamViewer"},
    "TeamViewer_Service.exe":   {"name": "TeamViewer",           "service": "TeamViewer"},
    "teamviewer":               {"name": "TeamViewer",           "service": "teamviewerd"},
    "rustdesk":                 {"name": "RustDesk",             "service": "rustdesk"},
    "rustdesk.exe":             {"name": "RustDesk",             "service": "rustdesk"},
    "remoting_host":            {"name": "Chrome Remote Desktop","service": "chromoting"},
    "remoting_host.exe":        {"name": "Chrome Remote Desktop","service": "chromoting"},
    "SplashtopStreamer.exe":    {"name": "Splashtop",            "service": "SplashtopRemoteService"},
    "parsecd.exe":              {"name": "Parsec",               "service": "Parsec"},
    "LogMeIn.exe":              {"name": "LogMeIn",              "service": "LogMeIn"},
    "vncserver":                {"name": "VNC",                  "service": "vncserver"},
    "winvnc.exe":               {"name": "VNC",                  "service": "uvnc_service"},
    "Xvnc":                     {"name": "VNC",                  "service": "vncserver"},
    "x11vnc":                   {"name": "VNC",                  "service": "x11vnc"},
    "radmin.exe":               {"name": "Radmin",               "service": "RManService"},
    "rserver3.exe":             {"name": "Radmin",               "service": "RManService"},
    "Supremo.exe":              {"name": "Supremo",              "service": "SupremoService"},
    "AA_v3.exe":                {"name": "Ammyy Admin",          "service": "AmmyyAdmin"},
    "MeshAgent.exe":            {"name": "MeshCentral",          "service": "MeshAgent"},
    "meshagent":                {"name": "MeshCentral",          "service": "meshagent"},
    "dwagent":                  {"name": "DWService",            "service": "DWAgent"},
    "dwagent.exe":              {"name": "DWService",            "service": "DWAgent"},
    "nxd":                      {"name": "NoMachine",            "service": "nxservice"},
    "nxserver":                 {"name": "NoMachine",            "service": "nxservice"},
    "ScreenConnect.ClientService.exe": {"name": "ScreenConnect", "service": "ScreenConnect"},
    "rfusclient.exe":           {"name": "Remote Utilities",     "service": "rutserv"},
    "rutserv.exe":              {"name": "Remote Utilities",     "service": "rutserv"},
    "client32.exe":             {"name": "NetSupport",           "service": "NetSupport"},
}


# ============================================
#   Employee Registration
# ============================================
class EmployeeRegistry:
    """تسجيل بيانات الموظف على الجهاز"""

    REGISTRY_FILE = Path(__file__).parent / "employee.json"

    @classmethod
    def is_registered(cls):
        return cls.REGISTRY_FILE.exists()

    @classmethod
    def register(cls, employee_name, employee_id, department, admin_approved=False):
        """تسجيل الموظف"""
        data = {
            "employee_name": employee_name,
            "employee_id": employee_id,
            "department": department,
            "hostname": socket.gethostname(),
            "os": f"{platform.system()} {platform.release()}",
            "registered_at": datetime.now().isoformat(),
            "admin_approved": admin_approved,
            "mac_address": cls._get_mac(),
        }
        with open(cls.REGISTRY_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"Employee registered: {employee_name} ({employee_id})")
        return data

    @classmethod
    def get_info(cls):
        """الحصول على بيانات الموظف"""
        if not cls.REGISTRY_FILE.exists():
            return None
        with open(cls.REGISTRY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)

    @classmethod
    def _get_mac(cls):
        try:
            import uuid
            mac = uuid.getnode()
            return ':'.join(('%012x' % mac)[i:i+2] for i in range(0, 12, 2))
        except:
            return "unknown"


# ============================================
#   Process Blocker (Cross-Platform)
# ============================================
class ProcessBlocker:
    """حظر وإيقاف برامج التحكم عن بُعد"""

    def __init__(self):
        self.system = platform.system()

    def kill_process(self, process_name):
        """إيقاف عملية"""
        try:
            if self.system == "Windows":
                # إيقاف العملية
                subprocess.run(
                    ["taskkill", "/F", "/IM", process_name],
                    capture_output=True, timeout=5
                )
                # إيقاف الخدمة المرتبطة
                app_info = REMOTE_ACCESS_APPS.get(process_name, {})
                service = app_info.get("service", "")
                if service:
                    subprocess.run(
                        ["net", "stop", service],
                        capture_output=True, timeout=10
                    )
                    # تعطيل الخدمة من الإقلاع
                    subprocess.run(
                        ["sc", "config", service, "start=", "disabled"],
                        capture_output=True, timeout=5
                    )
                return True

            elif self.system == "Darwin":
                clean_name = process_name.replace(".exe", "")
                subprocess.run(["pkill", "-9", "-f", clean_name], capture_output=True, timeout=5)
                return True

            elif self.system == "Linux":
                clean_name = process_name.replace(".exe", "")
                subprocess.run(["pkill", "-9", "-f", clean_name], capture_output=True, timeout=5)
                # إيقاف الخدمة
                app_info = REMOTE_ACCESS_APPS.get(process_name, {})
                service = app_info.get("service", "")
                if service:
                    subprocess.run(["systemctl", "stop", service], capture_output=True, timeout=10)
                    subprocess.run(["systemctl", "disable", service], capture_output=True, timeout=5)
                return True

        except Exception as e:
            logger.error(f"Kill process error: {e}")
        return False

    def kill_all_remote_access(self):
        """إيقاف جميع برامج التحكم عن بُعد"""
        killed = []
        running = self.get_running_remote_apps()

        for proc_name, app_info in running.items():
            if self.kill_process(proc_name):
                killed.append(app_info["name"])
                logger.warning(f"🔴 BLOCKED: {app_info['name']} ({proc_name})")

        return killed

    def get_running_remote_apps(self):
        """الحصول على برامج التحكم الشغالة حالياً"""
        found = {}
        try:
            if self.system == "Windows":
                output = subprocess.check_output(
                    ["tasklist", "/FO", "CSV", "/NH"],
                    text=True, stderr=subprocess.DEVNULL, timeout=5
                )
                for line in output.strip().split('\n'):
                    parts = line.strip('"').split('","')
                    if parts and parts[0] in REMOTE_ACCESS_APPS:
                        found[parts[0]] = REMOTE_ACCESS_APPS[parts[0]]
            else:
                output = subprocess.check_output(
                    ["ps", "-eo", "comm"],
                    text=True, stderr=subprocess.DEVNULL, timeout=5
                )
                for line in output.strip().split('\n'):
                    name = line.strip()
                    if name in REMOTE_ACCESS_APPS:
                        found[name] = REMOTE_ACCESS_APPS[name]
        except:
            pass
        return found

    def block_with_firewall(self, app_name):
        """حظر البرنامج عبر الفايروول"""
        try:
            if self.system == "Windows":
                # البحث عن مسار البرنامج
                app_info = None
                for proc, info in REMOTE_ACCESS_APPS.items():
                    if info["name"] == app_name:
                        app_info = info
                        break

                if app_info:
                    # حظر الاتصالات الواردة والصادرة
                    for direction in ["in", "out"]:
                        rule_name = f"Block_{app_name}_{direction}"
                        subprocess.run([
                            "netsh", "advfirewall", "firewall", "add", "rule",
                            f"name={rule_name}",
                            f"dir={direction}",
                            "action=block",
                            f"service={app_info.get('service', '')}",
                            "enable=yes"
                        ], capture_output=True, timeout=5)

            elif self.system == "Linux":
                # iptables - حظر البورتات المعروفة
                port_map = {
                    "AnyDesk": 7070, "TeamViewer": 5938,
                    "VNC": 5900, "Radmin": 4899,
                    "RustDesk": 21116, "NoMachine": 4000,
                }
                port = port_map.get(app_name)
                if port:
                    subprocess.run(
                        ["iptables", "-A", "INPUT", "-p", "tcp", "--dport", str(port), "-j", "DROP"],
                        capture_output=True, timeout=5
                    )

            logger.info(f"🔒 Firewall blocked: {app_name}")
            return True
        except Exception as e:
            logger.error(f"Firewall block error: {e}")
            return False

    def unblock_with_firewall(self, app_name):
        """رفع الحظر عن البرنامج"""
        try:
            if self.system == "Windows":
                for direction in ["in", "out"]:
                    rule_name = f"Block_{app_name}_{direction}"
                    subprocess.run([
                        "netsh", "advfirewall", "firewall", "delete", "rule",
                        f"name={rule_name}"
                    ], capture_output=True, timeout=5)

            elif self.system == "Linux":
                port_map = {
                    "AnyDesk": 7070, "TeamViewer": 5938,
                    "VNC": 5900, "Radmin": 4899,
                    "RustDesk": 21116, "NoMachine": 4000,
                }
                port = port_map.get(app_name)
                if port:
                    subprocess.run(
                        ["iptables", "-D", "INPUT", "-p", "tcp", "--dport", str(port), "-j", "DROP"],
                        capture_output=True, timeout=5
                    )

            logger.info(f"🔓 Firewall unblocked: {app_name}")
            return True
        except:
            return False


# ============================================
#   Popup Notification (Employee sees this)
# ============================================
class NotificationPopup:
    """إشعار يظهر للموظف"""

    def __init__(self):
        self.system = platform.system()

    def show_blocked(self, app_name, employee_name):
        """إشعار إن البرنامج تم حظره"""
        title = "⛔ تم حظر البرنامج"
        message = (
            f"مرحباً {employee_name}،\n\n"
            f"تم اكتشاف وحظر برنامج: {app_name}\n\n"
            f"هذا البرنامج يحتاج موافقة مسبقة من الإدارة.\n"
            f"تم إرسال طلب الموافقة تلقائياً.\n"
            f"إذا كنت تحتاج هذا البرنامج، تواصل مع قسم التقنية."
        )
        self._show(title, message, "warning")

    def show_approved(self, app_name, employee_name, duration_minutes):
        """إشعار إن البرنامج تمت الموافقة عليه"""
        title = "✅ تمت الموافقة"
        message = (
            f"مرحباً {employee_name}،\n\n"
            f"تمت الموافقة على استخدام: {app_name}\n"
            f"المدة المسموحة: {duration_minutes} دقيقة\n\n"
            f"سيتم إغلاق البرنامج تلقائياً بعد انتهاء المدة."
        )
        self._show(title, message, "info")

    def show_denied(self, app_name, employee_name):
        """إشعار إن الطلب مرفوض"""
        title = "❌ تم رفض الطلب"
        message = (
            f"مرحباً {employee_name}،\n\n"
            f"تم رفض طلب استخدام: {app_name}\n\n"
            f"إذا كنت تحتاج هذا البرنامج، تواصل مع المسؤول مباشرة."
        )
        self._show(title, message, "error")

    def show_session_ending(self, app_name, minutes_left):
        """إشعار إن الجلسة قربت تنتهي"""
        title = "⏰ تنبيه"
        message = f"الوقت المتبقي لاستخدام {app_name}: {minutes_left} دقيقة"
        self._show(title, message, "warning")

    def _show(self, title, message, msg_type="info"):
        """عرض الإشعار حسب النظام"""
        try:
            if self.system == "Windows":
                self._show_windows(title, message, msg_type)
            elif self.system == "Darwin":
                self._show_mac(title, message)
            elif self.system == "Linux":
                self._show_linux(title, message)
        except Exception as e:
            logger.error(f"Notification error: {e}")

    def _show_windows(self, title, message, msg_type):
        icon_map = {"info": 64, "warning": 48, "error": 16}
        icon = icon_map.get(msg_type, 64)

        ps_cmd = f"""
Add-Type -AssemblyName System.Windows.Forms
[System.Windows.Forms.MessageBox]::Show(
    '{message.replace(chr(10), "`n").replace("'", "''")}',
    '{title.replace("'", "''")}',
    [System.Windows.Forms.MessageBoxButtons]::OK,
    [System.Windows.Forms.MessageBoxIcon]::{
        'Information' if msg_type == 'info' else 'Warning' if msg_type == 'warning' else 'Error'
    }
)
"""
        # تشغيل في thread عشان ما يوقف البرنامج
        threading.Thread(
            target=lambda: subprocess.run(
                ["powershell", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd],
                capture_output=True, timeout=30
            ),
            daemon=True
        ).start()

    def _show_mac(self, title, message):
        clean_msg = message.replace('"', '\\"').replace('\n', '\\n')
        subprocess.Popen([
            "osascript", "-e",
            f'display dialog "{clean_msg}" with title "{title}" buttons {{"حسناً"}} default button 1'
        ])

    def _show_linux(self, title, message):
        # محاولة zenity أو notify-send
        try:
            subprocess.Popen([
                "zenity", "--info",
                f"--title={title}",
                f"--text={message}",
                "--width=400"
            ])
        except FileNotFoundError:
            try:
                subprocess.Popen([
                    "notify-send", title, message
                ])
            except:
                pass


# ============================================
#   Access Request Manager
# ============================================
class AccessRequestManager:
    """إدارة طلبات الوصول"""

    REQUESTS_FILE = Path(__file__).parent / "access_requests.json"

    def __init__(self):
        self.pending_requests = self._load()
        self.approved_sessions = {}  # {app_name: {approved_at, expires_at}}

    def _load(self):
        if self.REQUESTS_FILE.exists():
            try:
                with open(self.REQUESTS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return []

    def _save(self):
        with open(self.REQUESTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.pending_requests, f, ensure_ascii=False, indent=2)

    def create_request(self, app_name, employee_info):
        """إنشاء طلب موافقة"""
        request = {
            "id": f"REQ-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "app_name": app_name,
            "employee_name": employee_info.get("employee_name", "Unknown"),
            "employee_id": employee_info.get("employee_id", ""),
            "department": employee_info.get("department", ""),
            "hostname": socket.gethostname(),
            "timestamp": datetime.now().isoformat(),
            "status": "pending",  # pending, approved, denied
            "approved_duration": 0,
        }
        self.pending_requests.append(request)
        self._save()
        return request

    def approve(self, request_id, duration_minutes=30):
        """الموافقة على طلب"""
        for req in self.pending_requests:
            if req["id"] == request_id:
                req["status"] = "approved"
                req["approved_duration"] = duration_minutes
                req["approved_at"] = datetime.now().isoformat()
                self._save()

                # إضافة للجلسات المعتمدة
                self.approved_sessions[req["app_name"]] = {
                    "approved_at": datetime.now(),
                    "expires_at": datetime.now().timestamp() + (duration_minutes * 60),
                    "duration": duration_minutes,
                    "request_id": request_id,
                }
                return req
        return None

    def deny(self, request_id):
        """رفض طلب"""
        for req in self.pending_requests:
            if req["id"] == request_id:
                req["status"] = "denied"
                req["denied_at"] = datetime.now().isoformat()
                self._save()
                return req
        return None

    def is_approved(self, app_name):
        """هل البرنامج مسموح حالياً؟"""
        session = self.approved_sessions.get(app_name)
        if session:
            if time.time() < session["expires_at"]:
                return True
            else:
                # الجلسة انتهت
                del self.approved_sessions[app_name]
        return False

    def get_remaining_time(self, app_name):
        """الوقت المتبقي للجلسة (بالدقائق)"""
        session = self.approved_sessions.get(app_name)
        if session:
            remaining = session["expires_at"] - time.time()
            return max(0, remaining / 60)
        return 0

    def get_pending_requests(self):
        """الطلبات المعلقة"""
        return [r for r in self.pending_requests if r["status"] == "pending"]

    def revoke(self, app_name):
        """سحب الموافقة فوراً"""
        if app_name in self.approved_sessions:
            del self.approved_sessions[app_name]
            return True
        return False


# ============================================
#   Access Control Engine
# ============================================
class AccessControlEngine:
    """المحرك الرئيسي للتحكم بالوصول"""

    def __init__(self, config):
        self.config = config
        self.blocker = ProcessBlocker()
        self.notifier = NotificationPopup()
        self.request_manager = AccessRequestManager()
        self.employee_info = EmployeeRegistry.get_info()

        self.sio = None  # Socket.IO client
        self.dashboard_connected = False
        self.monitoring = True

        # الأجهزة المعروفة (whitelist)
        self.whitelisted_apps = set(config.get("whitelisted_apps", []))

        # سجل الأحداث
        self.event_log = []

        if not self.employee_info:
            logger.error("⚠️ Employee not registered! Run: python access_control.py --register")

    def connect_dashboard(self, dashboard_url):
        """الاتصال بالداشبورد للموافقات"""
        try:
            import socketio as sio_module
            self.sio = sio_module.Client(reconnection=True, reconnection_delay=5)

            @self.sio.on("connect")
            def on_connect():
                self.dashboard_connected = True
                logger.info("✅ Connected to admin dashboard")
                # تسجيل الجهاز
                self.sio.emit("register_agent", {
                    "agent_id": f"{socket.gethostname()}_{self.employee_info.get('employee_id', '')}",
                    "hostname": socket.gethostname(),
                    "employee_name": self.employee_info.get("employee_name", ""),
                    "employee_id": self.employee_info.get("employee_id", ""),
                    "department": self.employee_info.get("department", ""),
                    "os": platform.system(),
                    "user": self.employee_info.get("employee_name", ""),
                })

            @self.sio.on("disconnect")
            def on_disconnect():
                self.dashboard_connected = False
                logger.warning("❌ Disconnected from dashboard")

            @self.sio.on("access_approved")
            def on_approved(data):
                """المسؤول وافق"""
                app_name = data.get("app_name", "")
                duration = data.get("duration_minutes", 30)
                request_id = data.get("request_id", "")

                logger.info(f"✅ APPROVED: {app_name} for {duration} minutes")
                self.request_manager.approve(request_id, duration)

                # إشعار الموظف
                self.notifier.show_approved(
                    app_name,
                    self.employee_info.get("employee_name", ""),
                    duration
                )

                # رفع حظر الفايروول
                self.blocker.unblock_with_firewall(app_name)

                # تنبيه قبل الانتهاء
                threading.Thread(
                    target=self._session_timer,
                    args=(app_name, duration),
                    daemon=True
                ).start()

            @self.sio.on("access_denied")
            def on_denied(data):
                """المسؤول رفض"""
                app_name = data.get("app_name", "")
                request_id = data.get("request_id", "")

                logger.info(f"❌ DENIED: {app_name}")
                self.request_manager.deny(request_id)

                # إشعار الموظف
                self.notifier.show_denied(
                    app_name,
                    self.employee_info.get("employee_name", "")
                )

                # حظر البرنامج بالفايروول كمان
                self.blocker.block_with_firewall(app_name)

            @self.sio.on("revoke_access")
            def on_revoke(data):
                """المسؤول سحب الموافقة"""
                app_name = data.get("app_name", "")
                self.request_manager.revoke(app_name)
                self.blocker.kill_process_by_app_name(app_name)
                self.blocker.block_with_firewall(app_name)
                logger.warning(f"🔴 ACCESS REVOKED: {app_name}")

            self.sio.connect(dashboard_url, transports=['websocket', 'polling'])
            return True

        except Exception as e:
            logger.error(f"Dashboard connection failed: {e}")
            return False

    def _session_timer(self, app_name, duration_minutes):
        """مؤقت الجلسة"""
        # تنبيه قبل 5 دقائق من الانتهاء
        warn_time = max(0, (duration_minutes - 5) * 60)
        if warn_time > 0:
            time.sleep(warn_time)
            if self.request_manager.is_approved(app_name):
                self.notifier.show_session_ending(app_name, 5)

        # انتظر حتى انتهاء الجلسة
        remaining = self.request_manager.get_remaining_time(app_name)
        if remaining > 0:
            time.sleep(remaining * 60)

        # انتهت الجلسة
        if not self.request_manager.is_approved(app_name):
            logger.info(f"⏰ Session expired: {app_name}")
            self._handle_expired_session(app_name)

    def _handle_expired_session(self, app_name):
        """التعامل مع انتهاء الجلسة"""
        # إيقاف البرنامج
        for proc_name, info in REMOTE_ACCESS_APPS.items():
            if info["name"] == app_name:
                self.blocker.kill_process(proc_name)

        # حظر بالفايروول
        self.blocker.block_with_firewall(app_name)

        # إشعار الموظف
        self.notifier.show_blocked(
            app_name,
            self.employee_info.get("employee_name", "")
        )

    def monitor_loop(self):
        """حلقة المراقبة الرئيسية"""
        logger.info("🔍 Access Control monitoring started...")
        logger.info(f"👤 Employee: {self.employee_info.get('employee_name', 'Unknown')}")
        logger.info(f"🖥️ Hostname: {socket.gethostname()}")

        while self.monitoring:
            try:
                # فحص البرامج الشغالة
                running_apps = self.blocker.get_running_remote_apps()

                for proc_name, app_info in running_apps.items():
                    app_name = app_info["name"]

                    # هل البرنامج في القائمة البيضاء؟
                    if app_name in self.whitelisted_apps:
                        continue

                    # هل فيه موافقة سارية؟
                    if self.request_manager.is_approved(app_name):
                        continue

                    # ❌ مافيه موافقة - حظر البرنامج فوراً
                    logger.warning(f"🚨 UNAUTHORIZED: {app_name} detected! Blocking...")

                    # 1. إيقاف البرنامج فوراً
                    self.blocker.kill_process(proc_name)

                    # 2. حظر بالفايروول
                    self.blocker.block_with_firewall(app_name)

                    # 3. إشعار الموظف
                    self.notifier.show_blocked(
                        app_name,
                        self.employee_info.get("employee_name", "")
                    )

                    # 4. إرسال طلب موافقة للمسؤول
                    request = self.request_manager.create_request(app_name, self.employee_info)

                    # 5. إبلاغ الداشبورد
                    if self.sio and self.dashboard_connected:
                        self.sio.emit("access_request", {
                            "request_id": request["id"],
                            "app_name": app_name,
                            "employee_name": self.employee_info.get("employee_name", ""),
                            "employee_id": self.employee_info.get("employee_id", ""),
                            "department": self.employee_info.get("department", ""),
                            "hostname": socket.gethostname(),
                            "timestamp": datetime.now().isoformat(),
                            "agent_id": f"{socket.gethostname()}_{self.employee_info.get('employee_id', '')}",
                        })

                    # 6. تسجيل الحدث
                    self.event_log.append({
                        "time": datetime.now().isoformat(),
                        "event": "blocked",
                        "app": app_name,
                        "process": proc_name,
                        "employee": self.employee_info.get("employee_name", ""),
                    })

                time.sleep(3)

            except Exception as e:
                logger.error(f"Monitor error: {e}")
                time.sleep(5)

    def stop(self):
        self.monitoring = False
        if self.sio:
            try:
                self.sio.disconnect()
            except:
                pass


# ============================================
#   Employee Registration CLI
# ============================================
def register_employee_cli():
    """واجهة تسجيل الموظف"""
    print("""
╔══════════════════════════════════════════════════════════════╗
║     تسجيل الموظف - Employee Registration                    ║
╚══════════════════════════════════════════════════════════════╝
    """)

    if EmployeeRegistry.is_registered():
        info = EmployeeRegistry.get_info()
        print(f"  ⚠️ هذا الجهاز مسجل بالفعل باسم: {info['employee_name']}")
        confirm = input("  هل تريد إعادة التسجيل؟ (y/n): ").strip()
        if confirm.lower() != 'y':
            return

    name = input("  اسم الموظف: ").strip()
    emp_id = input("  الرقم الوظيفي: ").strip()
    department = input("  القسم: ").strip()

    if not name:
        print("  ❌ اسم الموظف مطلوب!")
        return

    data = EmployeeRegistry.register(name, emp_id, department)
    print()
    print(f"  ✅ تم التسجيل بنجاح!")
    print(f"     الاسم: {data['employee_name']}")
    print(f"     الرقم الوظيفي: {data['employee_id']}")
    print(f"     القسم: {data['department']}")
    print(f"     الجهاز: {data['hostname']}")
    print()


# ============================================
#   Main
# ============================================
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Access Control Module")
    parser.add_argument("--register", action="store_true", help="Register employee on this device")
    parser.add_argument("--dashboard", "-d", help="Dashboard URL", default="http://192.168.1.100:5000")
    parser.add_argument("--status", action="store_true", help="Show current status")
    args = parser.parse_args()

    if args.register:
        register_employee_cli()
        sys.exit(0)

    if args.status:
        info = EmployeeRegistry.get_info()
        if info:
            print(f"  👤 الموظف: {info['employee_name']} ({info['employee_id']})")
            print(f"  🖥️ الجهاز: {info['hostname']}")
            print(f"  📅 التسجيل: {info['registered_at']}")
        else:
            print("  ⚠️ الجهاز غير مسجل")
        sys.exit(0)

    # التحقق من التسجيل
    if not EmployeeRegistry.is_registered():
        print("  ⚠️ يجب تسجيل الموظف أولاً!")
        register_employee_cli()

    # تحميل الإعدادات
    config = {}
    config_path = Path(__file__).parent / "config.json"
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

    # تشغيل المحرك
    engine = AccessControlEngine(config)

    # الاتصال بالداشبورد
    dashboard_url = config.get("live_stream", {}).get("dashboard_url", args.dashboard)
    threading.Thread(
        target=engine.connect_dashboard,
        args=(dashboard_url,),
        daemon=True
    ).start()

    try:
        engine.monitor_loop()
    except KeyboardInterrupt:
        engine.stop()
        print("\n  ⏹ Stopped")
