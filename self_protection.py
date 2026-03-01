#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║     Self Protection Module - حماية ذاتية للوكيل              ║
║                                                              ║
║     الحماية فقط على ملفات البرنامج (مجلد التثبيت)            ║
║     الموظف حر يتصرف بكل ملفاته بدون أي تدخل أو عوائق       ║
║                                                              ║
║     • منع مسح ملفات البرنامج بدون إذن المسؤول                ║
║     • إعادة التشغيل التلقائي لو انقتل البرنامج              ║
║     • حماية الخدمة من التعطيل                                ║
║     • قفل الإزالة بكلمة مرور                                ║
║     ⚠️ لا تتدخل أبداً في ملفات الموظف الشخصية               ║
╚══════════════════════════════════════════════════════════════╝
"""

import os
import sys
import time
import json
import hashlib
import shutil
import signal
import ctypes
import platform
import subprocess
import threading
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("SelfProtection")
SYSTEM = platform.system()


# ============================================
#   Uninstall Password Manager
# ============================================
class UninstallLock:
    """قفل الإزالة — يحتاج كلمة مرور من المسؤول"""

    LOCK_FILE = Path(__file__).parent / ".protection_lock"
    DEFAULT_HASH = hashlib.sha256("Adm!n@2025#Secure".encode()).hexdigest()

    @classmethod
    def initialize(cls, password=None):
        """إنشاء قفل الحماية"""
        if password:
            pwd_hash = hashlib.sha256(password.encode()).hexdigest()
        else:
            pwd_hash = cls.DEFAULT_HASH

        data = {
            "hash": pwd_hash,
            "created": datetime.now().isoformat(),
            "locked": True,
        }

        with open(cls.LOCK_FILE, 'w') as f:
            json.dump(data, f)

        # إخفاء الملف على ويندوز
        if SYSTEM == "Windows":
            try:
                subprocess.run(["attrib", "+h", "+s", str(cls.LOCK_FILE)],
                             capture_output=True, timeout=3)
            except:
                pass

        logger.info("🔐 Uninstall lock initialized")

    @classmethod
    def verify(cls, password):
        """التحقق من كلمة المرور"""
        if not cls.LOCK_FILE.exists():
            return False

        with open(cls.LOCK_FILE, 'r') as f:
            data = json.load(f)

        pwd_hash = hashlib.sha256(password.encode()).hexdigest()
        return pwd_hash == data.get("hash", "")

    @classmethod
    def is_locked(cls):
        """هل القفل مفعل؟"""
        if not cls.LOCK_FILE.exists():
            cls.initialize()
            return True

        try:
            with open(cls.LOCK_FILE, 'r') as f:
                data = json.load(f)
            return data.get("locked", True)
        except:
            return True

    @classmethod
    def change_password(cls, old_password, new_password):
        """تغيير كلمة المرور"""
        if not cls.verify(old_password):
            return False

        cls.initialize(new_password)
        return True

    @classmethod
    def temporary_unlock(cls, password, duration_seconds=120):
        """فتح مؤقت للإزالة"""
        if not cls.verify(password):
            return False

        data = {
            "hash": hashlib.sha256(password.encode()).hexdigest(),
            "created": datetime.now().isoformat(),
            "locked": False,
            "unlock_expires": time.time() + duration_seconds,
        }

        with open(cls.LOCK_FILE, 'w') as f:
            json.dump(data, f)

        logger.warning(f"🔓 Temporary unlock for {duration_seconds}s")

        # إعادة القفل بعد المدة
        def relock():
            time.sleep(duration_seconds)
            cls.initialize(password)
            logger.info("🔐 Re-locked after timeout")

        threading.Thread(target=relock, daemon=True).start()
        return True


# ============================================
#   Process Guardian (حارس العمليات)
# ============================================
class ProcessGuardian:
    """
    يراقب عملية الوكيل ويعيد تشغيلها لو انقتلت
    يشتغل كعملية منفصلة
    """

    WATCHDOG_SCRIPT = Path(__file__).parent / ".watchdog.py"
    PID_FILE = Path(__file__).parent / ".agent.pid"

    @classmethod
    def save_pid(cls):
        """حفظ PID العملية الحالية"""
        with open(cls.PID_FILE, 'w') as f:
            f.write(str(os.getpid()))

        if SYSTEM == "Windows":
            try:
                subprocess.run(["attrib", "+h", str(cls.PID_FILE)],
                             capture_output=True, timeout=3)
            except:
                pass

    @classmethod
    def create_watchdog(cls):
        """إنشاء سكريبت الحارس"""
        install_dir = str(Path(__file__).parent).replace("\\", "\\\\")
        python_path = sys.executable.replace("\\", "\\\\")

        watchdog_code = f'''#!/usr/bin/env python3
"""Watchdog - يراقب الوكيل ويعيد تشغيله"""
import os, sys, time, subprocess, signal

AGENT_PY = r"{install_dir}/agent.py"
PID_FILE = r"{install_dir}/.agent.pid"
PYTHON = r"{python_path}"
CHECK_INTERVAL = 15

def is_running(pid):
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False

def get_saved_pid():
    try:
        with open(PID_FILE, 'r') as f:
            return int(f.read().strip())
    except:
        return None

def start_agent():
    proc = subprocess.Popen(
        [PYTHON, AGENT_PY],
        cwd=r"{install_dir}",
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    with open(PID_FILE, 'w') as f:
        f.write(str(proc.pid))
    return proc.pid

signal.signal(signal.SIGTERM, lambda *a: None)
signal.signal(signal.SIGINT, lambda *a: None)

while True:
    pid = get_saved_pid()
    if pid is None or not is_running(pid):
        new_pid = start_agent()
        print(f"[WATCHDOG] Agent restarted (PID: {{new_pid}})")
    time.sleep(CHECK_INTERVAL)
'''

        with open(cls.WATCHDOG_SCRIPT, 'w') as f:
            f.write(watchdog_code)

        if SYSTEM == "Windows":
            try:
                subprocess.run(["attrib", "+h", str(cls.WATCHDOG_SCRIPT)],
                             capture_output=True, timeout=3)
            except:
                pass

        logger.info("🐕 Watchdog script created")

    @classmethod
    def start_watchdog(cls):
        """تشغيل الحارس"""
        cls.create_watchdog()

        if SYSTEM == "Windows":
            # تشغيل مخفي
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0  # SW_HIDE

            subprocess.Popen(
                [sys.executable, str(cls.WATCHDOG_SCRIPT)],
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            subprocess.Popen(
                [sys.executable, str(cls.WATCHDOG_SCRIPT)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )

        logger.info("🐕 Watchdog started")


# ============================================
#   File Protection (حماية الملفات)
# ============================================
class FileProtector:
    """
    حماية ملفات البرنامج فقط من الحذف والتعديل
    ⚠️ مهم: لا تتدخل أبداً في ملفات الموظف الشخصية
    الموظف حر يمسح وينقل ويعدل أي ملف على جهازه
    الحماية فقط على ملفات المراقبة داخل مجلد التثبيت
    """

    def __init__(self):
        self.install_dir = Path(__file__).parent

        # ═══ فقط ملفات البرنامج — لا شي ثاني ═══
        self.protected_files = [
            "agent.py",
            "access_control.py",
            "stream_client.py",
            "activity_monitor.py",
            "advanced_protection.py",
            "self_protection.py",
            "remote_access_remover.py",
            "intruder_tracker.py",
            "config.json",
            "dashboard_server.py",
        ]

        self.file_hashes = {}
        self._calculate_hashes()

    def _calculate_hashes(self):
        """حساب هاش الملفات"""
        for fname in self.protected_files:
            fpath = self.install_dir / fname
            if fpath.exists():
                with open(fpath, 'rb') as f:
                    self.file_hashes[fname] = hashlib.md5(f.read()).hexdigest()

    def protect_files(self):
        """تفعيل حماية الملفات"""
        if SYSTEM == "Windows":
            self._protect_windows()
        elif SYSTEM == "Linux":
            self._protect_linux()
        elif SYSTEM == "Darwin":
            self._protect_mac()

    def _protect_windows(self):
        """
        حماية على ويندوز — فقط ملفات البرنامج
        ⚠️ لا نلمس أي ملف خارج مجلد التثبيت
        """
        for fname in self.protected_files:
            fpath = self.install_dir / fname
            if fpath.exists():
                try:
                    subprocess.run(
                        ["attrib", "+r", "+s", "+h", str(fpath)],
                        capture_output=True, timeout=3
                    )
                except:
                    pass

        # حماية مجلد التثبيت فقط (C:\EndpointMonitor)
        # ⚠️ هذا يمنع حذف المجلد نفسه فقط — ما يأثر على باقي الجهاز
        try:
            subprocess.run([
                "icacls", str(self.install_dir),
                "/deny", "Everyone:(DE,DC)",
            ], capture_output=True, timeout=5)
        except:
            pass

    def _protect_linux(self):
        """
        حماية على لينكس — فقط ملفات البرنامج
        ⚠️ لا نلمس أي ملف خارج مجلد التثبيت
        """
        for fname in self.protected_files:
            fpath = self.install_dir / fname
            if fpath.exists():
                try:
                    subprocess.run(
                        ["chattr", "+i", str(fpath)],
                        capture_output=True, timeout=3
                    )
                except:
                    pass

    def _protect_mac(self):
        """
        حماية على ماك — فقط ملفات البرنامج
        ⚠️ لا نلمس أي ملف خارج مجلد التثبيت
        """
        for fname in self.protected_files:
            fpath = self.install_dir / fname
            if fpath.exists():
                try:
                    subprocess.run(
                        ["chflags", "uchg", str(fpath)],
                        capture_output=True, timeout=3
                    )
                except:
                    pass

    def unprotect_files(self):
        """رفع الحماية (للتحديث أو الإزالة)"""
        if SYSTEM == "Windows":
            for fname in self.protected_files:
                fpath = self.install_dir / fname
                if fpath.exists():
                    subprocess.run(
                        ["attrib", "-r", "-s", "-h", str(fpath)],
                        capture_output=True, timeout=3
                    )
            subprocess.run([
                "icacls", str(self.install_dir),
                "/remove:d", "Everyone",
            ], capture_output=True, timeout=5)

        elif SYSTEM == "Linux":
            for fname in self.protected_files:
                fpath = self.install_dir / fname
                if fpath.exists():
                    subprocess.run(
                        ["chattr", "-i", str(fpath)],
                        capture_output=True, timeout=3
                    )

        elif SYSTEM == "Darwin":
            for fname in self.protected_files:
                fpath = self.install_dir / fname
                if fpath.exists():
                    subprocess.run(
                        ["chflags", "nouchg", str(fpath)],
                        capture_output=True, timeout=3
                    )

    def check_integrity(self):
        """فحص سلامة الملفات"""
        issues = []
        for fname, original_hash in self.file_hashes.items():
            fpath = self.install_dir / fname
            if not fpath.exists():
                issues.append({"file": fname, "issue": "deleted"})
            else:
                with open(fpath, 'rb') as f:
                    current_hash = hashlib.md5(f.read()).hexdigest()
                if current_hash != original_hash:
                    issues.append({"file": fname, "issue": "modified"})
        return issues

    def restore_from_backup(self):
        """استعادة الملفات من النسخة الاحتياطية"""
        backup_dir = self.install_dir / ".backup"
        if not backup_dir.exists():
            return False

        for fname in self.protected_files:
            backup_file = backup_dir / fname
            target_file = self.install_dir / fname
            if backup_file.exists() and not target_file.exists():
                shutil.copy2(str(backup_file), str(target_file))
                logger.info(f"📂 Restored: {fname}")

        return True

    def create_backup(self):
        """إنشاء نسخة احتياطية"""
        backup_dir = self.install_dir / ".backup"
        backup_dir.mkdir(exist_ok=True)

        for fname in self.protected_files:
            fpath = self.install_dir / fname
            if fpath.exists():
                shutil.copy2(str(fpath), str(backup_dir / fname))

        # إخفاء مجلد النسخة
        if SYSTEM == "Windows":
            subprocess.run(
                ["attrib", "+h", "+s", str(backup_dir)],
                capture_output=True, timeout=3
            )

        logger.info("📦 Backup created")


# ============================================
#   Service Protector (حماية الخدمة)
# ============================================
class ServiceProtector:
    """حماية خدمة النظام من التعطيل"""

    @staticmethod
    def protect_windows_service():
        """حماية خدمة ويندوز"""
        service_name = "EndpointSecurityMonitor"

        try:
            # منع إيقاف الخدمة
            subprocess.run([
                "sc", "failure", service_name,
                "reset=", "0",
                "actions=", "restart/5000/restart/10000/restart/30000"
            ], capture_output=True, timeout=5)

            # حماية Task Scheduler
            subprocess.run([
                "schtasks", "/change",
                "/tn", service_name,
                "/disable",  # No, we enable it
            ], capture_output=True, timeout=5)

            # إعادة التمكين
            subprocess.run([
                "schtasks", "/change",
                "/tn", service_name,
                "/enable",
            ], capture_output=True, timeout=5)

        except Exception as e:
            logger.error(f"Service protection error: {e}")

    @staticmethod
    def protect_linux_service():
        """حماية خدمة لينكس"""
        service_name = "endpoint-monitor"

        try:
            # تفعيل إعادة التشغيل التلقائي
            service_override = f"""[Service]
