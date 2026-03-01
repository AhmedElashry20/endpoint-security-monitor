#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║     Remote Access Remover - إزالة ومنع برامج التحكم          ║
║                                                              ║
║     • مسح جميع برامج التحكم عن بُعد من الجهاز               ║
║     • منع إعادة تثبيتها نهائياً                              ║
║     • مراقبة مستمرة لأي محاولة تثبيت جديدة                  ║
║     ⚠️ لا يتدخل في ملفات الموظف الشخصية                     ║
╚══════════════════════════════════════════════════════════════╝
"""

import os
import sys
import time
import json
import shutil
import platform
import subprocess
import threading
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("RemoteAccessRemover")
SYSTEM = platform.system()


# ============================================
#   قاعدة بيانات برامج التحكم
# ============================================
REMOTE_ACCESS_APPS = {

    "AnyDesk": {
        "processes": ["AnyDesk.exe", "anydesk.exe", "anydesk"],
        "services": ["AnyDesk"],
        "win_uninstall": [
            r"C:\Program Files (x86)\AnyDesk\AnyDesk.exe --remove",
            r"C:\Program Files\AnyDesk\AnyDesk.exe --remove",
        ],
        "win_paths": [
            r"C:\Program Files (x86)\AnyDesk",
            r"C:\Program Files\AnyDesk",
            r"C:\ProgramData\AnyDesk",
        ],
        "win_reg_keys": [
            r"HKLM\SOFTWARE\AnyDesk",
            r"HKLM\SOFTWARE\WOW6432Node\AnyDesk",
            r"HKCU\SOFTWARE\AnyDesk",
        ],
        "linux_packages": ["anydesk"],
        "linux_paths": ["/usr/bin/anydesk", "/opt/anydesk"],
        "mac_apps": ["AnyDesk.app"],
        "mac_paths": ["/Applications/AnyDesk.app"],
        "firewall_ports": [7070],
    },

    "TeamViewer": {
        "processes": ["TeamViewer.exe", "TeamViewer_Service.exe", "teamviewer", "teamviewerd"],
        "services": ["TeamViewer", "teamviewerd"],
        "win_uninstall": [
            r"C:\Program Files\TeamViewer\uninstall.exe /S",
            r"C:\Program Files (x86)\TeamViewer\uninstall.exe /S",
        ],
        "win_paths": [
            r"C:\Program Files\TeamViewer",
            r"C:\Program Files (x86)\TeamViewer",
        ],
        "win_reg_keys": [
            r"HKLM\SOFTWARE\TeamViewer",
            r"HKLM\SOFTWARE\WOW6432Node\TeamViewer",
        ],
        "linux_packages": ["teamviewer"],
        "linux_paths": ["/usr/bin/teamviewer", "/opt/teamviewer"],
        "mac_apps": ["TeamViewer.app"],
        "mac_paths": ["/Applications/TeamViewer.app"],
        "firewall_ports": [5938],
    },

    "RustDesk": {
        "processes": ["rustdesk.exe", "rustdesk"],
        "services": ["rustdesk", "RustDesk"],
        "win_uninstall": [],
        "win_paths": [
            r"C:\Program Files\RustDesk",
            r"C:\Users\*\AppData\Roaming\RustDesk",
        ],
        "win_reg_keys": [r"HKLM\SOFTWARE\RustDesk"],
        "linux_packages": ["rustdesk"],
        "linux_paths": ["/usr/bin/rustdesk", "/usr/lib/rustdesk"],
        "mac_apps": ["RustDesk.app"],
        "mac_paths": ["/Applications/RustDesk.app"],
        "firewall_ports": [21115, 21116, 21117, 21118, 21119],
    },

    "Chrome Remote Desktop": {
        "processes": ["remoting_host.exe", "remoting_host"],
        "services": ["chromoting", "Chrome Remote Desktop*"],
        "win_uninstall": [],
        "win_paths": [
            r"C:\Program Files (x86)\Google\Chrome Remote Desktop",
        ],
        "win_reg_keys": [],
        "linux_packages": ["chrome-remote-desktop"],
        "linux_paths": ["/opt/google/chrome-remote-desktop"],
        "mac_apps": [],
        "mac_paths": [],
        "firewall_ports": [],
    },

    "Splashtop": {
        "processes": ["SplashtopStreamer.exe", "SRService.exe"],
        "services": ["SplashtopRemoteService"],
        "win_uninstall": [],
        "win_paths": [r"C:\Program Files (x86)\Splashtop", r"C:\Program Files\Splashtop"],
        "win_reg_keys": [r"HKLM\SOFTWARE\Splashtop"],
        "linux_packages": [],
        "linux_paths": [],
        "mac_apps": ["Splashtop Streamer.app"],
        "mac_paths": ["/Applications/Splashtop Streamer.app"],
        "firewall_ports": [],
    },

    "Parsec": {
        "processes": ["parsecd.exe", "parsec"],
        "services": ["Parsec"],
        "win_uninstall": [],
        "win_paths": [r"C:\Program Files\Parsec"],
        "win_reg_keys": [r"HKLM\SOFTWARE\Parsec"],
        "linux_packages": ["parsec"],
        "linux_paths": ["/usr/bin/parsec"],
        "mac_apps": ["Parsec.app"],
        "mac_paths": ["/Applications/Parsec.app"],
        "firewall_ports": [],
    },

    "LogMeIn": {
        "processes": ["LogMeIn.exe", "LMIGuardianSvc.exe"],
        "services": ["LogMeIn", "LMIMaint"],
        "win_uninstall": [],
        "win_paths": [r"C:\Program Files (x86)\LogMeIn", r"C:\Program Files\LogMeIn"],
        "win_reg_keys": [r"HKLM\SOFTWARE\LogMeIn"],
        "linux_packages": [],
        "linux_paths": [],
        "mac_apps": ["LogMeIn Client.app"],
        "mac_paths": ["/Applications/LogMeIn Client.app"],
        "firewall_ports": [],
    },

    "VNC": {
        "processes": ["winvnc.exe", "vncserver", "Xvnc", "x11vnc", "vncviewer.exe",
                      "tvnserver.exe", "winvnc4.exe"],
        "services": ["uvnc_service", "vncserver", "tvnserver", "x11vnc"],
        "win_uninstall": [],
        "win_paths": [
            r"C:\Program Files\UltraVNC",
            r"C:\Program Files\TightVNC",
            r"C:\Program Files\RealVNC",
            r"C:\Program Files (x86)\UltraVNC",
            r"C:\Program Files (x86)\TightVNC",
        ],
        "win_reg_keys": [
            r"HKLM\SOFTWARE\UltraVNC",
            r"HKLM\SOFTWARE\TightVNC",
            r"HKLM\SOFTWARE\RealVNC",
        ],
        "linux_packages": ["tigervnc-standalone-server", "tightvncserver",
                           "x11vnc", "realvnc-vnc-server"],
        "linux_paths": ["/usr/bin/vncserver", "/usr/bin/x11vnc", "/usr/bin/Xvnc"],
        "mac_apps": [],
        "mac_paths": [],
        "firewall_ports": [5900, 5901, 5800],
    },

    "Radmin": {
        "processes": ["radmin.exe", "rserver3.exe"],
        "services": ["RManService", "Radmin3"],
        "win_uninstall": [],
        "win_paths": [r"C:\Program Files (x86)\Radmin", r"C:\Program Files\Radmin"],
        "win_reg_keys": [r"HKLM\SOFTWARE\Radmin"],
        "linux_packages": [],
        "linux_paths": [],
        "mac_apps": [],
        "mac_paths": [],
        "firewall_ports": [4899],
    },

    "Supremo": {
        "processes": ["Supremo.exe", "SupremoService.exe"],
        "services": ["SupremoService"],
        "win_uninstall": [],
        "win_paths": [r"C:\Program Files\Supremo", r"C:\ProgramData\SupremoControl"],
        "win_reg_keys": [r"HKLM\SOFTWARE\Supremo"],
        "linux_packages": [],
        "linux_paths": [],
        "mac_apps": [],
        "mac_paths": [],
        "firewall_ports": [],
    },

    "Ammyy Admin": {
        "processes": ["AA_v3.exe", "ammyy.exe"],
        "services": ["AmmyyAdmin"],
        "win_uninstall": [],
        "win_paths": [],
        "win_reg_keys": [],
        "linux_packages": [],
        "linux_paths": [],
        "mac_apps": [],
        "mac_paths": [],
        "firewall_ports": [],
    },

    "MeshCentral": {
        "processes": ["MeshAgent.exe", "meshagent"],
        "services": ["MeshAgent", "meshagent"],
        "win_uninstall": [r"C:\Program Files\Mesh Agent\MeshAgent.exe -uninstall"],
        "win_paths": [r"C:\Program Files\Mesh Agent"],
        "win_reg_keys": [],
        "linux_packages": [],
        "linux_paths": ["/opt/meshagent", "/usr/local/mesh"],
        "mac_apps": [],
        "mac_paths": ["/opt/meshagent"],
        "firewall_ports": [],
    },

    "DWService": {
        "processes": ["dwagent.exe", "dwagent"],
        "services": ["DWAgent", "dwagent"],
        "win_uninstall": [],
        "win_paths": [r"C:\Program Files\DWAgent", r"C:\Program Files (x86)\DWAgent"],
        "win_reg_keys": [],
        "linux_packages": [],
        "linux_paths": ["/usr/share/dwagent"],
        "mac_apps": [],
        "mac_paths": ["/Library/DWAgent"],
        "firewall_ports": [],
    },

    "NoMachine": {
        "processes": ["nxd", "nxserver", "nxnode", "nxserver.bin"],
        "services": ["nxservice", "nxserver"],
        "win_uninstall": [],
        "win_paths": [r"C:\Program Files\NoMachine", r"C:\Program Files (x86)\NoMachine"],
        "win_reg_keys": [r"HKLM\SOFTWARE\NoMachine"],
        "linux_packages": ["nomachine"],
        "linux_paths": ["/usr/NX"],
        "mac_apps": ["NoMachine.app"],
        "mac_paths": ["/Applications/NoMachine.app"],
        "firewall_ports": [4000],
    },

    "ScreenConnect": {
        "processes": ["ScreenConnect.ClientService.exe", "ScreenConnect.WindowsClient.exe"],
        "services": ["ScreenConnect*"],
        "win_uninstall": [],
        "win_paths": [r"C:\Program Files (x86)\ScreenConnect Client*"],
        "win_reg_keys": [],
        "linux_packages": [],
        "linux_paths": ["/opt/screenconnect*"],
        "mac_apps": [],
        "mac_paths": [],
        "firewall_ports": [],
    },

    "Remote Utilities": {
        "processes": ["rfusclient.exe", "rutserv.exe"],
        "services": ["rutserv"],
        "win_uninstall": [],
        "win_paths": [r"C:\Program Files\Remote Utilities*"],
        "win_reg_keys": [r"HKLM\SOFTWARE\Remote Utilities"],
        "linux_packages": [],
        "linux_paths": [],
        "mac_apps": [],
        "mac_paths": [],
        "firewall_ports": [],
    },

    "NetSupport": {
        "processes": ["client32.exe", "PCICTLUI.exe"],
        "services": ["NetSupport*"],
        "win_uninstall": [],
        "win_paths": [r"C:\Program Files\NetSupport*", r"C:\Program Files (x86)\NetSupport*"],
        "win_reg_keys": [r"HKLM\SOFTWARE\NetSupport"],
        "linux_packages": [],
        "linux_paths": [],
        "mac_apps": [],
        "mac_paths": [],
        "firewall_ports": [],
    },

    "Zoho Assist": {
        "processes": ["ZohoAssist.exe", "ZohoMeeting.exe"],
        "services": ["ZohoAssist"],
        "win_uninstall": [],
        "win_paths": [r"C:\Program Files\Zoho\Assist"],
        "win_reg_keys": [],
        "linux_packages": [],
        "linux_paths": [],
        "mac_apps": ["Zoho Assist.app"],
        "mac_paths": ["/Applications/Zoho Assist.app"],
        "firewall_ports": [],
    },
}


# ============================================
#   App Remover (مسح البرامج)
# ============================================
class AppRemover:
    """مسح برامج التحكم عن بُعد من الجهاز"""

    def __init__(self):
        self.removed = []
        self.failed = []

    def remove_all(self):
        """مسح جميع برامج التحكم"""
        logger.info("🗑️ Starting removal of all remote access software...")
        total_removed = []

        for app_name, app_info in REMOTE_ACCESS_APPS.items():
            found = self._is_installed(app_name, app_info)
            if found:
                logger.info(f"  📍 Found: {app_name}")
                success = self._remove_app(app_name, app_info)
                if success:
                    total_removed.append(app_name)
                    logger.info(f"  ✅ Removed: {app_name}")
                else:
                    self.failed.append(app_name)
                    logger.warning(f"  ⚠️ Partial removal: {app_name}")

        self.removed = total_removed
        return total_removed

    def _is_installed(self, app_name, app_info):
        """هل البرنامج مثبت؟"""
        # فحص العمليات
        for proc in app_info.get("processes", []):
            if self._process_exists(proc):
                return True

        # فحص المسارات
        if SYSTEM == "Windows":
            for path in app_info.get("win_paths", []):
                import glob
                matches = glob.glob(path)
                if matches:
                    return True
        elif SYSTEM == "Linux":
            for path in app_info.get("linux_paths", []):
                if os.path.exists(path):
                    return True
            for pkg in app_info.get("linux_packages", []):
                if self._linux_package_installed(pkg):
                    return True
        elif SYSTEM == "Darwin":
            for path in app_info.get("mac_paths", []):
                if os.path.exists(path):
                    return True

        return False

    def _process_exists(self, proc_name):
        try:
            if SYSTEM == "Windows":
                result = subprocess.run(
                    ["tasklist", "/FI", f"IMAGENAME eq {proc_name}", "/FO", "CSV", "/NH"],
                    capture_output=True, text=True, timeout=5
                )
                return proc_name.lower() in result.stdout.lower()
            else:
                result = subprocess.run(
                    ["pgrep", "-f", proc_name],
                    capture_output=True, timeout=5
                )
                return result.returncode == 0
        except:
            return False

    def _linux_package_installed(self, package):
        try:
            result = subprocess.run(
                ["dpkg", "-l", package],
                capture_output=True, text=True, timeout=5
            )
            return "ii" in result.stdout
        except:
            try:
                result = subprocess.run(
                    ["rpm", "-q", package],
                    capture_output=True, timeout=5
                )
                return result.returncode == 0
            except:
                return False

    def _remove_app(self, app_name, app_info):
        """إزالة برنامج واحد"""
        success = True

        # 1. إيقاف العمليات
        for proc in app_info.get("processes", []):
            self._kill_process(proc)

        # 2. إيقاف الخدمات
        for service in app_info.get("services", []):
            self._stop_service(service)

        # 3. تشغيل أمر الإزالة الرسمي
        if SYSTEM == "Windows":
            for cmd in app_info.get("win_uninstall", []):
                try:
                    subprocess.run(cmd, shell=True, capture_output=True, timeout=60)
                except:
                    pass

            # إزالة من Add/Remove Programs
            self._win_uninstall_registry(app_name)

        elif SYSTEM == "Linux":
            for pkg in app_info.get("linux_packages", []):
                self._linux_remove_package(pkg)

        elif SYSTEM == "Darwin":
            for app in app_info.get("mac_apps", []):
                mac_path = f"/Applications/{app}"
                if os.path.exists(mac_path):
                    try:
                        shutil.rmtree(mac_path)
                    except:
                        subprocess.run(["sudo", "rm", "-rf", mac_path], capture_output=True)

        # 4. حذف المجلدات
        self._delete_paths(app_info)

        # 5. حذف من الريجستري (ويندوز)
        if SYSTEM == "Windows":
            for key in app_info.get("win_reg_keys", []):
                self._delete_registry(key)

        # 6. حذف الخدمات
        for service in app_info.get("services", []):
            self._delete_service(service)

        return success

    def _kill_process(self, proc_name):
        try:
            if SYSTEM == "Windows":
                subprocess.run(["taskkill", "/F", "/IM", proc_name],
                             capture_output=True, timeout=5)
            else:
                subprocess.run(["pkill", "-9", "-f", proc_name],
                             capture_output=True, timeout=5)
        except:
            pass

    def _stop_service(self, service_name):
        try:
            if SYSTEM == "Windows":
                subprocess.run(["net", "stop", service_name],
                             capture_output=True, timeout=15)
                subprocess.run(["sc", "config", service_name, "start=", "disabled"],
                             capture_output=True, timeout=5)
            elif SYSTEM == "Linux":
                subprocess.run(["systemctl", "stop", service_name],
                             capture_output=True, timeout=10)
                subprocess.run(["systemctl", "disable", service_name],
                             capture_output=True, timeout=5)
            elif SYSTEM == "Darwin":
                subprocess.run(["launchctl", "unload", "-w",
                              f"/Library/LaunchDaemons/{service_name}.plist"],
                             capture_output=True, timeout=5)
        except:
            pass

    def _delete_service(self, service_name):
        try:
            if SYSTEM == "Windows":
                subprocess.run(["sc", "delete", service_name],
                             capture_output=True, timeout=5)
            elif SYSTEM == "Linux":
                service_file = f"/etc/systemd/system/{service_name}.service"
                if os.path.exists(service_file):
                    os.remove(service_file)
                subprocess.run(["systemctl", "daemon-reload"],
                             capture_output=True, timeout=5)
        except:
            pass

    def _delete_paths(self, app_info):
        """حذف المجلدات"""
        import glob

        if SYSTEM == "Windows":
            paths = app_info.get("win_paths", [])
        elif SYSTEM == "Linux":
            paths = app_info.get("linux_paths", [])
        elif SYSTEM == "Darwin":
            paths = app_info.get("mac_paths", [])
        else:
            paths = []

        for pattern in paths:
            for path in glob.glob(pattern):
                try:
                    if os.path.isdir(path):
                        shutil.rmtree(path, ignore_errors=True)
                    elif os.path.isfile(path):
                        os.remove(path)
                except:
                    # محاولة بصلاحيات
                    try:
                        if SYSTEM == "Windows":
                            subprocess.run(["cmd", "/c", "rmdir", "/s", "/q", path],
                                         capture_output=True, timeout=10)
                        else:
                            subprocess.run(["sudo", "rm", "-rf", path],
                                         capture_output=True, timeout=10)
                    except:
                        pass

    def _win_uninstall_registry(self, app_name):
        """البحث عن برنامج الإزالة في الريجستري"""
        try:
            search_paths = [
                r"HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
                r"HKLM\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
                r"HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
            ]
            for reg_path in search_paths:
                result = subprocess.run(
                    ["reg", "query", reg_path, "/s", "/f", app_name],
                    capture_output=True, text=True, timeout=10
                )
                for line in result.stdout.split('\n'):
                    if "UninstallString" in line:
                        uninstall_cmd = line.split("REG_SZ")[-1].strip()
                        if uninstall_cmd:
                            # إضافة /S للإزالة الصامتة
                            if "/S" not in uninstall_cmd.upper():
                                uninstall_cmd += " /S"
                            subprocess.run(uninstall_cmd, shell=True,
                                         capture_output=True, timeout=60)
        except:
            pass

    def _delete_registry(self, key):
        """حذف مفتاح ريجستري"""
        if SYSTEM != "Windows":
            return
        try:
            subprocess.run(
                ["reg", "delete", key, "/f"],
                capture_output=True, timeout=5
            )
        except:
            pass

    def _linux_remove_package(self, package):
        """إزالة حزمة لينكس"""
        try:
            if os.path.exists("/usr/bin/apt-get"):
                subprocess.run(
                    ["apt-get", "remove", "--purge", "-y", package],
                    capture_output=True, timeout=60
                )
            elif os.path.exists("/usr/bin/dnf"):
                subprocess.run(
                    ["dnf", "remove", "-y", package],
                    capture_output=True, timeout=60
                )
            elif os.path.exists("/usr/bin/yum"):
                subprocess.run(
                    ["yum", "remove", "-y", package],
                    capture_output=True, timeout=60
                )
            elif os.path.exists("/usr/bin/pacman"):
                subprocess.run(
                    ["pacman", "-Rns", "--noconfirm", package],
                    capture_output=True, timeout=60
                )
        except:
            pass


# ============================================
#   Installation Blocker (منع التثبيت)
# ============================================
class InstallationBlocker:
    """منع إعادة تثبيت برامج التحكم"""

    BLOCK_NAMES = []  # يتم تعبئتها تلقائياً

    def __init__(self):
        # أسماء الملفات التنفيذية المحظورة
        self.blocked_executables = set()
        for app_name, app_info in REMOTE_ACCESS_APPS.items():
            for proc in app_info.get("processes", []):
                self.blocked_executables.add(proc.lower())
                self.blocked_executables.add(proc.lower().replace(".exe", ""))

        # أسماء المثبتات المعروفة
        self.blocked_installers = [
            "anydesk", "teamviewer", "rustdesk", "splashtop",
            "parsec", "logmein", "ultravnc", "tightvnc", "realvnc",
            "radmin", "supremo", "ammyy", "meshagent", "dwagent",
            "nomachine", "screenconnect", "remoteutilities", "netsupport",
            "zohoassist", "chrome-remote-desktop",
        ]

        self.monitoring = False
        # تتبع البرامج التي تم مسحها بالفعل لمنع التكرار
        self.already_removed = set()

    def start_blocking(self):
        """بدء منع التثبيت"""
        self.monitoring = True

        # 1. حظر بالفايروول
        self._block_firewall()

        # 2. إنشاء ملفات وهمية (Decoy) تمنع التثبيت
        self._create_decoy_files()

        # 3. مراقبة مستمرة لأي تثبيت جديد
        threading.Thread(target=self._monitor_loop, daemon=True).start()

        # 4. على ويندوز: استخدام AppLocker / Software Restriction
        if SYSTEM == "Windows":
            self._windows_block_policy()

        logger.info("🚫 Installation blocker activated")

    def stop_blocking(self):
        self.monitoring = False

    def _block_firewall(self):
        """حظر بورتات برامج التحكم بالفايروول"""
        blocked_ports = set()
        for app_info in REMOTE_ACCESS_APPS.values():
            for port in app_info.get("firewall_ports", []):
                blocked_ports.add(port)

        for port in blocked_ports:
            try:
                if SYSTEM == "Windows":
                    # حظر الدخول
                    subprocess.run([
                        "netsh", "advfirewall", "firewall", "add", "rule",
                        f"name=Block_RemoteAccess_IN_{port}",
                        "dir=in", "action=block",
                        f"localport={port}", "protocol=tcp",
                        "enable=yes"
                    ], capture_output=True, timeout=5)
                    # حظر الخروج
                    subprocess.run([
                        "netsh", "advfirewall", "firewall", "add", "rule",
                        f"name=Block_RemoteAccess_OUT_{port}",
                        "dir=out", "action=block",
                        f"localport={port}", "protocol=tcp",
                        "enable=yes"
                    ], capture_output=True, timeout=5)

                elif SYSTEM == "Linux":
                    subprocess.run([
                        "iptables", "-A", "INPUT",
                        "-p", "tcp", "--dport", str(port), "-j", "DROP"
                    ], capture_output=True, timeout=5)
                    subprocess.run([
                        "iptables", "-A", "OUTPUT",
                        "-p", "tcp", "--dport", str(port), "-j", "DROP"
                    ], capture_output=True, timeout=5)

            except:
                pass

        logger.info(f"  🔥 Firewall: blocked {len(blocked_ports)} ports")

    def _create_decoy_files(self):
        """
        إنشاء مجلدات/ملفات وهمية بنفس أسماء البرامج
        بعض المثبتات ترفض التثبيت لو لقت ملف بنفس الاسم
        """
        if SYSTEM == "Windows":
            for app_info in REMOTE_ACCESS_APPS.values():
                for path in app_info.get("win_paths", []):
                    if "*" in path:
                        continue
                    try:
                        # إنشاء ملف فارغ بدل مجلد (يمنع التثبيت)
                        if not os.path.exists(path):
                            # ننشئ المجلد الأب
                            parent = os.path.dirname(path)
                            if os.path.exists(parent):
                                # ننشئ ملف بنفس اسم المجلد عشان المثبت يفشل
                                with open(path, 'w') as f:
                                    f.write("BLOCKED")
                                # نخليه read-only
                                subprocess.run(
                                    ["attrib", "+r", "+s", "+h", path],
                                    capture_output=True, timeout=3
                                )
                    except:
                        pass

    def _windows_block_policy(self):
        """حظر عبر Software Restriction Policy على ويندوز"""
        try:
            # حظر تشغيل أي ملف تنفيذي بأسماء البرامج المحظورة
            for installer in self.blocked_installers:
                rule_name = f"Block_{installer}_Install"
                # حظر من Program Files
                for prog_dir in [r"%ProgramFiles%", r"%ProgramFiles(x86)%", r"%LocalAppData%"]:
                    subprocess.run([
                        "netsh", "advfirewall", "firewall", "add", "rule",
                        f"name={rule_name}",
                        "dir=out", "action=block",
                        f"program={prog_dir}\\{installer}*\\*.exe",
                        "enable=yes"
                    ], capture_output=True, timeout=5)
        except:
            pass

    def _monitor_loop(self):
        """مراقبة مستمرة لأي تثبيت جديد"""
        logger.info("👁️ Monitoring for new installations...")

        while self.monitoring:
            try:
                # فحص العمليات الشغالة
                if SYSTEM == "Windows":
                    result = subprocess.run(
                        ["tasklist", "/FO", "CSV", "/NH"],
                        capture_output=True, text=True, timeout=5
                    )
                    for line in result.stdout.strip().split('\n'):
                        parts = line.strip('"').split('","')
                        if parts:
                            proc_name = parts[0].lower()
                            # هل هو برنامج تحكم أو مثبت لبرنامج تحكم؟
                            if proc_name in self.blocked_executables:
                                self._handle_blocked(proc_name)
                            # فحص المثبتات
                            for installer in self.blocked_installers:
                                if installer in proc_name:
                                    self._handle_blocked(proc_name)

                else:
                    result = subprocess.run(
                        ["ps", "-eo", "comm"],
                        capture_output=True, text=True, timeout=5
                    )
                    for line in result.stdout.strip().split('\n'):
                        proc_name = line.strip().lower()
                        if proc_name in self.blocked_executables:
                            self._handle_blocked(proc_name)
                        for installer in self.blocked_installers:
                            if installer in proc_name:
                                self._handle_blocked(proc_name)

                # فحص المسارات — لو حد ثبت شي جديد
                # تخطي البرامج اللي اتمسحت قبل كده (مجلدات متبقية مش بتتمسح)
                # بس لو لقينا عملية شغالة (process) يبقى فعلاً اتثبت من جديد
                remover = AppRemover()
                for app_name, app_info in REMOTE_ACCESS_APPS.items():
                    # لو البرنامج اتمسح قبل كده، بس نتحقق من العمليات مش المجلدات
                    if app_name in self.already_removed:
                        # فحص العمليات فقط (مش المجلدات)
                        has_process = False
                        for proc in app_info.get("processes", []):
                            if remover._process_exists(proc):
                                has_process = True
                                break
                        if has_process:
                            logger.warning(f"🚨 Re-installation detected: {app_name}")
                            remover._remove_app(app_name, app_info)
                            logger.info(f"✅ Re-removed: {app_name}")
                    else:
                        # برنامج جديد — فحص كامل (مجلدات + عمليات)
                        if remover._is_installed(app_name, app_info):
                            logger.warning(f"🚨 Re-installation detected: {app_name}")
                            remover._remove_app(app_name, app_info)
                            self.already_removed.add(app_name)
                            logger.info(f"✅ Re-removed: {app_name}")

            except:
                pass

            time.sleep(10)

    def _handle_blocked(self, proc_name):
        """التعامل مع عملية محظورة"""
        logger.warning(f"🚫 BLOCKED: {proc_name}")

        # إيقاف فوري
        try:
            if SYSTEM == "Windows":
                subprocess.run(["taskkill", "/F", "/IM", proc_name],
                             capture_output=True, timeout=5)
            else:
                subprocess.run(["pkill", "-9", "-f", proc_name],
                             capture_output=True, timeout=5)
        except:
            pass


# ============================================
#   Main Engine
# ============================================
class RemoteAccessRemoverEngine:
    """المحرك الرئيسي — مسح + منع"""

    def __init__(self, config, sio_client=None):
        self.config = config
        self.sio = sio_client
        self.remover = AppRemover()
        self.blocker = InstallationBlocker()

    def execute(self):
        """تنفيذ المسح ومنع التثبيت"""

        # 1. مسح كل البرامج
        logger.info("=" * 50)
        logger.info("🗑️ Phase 1: Removing remote access software...")
        logger.info("=" * 50)

        removed = self.remover.remove_all()

        if removed:
            logger.info(f"✅ Removed {len(removed)} apps: {', '.join(removed)}")
            # تسجيل البرامج اللي اتمسحت عشان الـ blocker ميكررش المسح
            for app_name in removed:
                self.blocker.already_removed.add(app_name)
            # تنبيه الداشبورد
            if self.sio:
                try:
                    import socket
                    self.sio.emit("agent_alert", {
                        "agent_id": socket.gethostname(),
                        "hostname": socket.gethostname(),
                        "message": f"تم مسح {len(removed)} برنامج تحكم: {', '.join(removed)}",
                        "severity": "HIGH",
                    })
                except:
                    pass
        else:
            logger.info("✅ No remote access software found")

        # 2. تفعيل منع التثبيت
        logger.info("")
        logger.info("=" * 50)
        logger.info("🚫 Phase 2: Blocking future installations...")
        logger.info("=" * 50)

        self.blocker.start_blocking()

        logger.info("✅ Protection active — remote access apps blocked")

        return removed

    def stop(self):
        self.blocker.stop_blocking()


# ============================================
#   Integration
# ============================================
def create_remover_engine(config, sio_client=None):
    """إنشاء المحرك"""
    return RemoteAccessRemoverEngine(config, sio_client)


# ============================================
#   CLI
# ============================================
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')

    print("""
╔══════════════════════════════════════════════════════════════╗
║     🗑️  Remote Access Software Remover                       ║
║     مسح ومنع برامج التحكم عن بُعد                            ║
╚══════════════════════════════════════════════════════════════╝
    """)

    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--scan", action="store_true", help="Scan only (don't remove)")
    parser.add_argument("--remove", action="store_true", help="Remove all + block")
    args = parser.parse_args()

    if args.scan:
        print("  🔍 جاري الفحص...")
        remover = AppRemover()
        found = []
        for app_name, app_info in REMOTE_ACCESS_APPS.items():
            if remover._is_installed(app_name, app_info):
                found.append(app_name)
                print(f"  📍 موجود: {app_name}")
        if not found:
            print("  ✅ لا توجد برامج تحكم مثبتة")
        else:
            print(f"\n  ⚠️ وُجد {len(found)} برنامج")
    elif args.remove:
        engine = RemoteAccessRemoverEngine({})
        engine.execute()
        print("\n  اضغط Ctrl+C للإيقاف")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            engine.stop()
    else:
        print("  --scan    فحص فقط")
        print("  --remove  مسح + منع التثبيت")
