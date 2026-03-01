#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════╗
║     Endpoint Security Monitor Agent v1.0                 ║
║     وكيل مراقبة أمن الأجهزة الطرفية                      ║
║     Cross-Platform: Windows / macOS / Linux              ║
╚══════════════════════════════════════════════════════════╝
"""

import os
import sys
import time
import json
import socket
import hashlib
import platform
import threading
import subprocess
import logging
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

# ============================================
#   Configuration
# ============================================
CONFIG_FILE = Path(__file__).parent / "config.json"

DEFAULT_CONFIG = {
    "scan_interval_seconds": 30,
    "email": {
        "enabled": True,
        "smtp_server": "smtp.gmail.com",
        "smtp_port": 587,
        "sender_email": "your-alert-email@gmail.com",
        "sender_password": "your-app-password",
        "recipient_emails": ["admin@company.com"],
        "use_tls": True
    },
    "monitoring": {
        "remote_access": True,
        "network_connections": True,
        "software_installs": True,
        "usb_devices": True,
        "file_changes": True,
        "suspicious_processes": True
    },
    "watched_directories": [
        "~/Documents",
        "~/Desktop"
    ],
    "alert_cooldown_minutes": 15,
    "log_file": "monitor.log",
    "threats_log": "threats.json"
}

# ============================================
#   Remote Access Software Database
# ============================================
REMOTE_ACCESS_DB = {
    "AnyDesk": {
        "processes": ["anydesk", "AnyDesk", "AnyDesk.exe"],
        "ports": [7070],
        "dirs_win": ["AnyDesk"],
        "dirs_mac": ["AnyDesk"],
        "dirs_linux": ["anydesk"],
    },
    "TeamViewer": {
        "processes": ["teamviewer", "TeamViewer", "TeamViewer.exe", "TeamViewer_Service.exe"],
        "ports": [5938, 5939, 5940],
        "dirs_win": ["TeamViewer"],
        "dirs_mac": ["TeamViewer"],
        "dirs_linux": ["teamviewer"],
    },
    "RustDesk": {
        "processes": ["rustdesk", "RustDesk", "rustdesk.exe"],
        "ports": [21115, 21116, 21117, 21118, 21119],
        "dirs_win": ["RustDesk"],
        "dirs_mac": ["RustDesk"],
        "dirs_linux": ["rustdesk"],
    },
    "Chrome Remote Desktop": {
        "processes": ["remoting_host", "chrome_remote_desktop", "CRD_Host"],
        "ports": [],
        "dirs_win": ["Chrome Remote Desktop"],
        "dirs_mac": ["Chrome Remote Desktop Host"],
        "dirs_linux": ["chrome-remote-desktop"],
    },
    "Splashtop": {
        "processes": ["SplashtopStreamer", "SRManager.exe", "splashtop"],
        "ports": [6783],
        "dirs_win": ["Splashtop"],
        "dirs_mac": ["Splashtop"],
        "dirs_linux": ["splashtop"],
    },
    "Parsec": {
        "processes": ["parsecd", "parsec", "pservice.exe"],
        "ports": [8000],
        "dirs_win": ["Parsec"],
        "dirs_mac": ["Parsec"],
        "dirs_linux": ["parsec"],
    },
    "LogMeIn": {
        "processes": ["LogMeIn", "LMIGuardianSvc", "logmein"],
        "ports": [443],
        "dirs_win": ["LogMeIn"],
        "dirs_mac": ["LogMeIn"],
        "dirs_linux": ["logmein"],
    },
    "VNC": {
        "processes": ["vncserver", "vncviewer", "winvnc", "Xvnc", "x11vnc", "tigervnc"],
        "ports": [5900, 5901, 5800],
        "dirs_win": ["RealVNC", "TightVNC", "UltraVNC", "TigerVNC"],
        "dirs_mac": ["RealVNC", "TigerVNC"],
        "dirs_linux": ["vnc", "realvnc", "tigervnc"],
    },
    "Radmin": {
        "processes": ["radmin", "rserver3", "Radmin.exe"],
        "ports": [4899],
        "dirs_win": ["Radmin"],
        "dirs_mac": [],
        "dirs_linux": [],
    },
    "Supremo": {
        "processes": ["Supremo", "SupremoService", "Supremo.exe"],
        "ports": [443],
        "dirs_win": ["Supremo"],
        "dirs_mac": [],
        "dirs_linux": [],
    },
    "Ammyy Admin": {
        "processes": ["AA_v3", "Ammyy", "AMMYY"],
        "ports": [443],
        "dirs_win": ["Ammyy"],
        "dirs_mac": [],
        "dirs_linux": [],
    },
    "MeshCentral": {
        "processes": ["MeshAgent", "meshagent"],
        "ports": [443, 4433],
        "dirs_win": ["Mesh Agent"],
        "dirs_mac": ["meshagent"],
        "dirs_linux": ["meshagent"],
    },
    "DWService": {
        "processes": ["dwagent", "dwagsvc"],
        "ports": [443],
        "dirs_win": ["DWAgent"],
        "dirs_mac": ["DWAgent"],
        "dirs_linux": ["dwagent"],
    },
    "NoMachine": {
        "processes": ["nxd", "nxserver", "nxnode", "nxclient"],
        "ports": [4000],
        "dirs_win": ["NoMachine"],
        "dirs_mac": ["NoMachine"],
        "dirs_linux": ["NoMachine"],
    },
    "RemotePC": {
        "processes": ["RemotePC", "RPCService"],
        "ports": [443],
        "dirs_win": ["RemotePC"],
        "dirs_mac": ["RemotePC"],
        "dirs_linux": [],
    },
    "ConnectWise/ScreenConnect": {
        "processes": ["ScreenConnect", "ConnectWiseControl"],
        "ports": [8040, 8041],
        "dirs_win": ["ScreenConnect", "ConnectWise"],
        "dirs_mac": ["connectwisecontrol"],
        "dirs_linux": ["connectwisecontrol"],
    },
    "Zoho Assist": {
        "processes": ["ZohoMeeting", "ZohoAssist", "zaaborservice"],
        "ports": [443],
        "dirs_win": ["ZohoMeeting", "Zoho Assist"],
        "dirs_mac": ["ZohoAssist"],
        "dirs_linux": ["zohoassist"],
    },
    "Dameware": {
        "processes": ["DWRCC", "dwmrcs"],
        "ports": [6129],
        "dirs_win": ["Dameware"],
        "dirs_mac": [],
        "dirs_linux": [],
    },
    "NetSupport": {
        "processes": ["client32", "PCICTLUI"],
        "ports": [5405],
        "dirs_win": ["NetSupport"],
        "dirs_mac": [],
        "dirs_linux": [],
    },
    "Remote Utilities": {
        "processes": ["rfusclient", "rutserv"],
        "ports": [5650, 5651],
        "dirs_win": ["Remote Utilities"],
        "dirs_mac": [],
        "dirs_linux": [],
    },
}

# Suspicious ports for network monitoring
SUSPICIOUS_PORTS = {
    4444: "Metasploit default",
    4445: "Metasploit",
    1337: "Common backdoor",
    31337: "Back Orifice",
    5555: "Android Debug Bridge",
    6666: "Common backdoor",
    6667: "IRC (potential C2)",
    8080: "HTTP Proxy",
    9090: "Common backdoor",
    12345: "NetBus",
    27374: "SubSeven",
    65535: "Common backdoor",
}


# ============================================
#   Logging Setup
# ============================================
def setup_logging(log_file):
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger("EndpointMonitor")


# ============================================
#   Email Alert System
# ============================================
class EmailAlerter:
    def __init__(self, config):
        self.config = config.get("email", {})
        self.enabled = self.config.get("enabled", False)
        self.cooldown = defaultdict(lambda: datetime.min)
        self.cooldown_minutes = config.get("alert_cooldown_minutes", 15)

    def _should_alert(self, alert_key):
        """Prevent alert flooding with cooldown"""
        now = datetime.now()
        if now - self.cooldown[alert_key] < timedelta(minutes=self.cooldown_minutes):
            return False
        self.cooldown[alert_key] = now
        return True

    def send_alert(self, subject, body, alert_key=None):
        """Send email alert"""
        if not self.enabled:
            return False

        if alert_key and not self._should_alert(alert_key):
            return False

        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart

            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"🚨 تنبيه أمني - {subject}"
            msg["From"] = self.config["sender_email"]
            msg["To"] = ", ".join(self.config["recipient_emails"])

            # Plain text
            text_part = MIMEText(body, "plain", "utf-8")

            # HTML version
            html_body = self._create_html_email(subject, body)
            html_part = MIMEText(html_body, "html", "utf-8")

            msg.attach(text_part)
            msg.attach(html_part)

            with smtplib.SMTP(self.config["smtp_server"], self.config["smtp_port"]) as server:
                if self.config.get("use_tls", True):
                    server.starttls()
                server.login(self.config["sender_email"], self.config["sender_password"])
                server.sendmail(
                    self.config["sender_email"],
                    self.config["recipient_emails"],
                    msg.as_string()
                )
            return True

        except Exception as e:
            logging.getLogger("EndpointMonitor").error(f"Failed to send email: {e}")
            return False

    def _create_html_email(self, subject, body):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        hostname = socket.gethostname()
        os_info = f"{platform.system()} {platform.release()}"

        lines = body.replace('\n', '<br>')

        return f"""
        <html dir="rtl">
        <head><meta charset="utf-8"></head>
        <body style="font-family: Arial, sans-serif; background-color: #f5f5f5; padding: 20px;">
            <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 10px; overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                <div style="background: linear-gradient(135deg, #e74c3c, #c0392b); color: white; padding: 20px; text-align: center;">
                    <h1 style="margin: 0;">🚨 تنبيه أمني</h1>
                    <p style="margin: 5px 0 0; opacity: 0.9;">{subject}</p>
                </div>
                <div style="padding: 20px;">
                    <div style="background: #fff3cd; border-right: 4px solid #ffc107; padding: 12px; margin-bottom: 15px; border-radius: 4px;">
                        <strong>⚠️ تم اكتشاف نشاط مشبوه على أحد الأجهزة</strong>
                    </div>
                    <table style="width: 100%; border-collapse: collapse; margin-bottom: 15px;">
                        <tr style="border-bottom: 1px solid #eee;">
                            <td style="padding: 8px; font-weight: bold; color: #555;">الجهاز:</td>
                            <td style="padding: 8px;">{hostname}</td>
                        </tr>
                        <tr style="border-bottom: 1px solid #eee;">
                            <td style="padding: 8px; font-weight: bold; color: #555;">النظام:</td>
                            <td style="padding: 8px;">{os_info}</td>
                        </tr>
                        <tr style="border-bottom: 1px solid #eee;">
                            <td style="padding: 8px; font-weight: bold; color: #555;">الوقت:</td>
                            <td style="padding: 8px;">{timestamp}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px; font-weight: bold; color: #555;">المستخدم:</td>
                            <td style="padding: 8px;">{self._get_current_user()}</td>
                        </tr>
                    </table>
                    <div style="background: #f8f9fa; padding: 15px; border-radius: 5px; border: 1px solid #dee2e6;">
                        <h3 style="margin-top: 0; color: #e74c3c;">التفاصيل:</h3>
                        <p style="white-space: pre-wrap; line-height: 1.8;">{lines}</p>
                    </div>
                    <div style="margin-top: 15px; padding: 12px; background: #d4edda; border-radius: 4px; border-right: 4px solid #28a745;">
                        <strong>📋 الإجراء المطلوب:</strong><br>
                        يرجى مراجعة هذا التنبيه واتخاذ الإجراء المناسب فوراً.
                    </div>
                </div>
                <div style="background: #f8f9fa; padding: 15px; text-align: center; color: #888; font-size: 12px; border-top: 1px solid #eee;">
                    Endpoint Security Monitor v1.0 | تم الإرسال تلقائياً
                </div>
            </div>
        </body>
        </html>
        """

    def _get_current_user(self):
        try:
            return os.getlogin()
        except:
            return os.environ.get("USER", os.environ.get("USERNAME", "Unknown"))


# ============================================
#   Threat Logger
# ============================================
class ThreatLogger:
    def __init__(self, filepath):
        self.filepath = Path(filepath)
        self.threats = self._load()

    def _load(self):
        if self.filepath.exists():
            try:
                with open(self.filepath, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return []
        return []

    def log(self, threat_type, details):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "hostname": socket.gethostname(),
            "user": os.environ.get("USER", os.environ.get("USERNAME", "Unknown")),
            "os": platform.system(),
            "type": threat_type,
            "details": details,
        }
        self.threats.append(entry)
        self._save()
        return entry

    def _save(self):
        with open(self.filepath, 'w', encoding='utf-8') as f:
            json.dump(self.threats, f, ensure_ascii=False, indent=2)


# ============================================
#   Cross-Platform Process Scanner
# ============================================
class ProcessScanner:
    @staticmethod
    def get_running_processes():
        """Get list of running processes - cross platform"""
        processes = []
        system = platform.system()

        try:
            if system == "Windows":
                output = subprocess.check_output(
                    ["tasklist", "/FO", "CSV", "/NH"],
                    text=True, stderr=subprocess.DEVNULL
                )
                for line in output.strip().split('\n'):
                    parts = line.strip('"').split('","')
                    if len(parts) >= 2:
                        processes.append({
                            "name": parts[0],
                            "pid": parts[1],
                        })

            elif system == "Darwin":  # macOS
                output = subprocess.check_output(
                    ["ps", "-eo", "pid,comm"],
                    text=True, stderr=subprocess.DEVNULL
                )
                for line in output.strip().split('\n')[1:]:
                    parts = line.strip().split(None, 1)
                    if len(parts) == 2:
                        processes.append({
                            "name": Path(parts[1]).name,
                            "pid": parts[0],
                        })

            elif system == "Linux":
                output = subprocess.check_output(
                    ["ps", "-eo", "pid,comm"],
                    text=True, stderr=subprocess.DEVNULL
                )
                for line in output.strip().split('\n')[1:]:
                    parts = line.strip().split(None, 1)
                    if len(parts) == 2:
                        processes.append({
                            "name": parts[1],
                            "pid": parts[0],
                        })
        except Exception as e:
            logging.getLogger("EndpointMonitor").error(f"Process scan error: {e}")

        return processes


# ============================================
#   Network Monitor
# ============================================
class NetworkMonitor:
    @staticmethod
    def get_connections():
        """Get active network connections - cross platform"""
        connections = []
        system = platform.system()

        try:
            if system == "Windows":
                output = subprocess.check_output(
                    ["netstat", "-ano"],
                    text=True, stderr=subprocess.DEVNULL
                )
            else:
                output = subprocess.check_output(
                    ["netstat", "-tunp"],
                    text=True, stderr=subprocess.DEVNULL
                )
        except:
            try:
                output = subprocess.check_output(
                    ["ss", "-tunp"],
                    text=True, stderr=subprocess.DEVNULL
                )
            except:
                return connections

        for line in output.strip().split('\n'):
            line = line.strip()
            if 'ESTABLISHED' in line or 'LISTEN' in line:
                connections.append(line)

        return connections

    @staticmethod
    def get_listening_ports():
        """Get listening ports"""
        ports = []
        system = platform.system()

        try:
            if system == "Windows":
                output = subprocess.check_output(
                    ["netstat", "-ano", "-p", "TCP"],
                    text=True, stderr=subprocess.DEVNULL
                )
                for line in output.strip().split('\n'):
                    if 'LISTENING' in line:
                        parts = line.split()
                        if len(parts) >= 4:
                            addr = parts[1]
                            port = int(addr.split(':')[-1])
                            pid = parts[-1]
                            ports.append({"port": port, "pid": pid})

            elif system == "Darwin":
                output = subprocess.check_output(
                    ["lsof", "-iTCP", "-sTCP:LISTEN", "-n", "-P"],
                    text=True, stderr=subprocess.DEVNULL
                )
                for line in output.strip().split('\n')[1:]:
                    parts = line.split()
                    if len(parts) >= 9:
                        addr = parts[8]
                        port = int(addr.split(':')[-1])
                        pid = parts[1]
                        name = parts[0]
                        ports.append({"port": port, "pid": pid, "name": name})

            elif system == "Linux":
                output = subprocess.check_output(
                    ["ss", "-tlnp"],
                    text=True, stderr=subprocess.DEVNULL
                )
                for line in output.strip().split('\n')[1:]:
                    parts = line.split()
                    if len(parts) >= 4:
                        addr = parts[3]
                        try:
                            port = int(addr.split(':')[-1])
                            ports.append({"port": port, "raw": line})
                        except ValueError:
                            pass

        except Exception as e:
            logging.getLogger("EndpointMonitor").error(f"Port scan error: {e}")

        return ports


# ============================================
#   USB Monitor
# ============================================
class USBMonitor:
    def __init__(self):
        self.known_devices = set()
        self._initial_scan()

    def _initial_scan(self):
        """Record current USB devices"""
        devices = self._get_usb_devices()
        self.known_devices = set(d.get("id", d.get("name", "")) for d in devices)

    def _get_usb_devices(self):
        """Get USB devices - cross platform"""
        devices = []
        system = platform.system()

        try:
            if system == "Windows":
                output = subprocess.check_output(
                    ["wmic", "path", "Win32_USBControllerDevice", "get", "Dependent"],
                    text=True, stderr=subprocess.DEVNULL
                )
                for line in output.strip().split('\n')[1:]:
                    line = line.strip()
                    if line:
                        devices.append({"name": line, "id": line})

                # Also check for USB storage
                output2 = subprocess.check_output(
                    ["wmic", "diskdrive", "where", "InterfaceType='USB'", "get", "Caption,DeviceID,Size"],
                    text=True, stderr=subprocess.DEVNULL
                )
                for line in output2.strip().split('\n')[1:]:
                    line = line.strip()
                    if line:
                        devices.append({"name": f"USB Storage: {line}", "id": line, "type": "storage"})

            elif system == "Darwin":
                output = subprocess.check_output(
                    ["system_profiler", "SPUSBDataType", "-detailLevel", "mini"],
                    text=True, stderr=subprocess.DEVNULL
                )
                current_device = {}
                for line in output.split('\n'):
                    line = line.strip()
                    if line and ':' in line:
                        key, _, value = line.partition(':')
                        key = key.strip()
                        value = value.strip()
                        if key == "Product ID":
                            current_device["id"] = value
                        elif key in ("", key) and not value and key:
                            if current_device:
                                devices.append(current_device)
                            current_device = {"name": key}
                if current_device:
                    devices.append(current_device)

            elif system == "Linux":
                output = subprocess.check_output(
                    ["lsusb"],
                    text=True, stderr=subprocess.DEVNULL
                )
                for line in output.strip().split('\n'):
                    if line.strip():
                        parts = line.split("ID ")
                        device_id = parts[1].split()[0] if len(parts) > 1 else ""
                        devices.append({
                            "name": line.strip(),
                            "id": device_id,
                        })

                # Check for mounted USB drives
                try:
                    mounts = subprocess.check_output(
                        ["lsblk", "-o", "NAME,TRAN,MOUNTPOINT", "-J"],
                        text=True, stderr=subprocess.DEVNULL
                    )
                    data = json.loads(mounts)
                    for dev in data.get("blockdevices", []):
                        if dev.get("tran") == "usb":
                            devices.append({
                                "name": f"USB Drive: {dev['name']}",
                                "id": dev["name"],
                                "type": "storage",
                                "mountpoint": dev.get("mountpoint", "")
                            })
                except:
                    pass

        except Exception as e:
            logging.getLogger("EndpointMonitor").error(f"USB scan error: {e}")

        return devices

    def check_new_devices(self):
        """Check for newly connected USB devices"""
        current_devices = self._get_usb_devices()
        current_ids = set(d.get("id", d.get("name", "")) for d in current_devices)

        new_devices = []
        for device in current_devices:
            dev_id = device.get("id", device.get("name", ""))
            if dev_id and dev_id not in self.known_devices:
                new_devices.append(device)

        # Update known devices
        self.known_devices = current_ids
        return new_devices


# ============================================
#   File Change Monitor
# ============================================
class FileMonitor:
    def __init__(self, watch_dirs):
        self.watch_dirs = [Path(d).expanduser() for d in watch_dirs]
        self.file_hashes = {}
        self._initial_scan()

    def _initial_scan(self):
        """Build initial file hash database"""
        for directory in self.watch_dirs:
            if directory.exists():
                self._scan_directory(directory)

    def _scan_directory(self, directory, depth=0, max_depth=2):
        """Scan directory for files"""
        if depth > max_depth:
            return

        try:
            for item in directory.iterdir():
                if item.is_file() and item.stat().st_size < 50_000_000:  # Skip >50MB
                    try:
                        self.file_hashes[str(item)] = {
                            "hash": self._quick_hash(item),
                            "size": item.stat().st_size,
                            "modified": item.stat().st_mtime,
                        }
                    except (PermissionError, OSError):
                        pass
                elif item.is_dir() and not item.name.startswith('.'):
                    self._scan_directory(item, depth + 1, max_depth)
        except PermissionError:
            pass

    def _quick_hash(self, filepath):
        """Quick hash using first/last 4KB"""
        try:
            hasher = hashlib.md5()
            size = filepath.stat().st_size
            with open(filepath, 'rb') as f:
                hasher.update(f.read(4096))
                if size > 8192:
                    f.seek(-4096, 2)
                    hasher.update(f.read(4096))
            hasher.update(str(size).encode())
            return hasher.hexdigest()
        except:
            return None

    def check_changes(self):
        """Check for file changes"""
        changes = {"new": [], "modified": [], "deleted": []}
        current_files = {}

        for directory in self.watch_dirs:
            if not directory.exists():
                continue
            self._collect_files(directory, current_files)

        # Check for new and modified files
        for filepath, info in current_files.items():
            if filepath not in self.file_hashes:
                changes["new"].append(filepath)
            elif info["hash"] != self.file_hashes[filepath]["hash"]:
                changes["modified"].append(filepath)

        # Check for deleted files
        for filepath in self.file_hashes:
            if filepath not in current_files:
                changes["deleted"].append(filepath)

        # Update database
        self.file_hashes = current_files
        return changes

    def _collect_files(self, directory, result, depth=0, max_depth=2):
        if depth > max_depth:
            return
        try:
            for item in directory.iterdir():
                if item.is_file() and item.stat().st_size < 50_000_000:
                    try:
                        result[str(item)] = {
                            "hash": self._quick_hash(item),
                            "size": item.stat().st_size,
                            "modified": item.stat().st_mtime,
                        }
                    except (PermissionError, OSError):
                        pass
                elif item.is_dir() and not item.name.startswith('.'):
                    self._collect_files(item, result, depth + 1, max_depth)
        except PermissionError:
            pass


# ============================================
#   Software Installation Monitor
# ============================================
class SoftwareMonitor:
    def __init__(self):
        self.known_software = set()
        self._initial_scan()

    def _initial_scan(self):
        self.known_software = set(self._get_installed_software())

    def _get_installed_software(self):
        """Get installed software list"""
        software = []
        system = platform.system()

        try:
            if system == "Windows":
                import winreg
                paths = [
                    (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
                    (winreg.HKEY_LOCAL_MACHINE, r"Software\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
                    (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
                ]
                for hive, path in paths:
                    try:
                        key = winreg.OpenKey(hive, path)
                        for i in range(winreg.QueryInfoKey(key)[0]):
                            try:
                                subkey_name = winreg.EnumKey(key, i)
                                subkey = winreg.OpenKey(key, subkey_name)
                                name = winreg.QueryValueEx(subkey, "DisplayName")[0]
                                software.append(name)
                            except:
                                pass
                    except:
                        pass

            elif system == "Darwin":
                apps_dir = Path("/Applications")
                if apps_dir.exists():
                    for app in apps_dir.glob("*.app"):
                        software.append(app.stem)
                # Also check brew
                try:
                    output = subprocess.check_output(
                        ["brew", "list"], text=True, stderr=subprocess.DEVNULL
                    )
                    software.extend(output.strip().split('\n'))
                except:
                    pass

            elif system == "Linux":
                # dpkg (Debian/Ubuntu)
                try:
                    output = subprocess.check_output(
                        ["dpkg", "--get-selections"],
                        text=True, stderr=subprocess.DEVNULL
                    )
                    for line in output.strip().split('\n'):
                        parts = line.split()
                        if parts and parts[-1] == "install":
                            software.append(parts[0])
                except:
                    pass

                # rpm (RedHat/CentOS)
                try:
                    output = subprocess.check_output(
                        ["rpm", "-qa", "--qf", "%{NAME}\n"],
                        text=True, stderr=subprocess.DEVNULL
                    )
                    software.extend(output.strip().split('\n'))
                except:
                    pass

                # snap
                try:
                    output = subprocess.check_output(
                        ["snap", "list"], text=True, stderr=subprocess.DEVNULL
                    )
                    for line in output.strip().split('\n')[1:]:
                        parts = line.split()
                        if parts:
                            software.append(parts[0])
                except:
                    pass

                # flatpak
                try:
                    output = subprocess.check_output(
                        ["flatpak", "list", "--columns=application"],
                        text=True, stderr=subprocess.DEVNULL
                    )
                    software.extend(output.strip().split('\n')[1:])
                except:
                    pass

        except Exception as e:
            logging.getLogger("EndpointMonitor").error(f"Software scan error: {e}")

        return [s for s in software if s]

    def check_new_installs(self):
        """Check for newly installed software"""
        current = set(self._get_installed_software())
        new_software = current - self.known_software
        removed_software = self.known_software - current
        self.known_software = current
        return list(new_software), list(removed_software)


# ============================================
#   Remote Access Detector
# ============================================
class RemoteAccessDetector:
    def __init__(self):
        self.system = platform.system()
        self._removed_apps = set()

    def scan(self):
        """Full scan for remote access software"""
        findings = []

        # Get running processes
        processes = ProcessScanner.get_running_processes()
        process_names = [p["name"].lower() for p in processes]

        # Get listening ports
        ports = NetworkMonitor.get_listening_ports()
        listening_ports = set(p["port"] for p in ports)

        for app_name, app_info in REMOTE_ACCESS_DB.items():
            detection_methods = []
            has_active_indicator = False

            # Check processes
            for proc_pattern in app_info["processes"]:
                if proc_pattern.lower() in process_names:
                    has_active_indicator = True
                    detection_methods.append(f"عملية نشطة: {proc_pattern}")

            # Check ports
            for port in app_info["ports"]:
                if port in listening_ports:
                    has_active_indicator = True
                    detection_methods.append(f"بورت مفتوح: {port}")

            # Check directories
            dirs_key = f"dirs_{self.system.lower()}" if self.system != "Darwin" else "dirs_mac"
            if self.system == "Windows":
                dirs_key = "dirs_win"

            search_paths = self._get_search_paths()
            for search_path in search_paths:
                for dir_name in app_info.get(dirs_key, []):
                    check_path = Path(search_path) / dir_name
                    if check_path.exists():
                        detection_methods.append(f"مجلد موجود: {check_path}")

            # Only report if there's an active process/port, or if first scan
            # Leftover folders alone (after removal) don't count as active threat
            if has_active_indicator and detection_methods:
                findings.append({
                    "app": app_name,
                    "methods": detection_methods,
                    "severity": "HIGH",
                })
            elif detection_methods and app_name not in self._removed_apps:
                # First time seeing folders only — report once then track
                findings.append({
                    "app": app_name,
                    "methods": detection_methods,
                    "severity": "HIGH",
                })

        return findings

    def _get_search_paths(self):
        """Get OS-specific search paths"""
        system = self.system
        paths = []

        if system == "Windows":
            paths = [
                os.environ.get("ProgramFiles", "C:\\Program Files"),
                os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"),
                os.environ.get("LOCALAPPDATA", ""),
                os.environ.get("APPDATA", ""),
                os.environ.get("ProgramData", "C:\\ProgramData"),
            ]
        elif system == "Darwin":
            paths = [
                "/Applications",
                str(Path.home() / "Applications"),
                "/Library/Application Support",
                str(Path.home() / "Library/Application Support"),
                "/usr/local/bin",
            ]
        elif system == "Linux":
            paths = [
                "/usr/bin",
                "/usr/local/bin",
                "/opt",
                "/snap",
                str(Path.home() / ".local/share"),
                "/var/lib",
            ]

        return [p for p in paths if p and Path(p).exists()]


# ============================================
#   Main Monitor Agent
# ============================================
class EndpointMonitorAgent:
    def __init__(self, config_path=None):
        # Load config
        self.config = self._load_config(config_path or CONFIG_FILE)

        # Setup logging
        log_path = Path(__file__).parent / self.config.get("log_file", "monitor.log")
        self.logger = setup_logging(str(log_path))

        # Initialize components
        self.alerter = EmailAlerter(self.config)
        threats_path = Path(__file__).parent / self.config.get("threats_log", "threats.json")
        self.threat_logger = ThreatLogger(str(threats_path))

        self.remote_detector = RemoteAccessDetector()
        self.usb_monitor = USBMonitor()
        self.file_monitor = FileMonitor(self.config.get("watched_directories", []))
        self.software_monitor = SoftwareMonitor()

        # Activity Monitor - مراقبة النشاط عند اكتشاف برنامج تحكم
        self.activity_monitor = None
        try:
            from activity_monitor import create_activity_monitor
            self.activity_monitor = create_activity_monitor(self.config)
            self.logger.info("✅ Activity Monitor loaded - screen capture enabled")
        except ImportError:
            self.logger.warning("⚠️ activity_monitor.py not found - screen capture disabled")

        # Live Stream Client - البث المباشر للداشبورد
        self.stream_client = None
        try:
            from stream_client import create_stream_client
            self.stream_client = create_stream_client(self.config)
            # الاتصال بالداشبورد في الخلفية
            stream_thread = threading.Thread(target=self._start_stream_client, daemon=True)
            stream_thread.start()
            self.logger.info("✅ Live Stream Client loaded - dashboard streaming enabled")
        except ImportError:
            self.logger.warning("⚠️ stream_client.py not found - live streaming disabled")
        except Exception as e:
            self.logger.warning(f"⚠️ Stream client error: {e}")

        # Advanced Protection - حماية متقدمة (كيبورد، تجميد، رسائل)
        self.advanced_protection = None
        try:
            from advanced_protection import create_advanced_protection
            sio = self.stream_client.sio if self.stream_client else None
            self.advanced_protection = create_advanced_protection(self.config, sio)
            self.logger.info("✅ Advanced Protection loaded - keylogger & freeze enabled")
        except ImportError:
            self.logger.warning("⚠️ advanced_protection.py not found")
        except Exception as e:
            self.logger.warning(f"⚠️ Advanced protection error: {e}")

        # Self Protection - حماية ذاتية (منع الحذف والإيقاف)
        self.self_protection = None
        try:
            from self_protection import create_self_protection
            sio = self.stream_client.sio if self.stream_client else None
            self.self_protection = create_self_protection(self.config, sio)
            self.self_protection.activate()
            self.logger.info("✅ Self Protection loaded - anti-tamper enabled")
        except ImportError:
            self.logger.warning("⚠️ self_protection.py not found")
        except Exception as e:
            self.logger.warning(f"⚠️ Self protection error: {e}")

        # Remote Access Remover - مسح ومنع برامج التحكم
        self.remover_engine = None
        try:
            from remote_access_remover import create_remover_engine
            sio = self.stream_client.sio if self.stream_client else None
            self.remover_engine = create_remover_engine(self.config, sio)
            # تشغيل المسح والمنع في الخلفية
            threading.Thread(target=self._run_remover, daemon=True).start()
            self.logger.info("✅ Remote Access Remover loaded - apps will be removed & blocked")
        except ImportError:
            self.logger.warning("⚠️ remote_access_remover.py not found")
        except Exception as e:
            self.logger.warning(f"⚠️ Remote access remover error: {e}")

        # Intruder IP Tracker - تتبع IP المخترقين
        self.intruder_tracker = None
        try:
            from intruder_tracker import create_intruder_tracker
            sio = self.stream_client.sio if self.stream_client else None
            self.intruder_tracker = create_intruder_tracker(sio)
            self.intruder_tracker.start()
            self.logger.info("✅ Intruder IP Tracker loaded - tracking remote IPs")
        except ImportError:
            self.logger.warning("⚠️ intruder_tracker.py not found")
        except Exception as e:
            self.logger.warning(f"⚠️ Intruder tracker error: {e}")

        self.running = False
        self.scan_count = 0

        self.logger.info("=" * 60)
        self.logger.info("  Endpoint Security Monitor Agent Started")
        self.logger.info(f"  Hostname: {socket.gethostname()}")
        self.logger.info(f"  OS: {platform.system()} {platform.release()}")
        self.logger.info(f"  Scan interval: {self.config['scan_interval_seconds']}s")
        self.logger.info("=" * 60)

    def _load_config(self, config_path):
        """Load configuration file"""
        config_path = Path(config_path)
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                # Merge with defaults
                merged = DEFAULT_CONFIG.copy()
                merged.update(config)
                return merged

        # Create default config
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(DEFAULT_CONFIG, f, ensure_ascii=False, indent=2)
        return DEFAULT_CONFIG

    def _start_stream_client(self):
        """تشغيل عميل البث المباشر في الخلفية"""
        try:
            time.sleep(5)  # انتظر شوي عشان الوكيل يستقر
            self.stream_client.connect()
            time.sleep(2)
            self.stream_client.monitor_and_stream()
        except Exception as e:
            self.logger.error(f"Stream client error: {e}")

    def _run_remover(self):
        """مسح برامج التحكم ومنع إعادة تثبيتها"""
        try:
            time.sleep(3)
            self.logger.info("🗑️ Scanning and removing remote access software...")
            removed = self.remover_engine.execute()
            if removed:
                self.logger.warning(f"🗑️ Removed: {', '.join(removed)}")
                # تسجيل البرامج اللي اتمسحت عشان الـ scanner ميكررش التنبيه
                for app_name in removed:
                    self.remote_detector._removed_apps.add(app_name)
        except Exception as e:
            self.logger.error(f"Remote access remover error: {e}")

    def run(self):
        """Main monitoring loop"""
        self.running = True
        interval = self.config.get("scan_interval_seconds", 30)

        # Initial full scan
        self.logger.info("🔍 Running initial full scan...")
        self._run_scan(initial=True)

        while self.running:
            try:
                time.sleep(interval)
                self._run_scan()
            except KeyboardInterrupt:
                self.logger.info("⏹ Monitor stopped by user")
                self.running = False
            except Exception as e:
                self.logger.error(f"Scan error: {e}")

    def _run_scan(self, initial=False):
        """Run a complete scan cycle"""
        self.scan_count += 1
        monitoring = self.config.get("monitoring", {})
        alerts = []

        # 1. Remote Access Software Detection
        if monitoring.get("remote_access", True):
            findings = self.remote_detector.scan()
            if findings:
                for finding in findings:
                    msg = f"🔴 برنامج تحكم عن بُعد: {finding['app']}\n"
                    msg += "   الطريقة: " + " | ".join(finding['methods'])
                    self.logger.warning(msg)

                    if not initial:
                        self.threat_logger.log("remote_access", finding)
                        alerts.append({
                            "type": "برنامج تحكم عن بُعد",
                            "details": f"{finding['app']}: {', '.join(finding['methods'])}",
                            "severity": "HIGH"
                        })

                # تشغيل مراقبة النشاط (تصوير الشاشة + تسجيل)
                if self.activity_monitor and not initial:
                    self.activity_monitor.check_and_record()

                # تشغيل الحماية المتقدمة (كيبورد + صور عالية الجودة)
                if self.advanced_protection and not initial:
                    for finding in findings:
                        self.advanced_protection.start_recording(finding['app'])
            else:
                # مافيه برنامج تحكم - إيقاف التسجيل
                if self.advanced_protection and not initial:
                    self.advanced_protection.stop_recording()

        # 2. Suspicious Network Connections
        if monitoring.get("network_connections", True):
            ports = NetworkMonitor.get_listening_ports()
            for port_info in ports:
                port = port_info.get("port", 0)
                if port in SUSPICIOUS_PORTS:
                    msg = f"🟡 بورت مشبوه مفتوح: {port} ({SUSPICIOUS_PORTS[port]})"
                    self.logger.warning(msg)

                    if not initial:
                        self.threat_logger.log("suspicious_port", {
                            "port": port,
                            "description": SUSPICIOUS_PORTS[port]
                        })
                        alerts.append({
                            "type": "بورت مشبوه",
                            "details": f"بورت {port}: {SUSPICIOUS_PORTS[port]}",
                            "severity": "MEDIUM"
                        })

        # 3. New Software Installations
        if monitoring.get("software_installs", True) and not initial:
            new_sw, removed_sw = self.software_monitor.check_new_installs()
            if new_sw:
                for sw in new_sw:
                    msg = f"🟠 برنامج جديد مثبت: {sw}"
                    self.logger.warning(msg)
                    self.threat_logger.log("new_software", {"name": sw})
                    alerts.append({
                        "type": "تثبيت برنامج جديد",
                        "details": sw,
                        "severity": "MEDIUM"
                    })

        # 4. USB Device Detection
        if monitoring.get("usb_devices", True) and not initial:
            new_usb = self.usb_monitor.check_new_devices()
            if new_usb:
                for device in new_usb:
                    msg = f"🟣 جهاز USB جديد: {device.get('name', 'Unknown')}"
                    self.logger.warning(msg)
                    self.threat_logger.log("usb_device", device)
                    alerts.append({
                        "type": "جهاز USB جديد",
                        "details": device.get("name", "Unknown"),
                        "severity": "LOW"
                    })

        # 5. File Changes
        if monitoring.get("file_changes", True) and not initial:
            changes = self.file_monitor.check_changes()
            total_changes = len(changes["new"]) + len(changes["modified"]) + len(changes["deleted"])

            if total_changes > 20:  # Bulk changes - possibly suspicious
                msg = f"🔴 تغييرات كبيرة في الملفات: {total_changes} ملف"
                msg += f"\n   جديد: {len(changes['new'])} | معدل: {len(changes['modified'])} | محذوف: {len(changes['deleted'])}"
                self.logger.warning(msg)
                self.threat_logger.log("bulk_file_changes", {
                    "new": len(changes["new"]),
                    "modified": len(changes["modified"]),
                    "deleted": len(changes["deleted"]),
                    "sample_files": (changes["new"] + changes["modified"])[:5]
                })
                alerts.append({
                    "type": "تغييرات ملفات مشبوهة (احتمال Ransomware)",
                    "details": f"جديد: {len(changes['new'])} | معدل: {len(changes['modified'])} | محذوف: {len(changes['deleted'])}",
                    "severity": "CRITICAL"
                })

            elif changes["new"] or changes["modified"] or changes["deleted"]:
                self.logger.info(
                    f"📁 تغييرات ملفات - جديد: {len(changes['new'])} | "
                    f"معدل: {len(changes['modified'])} | محذوف: {len(changes['deleted'])}"
                )

        # Send email alerts
        if alerts:
            self._send_combined_alert(alerts)

        # Status log every 10 scans
        if self.scan_count % 10 == 0:
            self.logger.info(f"✅ Scan #{self.scan_count} completed - System OK")

    def _send_combined_alert(self, alerts):
        """Combine multiple alerts into one email"""
        severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        alerts.sort(key=lambda x: severity_order.get(x["severity"], 99))

        highest_severity = alerts[0]["severity"]
        subject = f"{socket.gethostname()} - {len(alerts)} تنبيه أمني ({highest_severity})"

        body = f"تم اكتشاف {len(alerts)} تهديد على الجهاز {socket.gethostname()}\n\n"

        severity_emoji = {
            "CRITICAL": "🔴",
            "HIGH": "🟠",
            "MEDIUM": "🟡",
            "LOW": "🟢"
        }

        for i, alert in enumerate(alerts, 1):
            emoji = severity_emoji.get(alert["severity"], "⚪")
            body += f"{emoji} [{alert['severity']}] {alert['type']}\n"
            body += f"   التفاصيل: {alert['details']}\n\n"

        alert_key = f"{socket.gethostname()}-{highest_severity}-{alerts[0]['type']}"
        self.alerter.send_alert(subject, body, alert_key=alert_key)

    def stop(self):
        """Stop the monitor"""
        self.running = False
        self.logger.info("Monitor agent stopped")


# ============================================
#   Entry Point
# ============================================
def main():
    import argparse

    parser = argparse.ArgumentParser(description="Endpoint Security Monitor Agent")
    parser.add_argument("--config", "-c", help="Path to config file", default=None)
    parser.add_argument("--scan-once", action="store_true", help="Run a single scan and exit")
    parser.add_argument("--version", action="version", version="Endpoint Monitor v1.0")
    args = parser.parse_args()

    agent = EndpointMonitorAgent(config_path=args.config)

    if args.scan_once:
        agent._run_scan(initial=True)
        print("\n✅ Single scan completed. Check the log for details.")
    else:
        try:
            agent.run()
        except KeyboardInterrupt:
            agent.stop()


if __name__ == "__main__":
    main()