Restart=always
RestartSec=5
StartLimitIntervalSec=0
StartLimitBurst=0
"""
            override_dir = f"/etc/systemd/system/{service_name}.service.d"
            os.makedirs(override_dir, exist_ok=True)

            with open(f"{override_dir}/restart.conf", 'w') as f:
                f.write(service_override)

            subprocess.run(["systemctl", "daemon-reload"], capture_output=True, timeout=5)

            # حماية ملف الخدمة
            service_file = f"/etc/systemd/system/{service_name}.service"
            if os.path.exists(service_file):
                subprocess.run(
                    ["chattr", "+i", service_file],
                    capture_output=True, timeout=3
                )

        except Exception as e:
            logger.error(f"Service protection error: {e}")

    @staticmethod
    def protect_mac_service():
        """حماية خدمة ماك"""
        plist_path = os.path.expanduser(
            "~/Library/LaunchAgents/com.security.endpointmonitor.plist"
        )
        if os.path.exists(plist_path):
            try:
                subprocess.run(
                    ["chflags", "uchg", plist_path],
                    capture_output=True, timeout=3
                )
            except:
                pass


# ============================================
#   Anti-Kill (منع الإيقاف)
# ============================================
class AntiKill:
    """منع إيقاف العملية"""

    @staticmethod
    def setup():
        """إعداد حماية من الإيقاف"""
        # تجاهل إشارات الإيقاف
        try:
            signal.signal(signal.SIGTERM, AntiKill._handle_signal)
            signal.signal(signal.SIGINT, AntiKill._handle_signal)
            if hasattr(signal, 'SIGHUP'):
                signal.signal(signal.SIGHUP, AntiKill._handle_signal)
        except:
            pass

        # على ويندوز: إخفاء من Task Manager
        if SYSTEM == "Windows":
            AntiKill._hide_windows_process()

    @staticmethod
    def _handle_signal(signum, frame):
        """التعامل مع إشارات الإيقاف"""
        logger.warning(f"⚠️ Kill signal {signum} blocked! Use admin dashboard to stop.")

    @staticmethod
    def _hide_windows_process():
        """إخفاء العملية على ويندوز"""
        try:
            # تغيير عنوان النافذة
            if hasattr(ctypes, 'windll'):
                ctypes.windll.kernel32.SetConsoleTitleW("System Service Host")
        except:
            pass


# ============================================
#   Task Manager Blocker
# ============================================
class TaskManagerGuard:
    """مراقبة محاولات فتح Task Manager لقتل العملية"""

    def __init__(self, sio_client=None):
        self.sio = sio_client
        self.monitoring = False

    def start(self):
        """بدء مراقبة Task Manager"""
        self.monitoring = True
        threading.Thread(target=self._monitor_loop, daemon=True).start()

    def stop(self):
        self.monitoring = False

    def _monitor_loop(self):
        """مراقبة إذا حد حاول يفتح Task Manager أو يوقف الخدمة"""
        while self.monitoring:
            try:
                if SYSTEM == "Windows":
                    # فحص إذا Task Manager مفتوح ويعرض عمليتنا
                    result = subprocess.run(
                        ["tasklist", "/FI", "IMAGENAME eq taskmgr.exe", "/FO", "CSV", "/NH"],
                        capture_output=True, text=True, timeout=3
                    )
                    if "taskmgr.exe" in result.stdout.lower():
                        # Task Manager مفتوح — تنبيه
                        if self.sio:
                            try:
                                import socket as sock
                                self.sio.emit("agent_alert", {
                                    "agent_id": sock.gethostname(),
                                    "hostname": sock.gethostname(),
                                    "message": "⚠️ تم فتح Task Manager — محاولة محتملة لإيقاف المراقبة",
                                    "severity": "MEDIUM",
                                })
                            except:
                                pass

                    # فحص محاولة إيقاف الخدمة
                    result2 = subprocess.run(
                        ["tasklist", "/FI", "IMAGENAME eq services.msc", "/FO", "CSV", "/NH"],
                        capture_output=True, text=True, timeout=3
                    )

                elif SYSTEM == "Linux":
                    # فحص أوامر إيقاف
                    result = subprocess.run(
                        ["ps", "-eo", "args"],
                        capture_output=True, text=True, timeout=3
                    )
                    for line in result.stdout.split('\n'):
                        if "systemctl stop endpoint" in line or "kill" in line:
                            if self.sio:
                                try:
                                    import socket as sock
                                    self.sio.emit("agent_alert", {
                                        "agent_id": sock.gethostname(),
                                        "hostname": sock.gethostname(),
                                        "message": f"⚠️ محاولة إيقاف: {line.strip()[:60]}",
                                        "severity": "HIGH",
                                    })
                                except:
                                    pass

            except:
                pass

            time.sleep(10)


# ============================================
#   Secure Uninstaller (إزالة آمنة)
# ============================================
class SecureUninstaller:
    """إزالة البرنامج — فقط بكلمة مرور المسؤول"""

    @staticmethod
    def uninstall(password):
        """إزالة البرنامج بكلمة المرور"""
        # التحقق من كلمة المرور
        if not UninstallLock.verify(password):
            logger.warning("❌ Wrong uninstall password!")
            return False

        logger.info("🔓 Uninstall authorized")

        install_dir = Path(__file__).parent

        # 1. رفع حماية الملفات
        fp = FileProtector()
        fp.unprotect_files()

        # 2. إيقاف الخدمات
        if SYSTEM == "Windows":
            subprocess.run(
                ["schtasks", "/delete", "/tn", "EndpointSecurityMonitor", "/f"],
                capture_output=True, timeout=5
            )
            subprocess.run(
                ["schtasks", "/delete", "/tn", "EndpointWatchdog", "/f"],
                capture_output=True, timeout=5
            )

        elif SYSTEM == "Linux":
            # رفع immutable
            service_file = "/etc/systemd/system/endpoint-monitor.service"
            subprocess.run(["chattr", "-i", service_file], capture_output=True, timeout=3)
            subprocess.run(["systemctl", "stop", "endpoint-monitor"], capture_output=True)
            subprocess.run(["systemctl", "disable", "endpoint-monitor"], capture_output=True)
            try:
                os.remove(service_file)
                shutil.rmtree("/etc/systemd/system/endpoint-monitor.service.d", ignore_errors=True)
            except:
                pass
            subprocess.run(["systemctl", "daemon-reload"], capture_output=True)

        elif SYSTEM == "Darwin":
            plist = os.path.expanduser(
                "~/Library/LaunchAgents/com.security.endpointmonitor.plist"
            )
            subprocess.run(["chflags", "nouchg", plist], capture_output=True, timeout=3)
            subprocess.run(["launchctl", "unload", plist], capture_output=True)
            try:
                os.remove(plist)
            except:
                pass

        # 3. إيقاف الحارس
        watchdog_script = install_dir / ".watchdog.py"
        if SYSTEM == "Windows":
            subprocess.run(
                ["taskkill", "/F", "/FI", f"WINDOWTITLE eq *watchdog*"],
                capture_output=True, timeout=5
            )
        else:
            subprocess.run(
                ["pkill", "-f", ".watchdog.py"],
                capture_output=True, timeout=5
            )

        logger.info("✅ Uninstall complete. You can now delete the folder.")
        return True


# ============================================
#   Main Protection Engine
# ============================================
class SelfProtectionEngine:
    """محرك الحماية الذاتية الرئيسي"""

    def __init__(self, config, sio_client=None):
        self.config = config
        self.sio = sio_client
        self.file_protector = FileProtector()
        self.tm_guard = TaskManagerGuard(sio_client)

    def activate(self):
        """تفعيل كل الحمايات"""
        logger.info("🛡️ Activating self-protection...")

        # 1. قفل الإزالة
        if not UninstallLock.is_locked():
            UninstallLock.initialize()
        logger.info("  ✓ Uninstall lock active")

        # 2. حفظ PID
        ProcessGuardian.save_pid()

        # 3. تشغيل الحارس
        ProcessGuardian.start_watchdog()
        logger.info("  ✓ Watchdog running")

        # 4. نسخة احتياطية
        self.file_protector.create_backup()
        logger.info("  ✓ Backup created")

        # 5. حماية الملفات
        self.file_protector.protect_files()
        logger.info("  ✓ Files protected")

        # 6. حماية الخدمة
        if SYSTEM == "Windows":
            ServiceProtector.protect_windows_service()
        elif SYSTEM == "Linux":
            ServiceProtector.protect_linux_service()
        elif SYSTEM == "Darwin":
            ServiceProtector.protect_mac_service()
        logger.info("  ✓ Service protected")

        # 7. منع الإيقاف
        AntiKill.setup()
        logger.info("  ✓ Anti-kill active")

        # 8. مراقبة Task Manager
        self.tm_guard.start()
        logger.info("  ✓ Task manager guard active")

        # 9. فحص سلامة الملفات دوري
        threading.Thread(target=self._integrity_loop, daemon=True).start()
        logger.info("  ✓ Integrity monitor active")

        # إعداد أحداث الداشبورد
        self._setup_socket_events()

        logger.info("🛡️ Self-protection fully activated")

    def _integrity_loop(self):
        """فحص سلامة الملفات كل 30 ثانية"""
        while True:
            time.sleep(30)
            try:
                issues = self.file_protector.check_integrity()
                if issues:
                    logger.warning(f"⚠️ File integrity issues: {issues}")

                    # محاولة استعادة
                    self.file_protector.restore_from_backup()
                    self.file_protector.protect_files()

                    # تنبيه الداشبورد
                    if self.sio:
                        try:
                            import socket as sock
                            self.sio.emit("agent_alert", {
                                "agent_id": sock.gethostname(),
                                "hostname": sock.gethostname(),
                                "message": f"🚨 محاولة تلاعب بملفات البرنامج: {', '.join(i['file'] for i in issues)}",
                                "severity": "CRITICAL",
                            })
                        except:
                            pass
            except:
                pass

    def _setup_socket_events(self):
        """أحداث الداشبورد"""
        if not self.sio:
            return

        @self.sio.on("remote_uninstall")
        def on_remote_uninstall(data):
            """المسؤول يطلب إزالة من الداشبورد"""
            password = data.get("password", "")
            if SecureUninstaller.uninstall(password):
                self.sio.emit("uninstall_result", {
                    "success": True,
                    "hostname": platform.node(),
                })
            else:
                self.sio.emit("uninstall_result", {
                    "success": False,
                    "hostname": platform.node(),
                    "error": "كلمة المرور خاطئة",
                })

        @self.sio.on("change_uninstall_password")
        def on_change_password(data):
            """تغيير كلمة مرور الإزالة"""
            old_pwd = data.get("old_password", "")
            new_pwd = data.get("new_password", "")
            success = UninstallLock.change_password(old_pwd, new_pwd)
            self.sio.emit("password_change_result", {
                "success": success,
                "hostname": platform.node(),
            })

        @self.sio.on("temporary_uninstall_unlock")
        def on_temp_unlock(data):
            """فتح مؤقت"""
            password = data.get("password", "")
            duration = data.get("duration_seconds", 120)
            success = UninstallLock.temporary_unlock(password, duration)
            self.sio.emit("unlock_result", {
                "success": success,
                "hostname": platform.node(),
                "duration": duration,
            })


# ============================================
#   Integration
# ============================================
def create_self_protection(config, sio_client=None):
    """إنشاء محرك الحماية"""
    engine = SelfProtectionEngine(config, sio_client)
    return engine


# ============================================
#   CLI - إزالة يدوية بكلمة المرور
# ============================================
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Self Protection Module")
    parser.add_argument("--uninstall", action="store_true", help="Uninstall (requires password)")
    parser.add_argument("--set-password", action="store_true", help="Set uninstall password")
    parser.add_argument("--status", action="store_true", help="Show protection status")
    args = parser.parse_args()

    if args.status:
        print()
        print(f"  🔐 القفل: {'مفعل' if UninstallLock.is_locked() else 'غير مفعل'}")
        print(f"  🖥️ النظام: {SYSTEM}")
        fp = FileProtector()
        issues = fp.check_integrity()
        if issues:
            print(f"  ⚠️ مشاكل: {len(issues)}")
            for i in issues:
                print(f"     - {i['file']}: {i['issue']}")
        else:
            print(f"  ✅ الملفات سليمة")
        print()
        sys.exit(0)

    if args.set_password:
        print()
        import getpass
        pwd1 = getpass.getpass("  أدخل كلمة المرور الجديدة: ")
        pwd2 = getpass.getpass("  أعد إدخال كلمة المرور: ")
        if pwd1 != pwd2:
            print("  ❌ كلمات المرور غير متطابقة")
            sys.exit(1)
        UninstallLock.initialize(pwd1)
        print("  ✅ تم تعيين كلمة المرور")
        print()
        sys.exit(0)

    if args.uninstall:
        print()
        print("  ⚠️  إزالة Endpoint Security Monitor")
        print()
        import getpass
        password = getpass.getpass("  أدخل كلمة مرور الإزالة: ")
        if SecureUninstaller.uninstall(password):
            print("  ✅ تمت الإزالة — يمكنك حذف المجلد الآن")
        else:
            print("  ❌ كلمة المرور خاطئة!")
        print()
        sys.exit(0)

    print("  استخدم --help لعرض الخيارات")
