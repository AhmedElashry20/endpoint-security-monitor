#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║     Activity Monitor Module - وحدة مراقبة النشاط            ║
║     يسجل نشاط الجهاز عند اكتشاف برنامج تحكم عن بُعد        ║
║     Cross-Platform: Windows / macOS / Linux                  ║
╚══════════════════════════════════════════════════════════════╝

عند اكتشاف أي برنامج تحكم عن بُعد:
- يلتقط صور للشاشة كل فترة
- يسجل البرامج المفتوحة والنوافذ النشطة
- يسجل الملفات اللي يتم الوصول لها
- يسجل اتصالات الشبكة
- يرسل كل شي على الإيميل كتقرير مع الصور
"""

import os
import sys
import time
import json
import socket
import base64
import shutil
import platform
import subprocess
import threading
import logging
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

# ============================================
#   Configuration
# ============================================
CAPTURE_INTERVAL = 10          # التقاط صورة كل 10 ثواني
ACTIVITY_LOG_INTERVAL = 5      # تسجيل النشاط كل 5 ثواني
MAX_SCREENSHOTS = 50           # أقصى عدد صور محفوظة
MAX_CAPTURE_DURATION = 600     # أقصى مدة تسجيل = 10 دقائق
EVIDENCE_DIR = Path(__file__).parent / "evidence"
LOG_FILE = Path(__file__).parent / "activity_monitor.log"

# إعداد السجل
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(str(LOG_FILE), encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("ActivityMonitor")

# قائمة البرامج المراقبة
REMOTE_ACCESS_PROCESSES = {
    "anydesk": "AnyDesk",
    "teamviewer": "TeamViewer",
    "teamviewer_service": "TeamViewer",
    "rustdesk": "RustDesk",
    "remoting_host": "Chrome Remote Desktop",
    "chrome_remote_desktop": "Chrome Remote Desktop",
    "splashtopstreamer": "Splashtop",
    "parsecd": "Parsec",
    "logmein": "LogMeIn",
    "lmiguardiansvc": "LogMeIn",
    "vncserver": "VNC",
    "vncviewer": "VNC",
    "winvnc": "VNC",
    "x11vnc": "VNC",
    "radmin": "Radmin",
    "rserver3": "Radmin",
    "supremo": "Supremo",
    "supremoservice": "Supremo",
    "aa_v3": "Ammyy Admin",
    "ammyy": "Ammyy Admin",
    "meshagent": "MeshCentral",
    "dwagent": "DWService",
    "nxd": "NoMachine",
    "nxserver": "NoMachine",
    "remotepc": "RemotePC",
    "screenconnect": "ScreenConnect",
    "connectwisecontrol": "ConnectWise",
    "zohoassist": "Zoho Assist",
    "zohomeeting": "Zoho Assist",
    "client32": "NetSupport",
    "rfusclient": "Remote Utilities",
    "rutserv": "Remote Utilities",
}


# ============================================
#   Screenshot Capture (Cross-Platform)
# ============================================
class ScreenCapture:
    """التقاط صور الشاشة"""

    def __init__(self, save_dir):
        self.save_dir = Path(save_dir)
        self.save_dir.mkdir(parents=True, exist_ok=True)
        self.system = platform.system()
        self._check_dependencies()

    def _check_dependencies(self):
        """التحقق من المكتبات المطلوبة"""
        self.capture_method = None

        # المحاولة 1: Pillow (ImageGrab)
        try:
            from PIL import ImageGrab
            self.capture_method = "pillow"
            logger.info("Screenshot method: Pillow (ImageGrab)")
            return
        except ImportError:
            pass

        # المحاولة 2: mss
        try:
            import mss
            self.capture_method = "mss"
            logger.info("Screenshot method: mss")
            return
        except ImportError:
            pass

        # المحاولة 3: أدوات النظام
        if self.system == "Windows":
            self.capture_method = "native_win"
            logger.info("Screenshot method: Windows native (PowerShell)")
        elif self.system == "Darwin":
            self.capture_method = "native_mac"
            logger.info("Screenshot method: macOS screencapture")
        elif self.system == "Linux":
            # التحقق من الأدوات المتاحة
            for tool in ["scrot", "gnome-screenshot", "import", "xdotool"]:
                if shutil.which(tool):
                    self.capture_method = f"native_linux_{tool}"
                    logger.info(f"Screenshot method: Linux ({tool})")
                    return

            self.capture_method = "none"
            logger.warning("No screenshot tool found! Install: pip install Pillow or pip install mss")

    def capture(self, filename=None):
        """التقاط صورة للشاشة"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"screenshot_{timestamp}.png"

        filepath = self.save_dir / filename

        try:
            if self.capture_method == "pillow":
                return self._capture_pillow(filepath)
            elif self.capture_method == "mss":
                return self._capture_mss(filepath)
            elif self.capture_method == "native_win":
                return self._capture_windows(filepath)
            elif self.capture_method == "native_mac":
                return self._capture_mac(filepath)
            elif self.capture_method and self.capture_method.startswith("native_linux"):
                return self._capture_linux(filepath)
            else:
                logger.error("No screenshot method available")
                return None
        except Exception as e:
            logger.error(f"Screenshot error: {e}")
            return None

    def _capture_pillow(self, filepath):
        from PIL import ImageGrab
        img = ImageGrab.grab()
        img.save(str(filepath), "PNG", quality=60)
        return filepath

    def _capture_mss(self, filepath):
        import mss
        with mss.mss() as sct:
            sct.shot(output=str(filepath))
        return filepath

    def _capture_windows(self, filepath):
        """التقاط باستخدام PowerShell"""
        ps_script = f"""
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$screen = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$bitmap = New-Object System.Drawing.Bitmap($screen.Width, $screen.Height)
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.CopyFromScreen($screen.Location, [System.Drawing.Point]::Empty, $screen.Size)
$bitmap.Save('{filepath}', [System.Drawing.Imaging.ImageFormat]::Png)
$graphics.Dispose()
$bitmap.Dispose()
"""
        subprocess.run(
            ["powershell", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
            capture_output=True, timeout=10
        )
        if filepath.exists():
            return filepath
        return None

    def _capture_mac(self, filepath):
        subprocess.run(
            ["screencapture", "-x", str(filepath)],
            capture_output=True, timeout=10
        )
        if filepath.exists():
            return filepath
        return None

    def _capture_linux(self, filepath):
        tool = self.capture_method.replace("native_linux_", "")
        if tool == "scrot":
            subprocess.run(["scrot", str(filepath)], capture_output=True, timeout=10)
        elif tool == "gnome-screenshot":
            subprocess.run(["gnome-screenshot", "-f", str(filepath)], capture_output=True, timeout=10)
        elif tool == "import":
            subprocess.run(["import", "-window", "root", str(filepath)], capture_output=True, timeout=10)

        if filepath.exists():
            return filepath
        return None

    def cleanup_old(self, keep=MAX_SCREENSHOTS):
        """حذف الصور القديمة"""
        files = sorted(self.save_dir.glob("screenshot_*.png"), key=lambda f: f.stat().st_mtime)
        if len(files) > keep:
            for f in files[:len(files) - keep]:
                f.unlink()


# ============================================
#   Active Window Tracker
# ============================================
class WindowTracker:
    """تتبع النافذة النشطة"""

    def __init__(self):
        self.system = platform.system()

    def get_active_window(self):
        """الحصول على عنوان النافذة النشطة"""
        try:
            if self.system == "Windows":
                return self._get_windows_active()
            elif self.system == "Darwin":
                return self._get_mac_active()
            elif self.system == "Linux":
                return self._get_linux_active()
        except Exception as e:
            return {"title": "Unknown", "process": "Unknown", "error": str(e)}

    def _get_windows_active(self):
        try:
            ps_cmd = """
$FG = Add-Type -MemberDefinition '
    [DllImport("user32.dll")]
    public static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")]
    public static extern int GetWindowText(IntPtr hWnd, System.Text.StringBuilder text, int count);
    [DllImport("user32.dll")]
    public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint lpdwProcessId);
' -Name 'Win32' -Namespace 'Native' -PassThru

$hwnd = [Native.Win32]::GetForegroundWindow()
$sb = New-Object System.Text.StringBuilder(256)
[Native.Win32]::GetWindowText($hwnd, $sb, 256) | Out-Null
$title = $sb.ToString()

$pid = 0
[Native.Win32]::GetWindowThreadProcessId($hwnd, [ref]$pid) | Out-Null
$proc = Get-Process -Id $pid -ErrorAction SilentlyContinue

@{Title=$title; Process=$proc.ProcessName; PID=$pid} | ConvertTo-Json
"""
            result = subprocess.run(
                ["powershell", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd],
                capture_output=True, text=True, timeout=5
            )
            if result.stdout.strip():
                data = json.loads(result.stdout.strip())
                return {
                    "title": data.get("Title", ""),
                    "process": data.get("Process", ""),
                    "pid": data.get("PID", 0)
                }
        except:
            pass
        return {"title": "Unknown", "process": "Unknown"}

    def _get_mac_active(self):
        try:
            script = '''
            tell application "System Events"
                set frontApp to name of first application process whose frontmost is true
                set frontWindow to ""
                try
                    tell process frontApp
                        set frontWindow to name of front window
                    end tell
                end try
            end tell
            return frontApp & "|" & frontWindow
            '''
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True, text=True, timeout=5
            )
            if result.stdout.strip():
                parts = result.stdout.strip().split("|", 1)
                return {
                    "process": parts[0] if parts else "Unknown",
                    "title": parts[1] if len(parts) > 1 else ""
                }
        except:
            pass
        return {"title": "Unknown", "process": "Unknown"}

    def _get_linux_active(self):
        try:
            # xdotool
            result = subprocess.run(
                ["xdotool", "getactivewindow", "getwindowname"],
                capture_output=True, text=True, timeout=5
            )
            title = result.stdout.strip() if result.returncode == 0 else "Unknown"

            # Get PID
            result2 = subprocess.run(
                ["xdotool", "getactivewindow", "getwindowpid"],
                capture_output=True, text=True, timeout=5
            )
            pid = result2.stdout.strip() if result2.returncode == 0 else ""

            proc_name = ""
            if pid:
                try:
                    result3 = subprocess.run(
                        ["ps", "-p", pid, "-o", "comm="],
                        capture_output=True, text=True, timeout=5
                    )
                    proc_name = result3.stdout.strip()
                except:
                    pass

            return {"title": title, "process": proc_name, "pid": pid}
        except:
            pass
        return {"title": "Unknown", "process": "Unknown"}


# ============================================
#   Process Monitor
# ============================================
class ProcessMonitor:
    """مراقبة العمليات الجارية"""

    def __init__(self):
        self.system = platform.system()

    def get_all_processes(self):
        """الحصول على جميع العمليات"""
        processes = []
        try:
            if self.system == "Windows":
                output = subprocess.check_output(
                    ["tasklist", "/FO", "CSV", "/V", "/NH"],
                    text=True, stderr=subprocess.DEVNULL, timeout=10
                )
                for line in output.strip().split('\n'):
                    parts = line.strip('"').split('","')
                    if len(parts) >= 8:
                        processes.append({
                            "name": parts[0],
                            "pid": parts[1],
                            "memory": parts[4],
                            "status": parts[5] if len(parts) > 5 else "",
                            "title": parts[-1] if len(parts) > 8 else ""
                        })
            else:
                output = subprocess.check_output(
                    ["ps", "-eo", "pid,comm,%cpu,%mem,etime"],
                    text=True, stderr=subprocess.DEVNULL, timeout=10
                )
                for line in output.strip().split('\n')[1:]:
                    parts = line.split(None, 4)
                    if len(parts) >= 4:
                        processes.append({
                            "pid": parts[0],
                            "name": parts[1],
                            "cpu": parts[2],
                            "memory": parts[3],
                            "uptime": parts[4] if len(parts) > 4 else ""
                        })
        except Exception as e:
            logger.error(f"Process list error: {e}")

        return processes

    def find_remote_access(self):
        """البحث عن برامج التحكم عن بُعد"""
        processes = self.get_all_processes()
        found = []

        for proc in processes:
            proc_name = proc["name"].lower().replace(".exe", "")
            if proc_name in REMOTE_ACCESS_PROCESSES:
                proc["app_name"] = REMOTE_ACCESS_PROCESSES[proc_name]
                found.append(proc)

        return found


# ============================================
#   Network Connection Logger
# ============================================
class NetworkLogger:
    """تسجيل اتصالات الشبكة"""

    def __init__(self):
        self.system = platform.system()

    def get_connections(self):
        """الحصول على الاتصالات النشطة"""
        connections = []
        try:
            if self.system == "Windows":
                output = subprocess.check_output(
                    ["netstat", "-ano", "-p", "TCP"],
                    text=True, stderr=subprocess.DEVNULL, timeout=10
                )
                for line in output.strip().split('\n'):
                    if 'ESTABLISHED' in line:
                        parts = line.split()
                        if len(parts) >= 5:
                            local = parts[1]
                            remote = parts[2]
                            pid = parts[4]
                            try:
                                proc = subprocess.check_output(
                                    ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                                    text=True, stderr=subprocess.DEVNULL, timeout=5
                                ).strip().strip('"').split('","')[0]
                            except:
                                proc = "Unknown"

                            connections.append({
                                "local": local,
                                "remote": remote,
                                "pid": pid,
                                "process": proc,
                                "state": "ESTABLISHED"
                            })
            else:
                try:
                    output = subprocess.check_output(
                        ["ss", "-tunp"],
                        text=True, stderr=subprocess.DEVNULL, timeout=10
                    )
                except:
                    output = subprocess.check_output(
                        ["netstat", "-tunp"],
                        text=True, stderr=subprocess.DEVNULL, timeout=10
                    )

                for line in output.strip().split('\n'):
                    if 'ESTAB' in line:
                        connections.append({"raw": line.strip()})

        except Exception as e:
            logger.error(f"Network scan error: {e}")

        return connections


# ============================================
#   File Access Logger
# ============================================
class FileAccessLogger:
    """مراقبة الملفات اللي يتم الوصول لها"""

    def __init__(self):
        self.system = platform.system()
        self.last_check = datetime.now()

    def get_recent_files(self, minutes=5):
        """الملفات اللي تم الوصول لها مؤخراً"""
        files = []
        try:
            if self.system == "Windows":
                ps_cmd = f"""
$cutoff = (Get-Date).AddMinutes(-{minutes})
$paths = @(
    [Environment]::GetFolderPath('Desktop'),
    [Environment]::GetFolderPath('MyDocuments'),
    "$env:USERPROFILE\\Downloads"
)
foreach ($p in $paths) {{
    Get-ChildItem -Path $p -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object {{ $_.LastAccessTime -gt $cutoff }} |
        Select-Object FullName, LastAccessTime, Length |
        ForEach-Object {{ "$($_.FullName)|$($_.LastAccessTime)|$($_.Length)" }}
}}
"""
                result = subprocess.run(
                    ["powershell", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd],
                    capture_output=True, text=True, timeout=30
                )
                for line in result.stdout.strip().split('\n'):
                    if '|' in line:
                        parts = line.split('|', 2)
                        files.append({
                            "path": parts[0],
                            "accessed": parts[1] if len(parts) > 1 else "",
                            "size": parts[2] if len(parts) > 2 else ""
                        })

            else:
                # macOS / Linux
                search_dirs = [
                    str(Path.home() / "Desktop"),
                    str(Path.home() / "Documents"),
                    str(Path.home() / "Downloads")
                ]
                for d in search_dirs:
                    if Path(d).exists():
                        try:
                            result = subprocess.run(
                                ["find", d, "-maxdepth", "2", "-type", "f",
                                 "-amin", f"-{minutes}", "-printf", "%p|%A@|%s\n"],
                                capture_output=True, text=True, timeout=15
                            )
                            for line in result.stdout.strip().split('\n'):
                                if '|' in line:
                                    parts = line.split('|', 2)
                                    files.append({
                                        "path": parts[0],
                                        "accessed": parts[1] if len(parts) > 1 else "",
                                        "size": parts[2] if len(parts) > 2 else ""
                                    })
                        except:
                            pass

        except Exception as e:
            logger.error(f"File access scan error: {e}")

        return files


# ============================================
#   Clipboard Monitor
# ============================================
class ClipboardMonitor:
    """مراقبة الحافظة (Clipboard)"""

    def __init__(self):
        self.system = platform.system()
        self.last_content = ""

    def get_clipboard(self):
        """قراءة محتوى الحافظة"""
        try:
            if self.system == "Windows":
                result = subprocess.run(
                    ["powershell", "-Command", "Get-Clipboard"],
                    capture_output=True, text=True, timeout=5
                )
                return result.stdout.strip()

            elif self.system == "Darwin":
                result = subprocess.run(
                    ["pbpaste"],
                    capture_output=True, text=True, timeout=5
                )
                return result.stdout.strip()

            elif self.system == "Linux":
                result = subprocess.run(
                    ["xclip", "-selection", "clipboard", "-o"],
                    capture_output=True, text=True, timeout=5
                )
                return result.stdout.strip()
        except:
            pass
        return ""

    def check_change(self):
        """التحقق من تغيير الحافظة"""
        current = self.get_clipboard()
        if current and current != self.last_content:
            old = self.last_content
            self.last_content = current
            return {"old": old[:200], "new": current[:200]}
        return None


# ============================================
#   Email Reporter with Screenshots
# ============================================
class EvidenceReporter:
    """إرسال تقرير بالإيميل مع الصور"""

    def __init__(self, config):
        self.config = config

    def send_evidence_report(self, detected_app, activity_log, screenshots, network_log, file_log, clipboard_log):
        """إرسال تقرير كامل"""
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            from email.mime.image import MIMEImage
            from email.mime.base import MIMEBase
            from email import encoders

            email_cfg = self.config.get("email", {})
            if not email_cfg.get("enabled"):
                return False

            msg = MIMEMultipart("mixed")
            msg["Subject"] = f"🚨 نشاط مشبوه: {detected_app} على {socket.gethostname()}"
            msg["From"] = email_cfg["sender_email"]
            msg["To"] = ", ".join(email_cfg["recipient_emails"])

            # إنشاء التقرير HTML
            html = self._build_html_report(
                detected_app, activity_log, network_log, file_log, clipboard_log, len(screenshots)
            )
            msg.attach(MIMEText(html, "html", "utf-8"))

            # إرفاق الصور (أول 10 صور)
            for i, screenshot_path in enumerate(screenshots[:10]):
                try:
                    with open(screenshot_path, "rb") as f:
                        img_data = f.read()
                    img = MIMEImage(img_data, name=f"screenshot_{i+1}.png")
                    img.add_header('Content-Disposition', 'attachment', filename=f"screenshot_{i+1}.png")
                    msg.attach(img)
                except Exception as e:
                    logger.error(f"Error attaching screenshot: {e}")

            # إرفاق سجل النشاط كملف JSON
            activity_json = json.dumps({
                "detected_app": detected_app,
                "hostname": socket.gethostname(),
                "timestamp": datetime.now().isoformat(),
                "activity_log": activity_log,
                "network_log": network_log,
                "file_access_log": file_log,
                "clipboard_log": clipboard_log,
            }, ensure_ascii=False, indent=2)

            json_attachment = MIMEBase('application', 'json')
            json_attachment.set_payload(activity_json.encode('utf-8'))
            encoders.encode_base64(json_attachment)
            json_attachment.add_header('Content-Disposition', 'attachment', filename='activity_log.json')
            msg.attach(json_attachment)

            # إرسال
            with smtplib.SMTP(email_cfg["smtp_server"], email_cfg["smtp_port"]) as server:
                if email_cfg.get("use_tls", True):
                    server.starttls()
                server.login(email_cfg["sender_email"], email_cfg["sender_password"])
                server.sendmail(
                    email_cfg["sender_email"],
                    email_cfg["recipient_emails"],
                    msg.as_string()
                )

            logger.info(f"Evidence report sent! ({len(screenshots)} screenshots attached)")
            return True

        except Exception as e:
            logger.error(f"Failed to send evidence report: {e}")
            return False

    def _build_html_report(self, app_name, activity_log, network_log, file_log, clipboard_log, screenshot_count):
        """بناء تقرير HTML"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        hostname = socket.gethostname()
        username = os.environ.get("USER", os.environ.get("USERNAME", "Unknown"))
        os_info = f"{platform.system()} {platform.release()}"

        # بناء جدول النشاط
        activity_rows = ""
        for entry in activity_log[-30:]:
            activity_rows += f"""
            <tr>
                <td style="padding:6px; border-bottom:1px solid #eee; font-size:12px;">{entry.get('time', '')}</td>
                <td style="padding:6px; border-bottom:1px solid #eee; font-size:12px;">{entry.get('window_title', '')[:60]}</td>
                <td style="padding:6px; border-bottom:1px solid #eee; font-size:12px;">{entry.get('process', '')}</td>
            </tr>"""

        # بناء جدول الشبكة
        network_rows = ""
        for conn in network_log[:20]:
            network_rows += f"""
            <tr>
                <td style="padding:6px; border-bottom:1px solid #eee; font-size:12px;">{conn.get('remote', conn.get('raw', ''))[:40]}</td>
                <td style="padding:6px; border-bottom:1px solid #eee; font-size:12px;">{conn.get('process', '')}</td>
                <td style="padding:6px; border-bottom:1px solid #eee; font-size:12px;">{conn.get('state', '')}</td>
            </tr>"""

        # بناء قائمة الملفات
        file_rows = ""
        for f in file_log[:20]:
            file_rows += f"""
            <tr>
                <td style="padding:6px; border-bottom:1px solid #eee; font-size:12px;" dir="ltr">{f.get('path', '')[-60:]}</td>
                <td style="padding:6px; border-bottom:1px solid #eee; font-size:12px;">{f.get('accessed', '')}</td>
            </tr>"""

        # بناء سجل الحافظة
        clipboard_rows = ""
        for c in clipboard_log[:10]:
            content = c.get('content', '')[:100]
            clipboard_rows += f"""
            <tr>
                <td style="padding:6px; border-bottom:1px solid #eee; font-size:12px;">{c.get('time', '')}</td>
                <td style="padding:6px; border-bottom:1px solid #eee; font-size:12px;">{content}</td>
            </tr>"""

        return f"""
        <html dir="rtl">
        <head><meta charset="utf-8"></head>
        <body style="font-family: Arial, sans-serif; background:#f5f5f5; padding:20px;">
        <div style="max-width:800px; margin:0 auto; background:white; border-radius:10px; overflow:hidden; box-shadow:0 2px 15px rgba(0,0,0,0.1);">

            <!-- Header -->
            <div style="background:linear-gradient(135deg, #e74c3c, #8e44ad); color:white; padding:25px; text-align:center;">
                <h1 style="margin:0; font-size:24px;">🚨 تقرير نشاط مشبوه</h1>
                <p style="margin:8px 0 0; opacity:0.9; font-size:16px;">تم اكتشاف {app_name} على الجهاز</p>
            </div>

            <div style="padding:20px;">

                <!-- معلومات الجهاز -->
                <div style="background:#fff3cd; border-right:4px solid #ffc107; padding:15px; margin-bottom:20px; border-radius:4px;">
                    <h3 style="margin:0 0 10px; color:#856404;">⚠️ معلومات الحادثة</h3>
                    <table style="width:100%;">
                        <tr><td style="padding:4px; font-weight:bold; width:120px;">البرنامج:</td><td style="color:#e74c3c; font-weight:bold;">{app_name}</td></tr>
                        <tr><td style="padding:4px; font-weight:bold;">الجهاز:</td><td>{hostname}</td></tr>
                        <tr><td style="padding:4px; font-weight:bold;">المستخدم:</td><td>{username}</td></tr>
                        <tr><td style="padding:4px; font-weight:bold;">النظام:</td><td>{os_info}</td></tr>
                        <tr><td style="padding:4px; font-weight:bold;">الوقت:</td><td>{timestamp}</td></tr>
                        <tr><td style="padding:4px; font-weight:bold;">صور الشاشة:</td><td>{screenshot_count} صورة مرفقة</td></tr>
                    </table>
                </div>

                <!-- سجل النوافذ النشطة -->
                <div style="margin-bottom:20px;">
                    <h3 style="color:#2c3e50; border-bottom:2px solid #3498db; padding-bottom:5px;">
                        🖥️ النوافذ والبرامج النشطة ({len(activity_log)} سجل)
                    </h3>
                    <table style="width:100%; border-collapse:collapse;">
                        <tr style="background:#3498db; color:white;">
                            <th style="padding:8px; text-align:right;">الوقت</th>
                            <th style="padding:8px; text-align:right;">عنوان النافذة</th>
                            <th style="padding:8px; text-align:right;">البرنامج</th>
                        </tr>
                        {activity_rows}
                    </table>
                </div>

                <!-- اتصالات الشبكة -->
                <div style="margin-bottom:20px;">
                    <h3 style="color:#2c3e50; border-bottom:2px solid #e67e22; padding-bottom:5px;">
                        🌐 اتصالات الشبكة ({len(network_log)} اتصال)
                    </h3>
                    <table style="width:100%; border-collapse:collapse;">
                        <tr style="background:#e67e22; color:white;">
                            <th style="padding:8px; text-align:right;">العنوان البعيد</th>
                            <th style="padding:8px; text-align:right;">العملية</th>
                            <th style="padding:8px; text-align:right;">الحالة</th>
                        </tr>
                        {network_rows}
                    </table>
                </div>

                <!-- الملفات -->
                <div style="margin-bottom:20px;">
                    <h3 style="color:#2c3e50; border-bottom:2px solid #27ae60; padding-bottom:5px;">
                        📁 الملفات المفتوحة ({len(file_log)} ملف)
                    </h3>
                    <table style="width:100%; border-collapse:collapse;">
                        <tr style="background:#27ae60; color:white;">
                            <th style="padding:8px; text-align:right;">المسار</th>
                            <th style="padding:8px; text-align:right;">وقت الوصول</th>
                        </tr>
                        {file_rows}
                    </table>
                </div>

                <!-- الحافظة -->
                {f'''
                <div style="margin-bottom:20px;">
                    <h3 style="color:#2c3e50; border-bottom:2px solid #9b59b6; padding-bottom:5px;">
                        📋 سجل الحافظة (Copy/Paste) ({len(clipboard_log)} تغيير)
                    </h3>
                    <table style="width:100%; border-collapse:collapse;">
                        <tr style="background:#9b59b6; color:white;">
                            <th style="padding:8px; text-align:right;">الوقت</th>
                            <th style="padding:8px; text-align:right;">المحتوى</th>
                        </tr>
                        {clipboard_rows}
                    </table>
                </div>
                ''' if clipboard_log else ''}

                <!-- الإجراء المطلوب -->
                <div style="background:#d4edda; border-right:4px solid #28a745; padding:15px; border-radius:4px;">
                    <h3 style="margin:0 0 8px; color:#155724;">📋 الإجراء المطلوب</h3>
                    <p style="margin:0;">راجع صور الشاشة المرفقة وسجل النشاط لمعرفة ما تم عمله على الجهاز أثناء تشغيل برنامج التحكم عن بُعد. اتخذ الإجراء المناسب فوراً.</p>
                </div>

            </div>

            <div style="background:#f8f9fa; padding:15px; text-align:center; color:#888; font-size:12px; border-top:1px solid #eee;">
                Endpoint Security Monitor v1.0 - Activity Report | تم الإرسال تلقائياً
            </div>
        </div>
        </body>
        </html>
        """


# ============================================
#   Main Activity Monitor
# ============================================
class ActivityMonitor:
    """المراقب الرئيسي للنشاط"""

    def __init__(self, config):
        self.config = config
        self.screen_capture = ScreenCapture(EVIDENCE_DIR / "screenshots")
        self.window_tracker = WindowTracker()
        self.process_monitor = ProcessMonitor()
        self.network_logger = NetworkLogger()
        self.file_logger = FileAccessLogger()
        self.clipboard_monitor = ClipboardMonitor()
        self.reporter = EvidenceReporter(config)

        self.is_recording = False
        self.detected_apps = set()
        self.current_session = None

    def check_and_record(self):
        """فحص وتسجيل إذا وُجد برنامج تحكم"""
        remote_apps = self.process_monitor.find_remote_access()

        if remote_apps and not self.is_recording:
            # تم اكتشاف برنامج جديد!
            app_names = set(app["app_name"] for app in remote_apps)
            new_apps = app_names - self.detected_apps

            if new_apps:
                for app_name in new_apps:
                    logger.warning(f"🔴 DETECTED: {app_name} - Starting activity recording!")

                self.detected_apps.update(new_apps)
                detected_str = ", ".join(new_apps)

                # بدء التسجيل في thread منفصل
                self.is_recording = True
                thread = threading.Thread(
                    target=self._record_session,
                    args=(detected_str,),
                    daemon=True
                )
                thread.start()

        elif not remote_apps and self.is_recording:
            # البرنامج اتقفل
            self.is_recording = False
            self.detected_apps.clear()

    def _record_session(self, detected_app):
        """تسجيل جلسة كاملة"""
        logger.info(f"📹 Recording session for: {detected_app}")

        session_dir = EVIDENCE_DIR / f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        session_dir.mkdir(parents=True, exist_ok=True)

        activity_log = []
        screenshots = []
        clipboard_log = []
        start_time = datetime.now()

        screenshot_counter = 0
        last_screenshot_time = 0
        last_activity_time = 0

        while self.is_recording:
            now = time.time()
            current_time = datetime.now()

            # تحقق من انتهاء المدة
            if (current_time - start_time).total_seconds() > MAX_CAPTURE_DURATION:
                logger.info("⏱️ Max recording duration reached")
                break

            # التقاط صورة للشاشة
            if now - last_screenshot_time >= CAPTURE_INTERVAL:
                screenshot_counter += 1
                filename = f"capture_{screenshot_counter:04d}.png"
                screenshot_path = self.screen_capture.capture(filename)

                if screenshot_path:
                    # انقل الصورة لمجلد الجلسة
                    dest = session_dir / filename
                    try:
                        shutil.move(str(screenshot_path), str(dest))
                        screenshots.append(str(dest))
                    except:
                        screenshots.append(str(screenshot_path))

                last_screenshot_time = now

            # تسجيل النافذة النشطة
            if now - last_activity_time >= ACTIVITY_LOG_INTERVAL:
                window = self.window_tracker.get_active_window()
                activity_log.append({
                    "time": current_time.strftime("%H:%M:%S"),
                    "window_title": window.get("title", ""),
                    "process": window.get("process", ""),
                    "pid": window.get("pid", ""),
                })

                # مراقبة الحافظة
                clip_change = self.clipboard_monitor.check_change()
                if clip_change:
                    clipboard_log.append({
                        "time": current_time.strftime("%H:%M:%S"),
                        "content": clip_change["new"],
                    })

                last_activity_time = now

            time.sleep(1)

        # انتهاء التسجيل - جمع البيانات
        logger.info(f"📹 Recording ended. Captured {len(screenshots)} screenshots, {len(activity_log)} activity entries")

        # جمع بيانات الشبكة والملفات
        network_log = self.network_logger.get_connections()
        file_log = self.file_logger.get_recent_files(minutes=15)

        # حفظ السجل المحلي
        session_data = {
            "detected_app": detected_app,
            "start_time": start_time.isoformat(),
            "end_time": datetime.now().isoformat(),
            "hostname": socket.gethostname(),
            "activity_log": activity_log,
            "network_log": network_log,
            "file_log": file_log,
            "clipboard_log": clipboard_log,
            "screenshots_count": len(screenshots),
        }

        with open(session_dir / "session_log.json", 'w', encoding='utf-8') as f:
            json.dump(session_data, f, ensure_ascii=False, indent=2)

        # إرسال التقرير بالإيميل
        self.reporter.send_evidence_report(
            detected_app=detected_app,
            activity_log=activity_log,
            screenshots=screenshots,
            network_log=network_log,
            file_log=file_log,
            clipboard_log=clipboard_log
        )

        # تنظيف الصور القديمة (إبقاء آخر 3 جلسات)
        self._cleanup_old_sessions()

    def _cleanup_old_sessions(self, keep=3):
        """حذف الجلسات القديمة"""
        sessions = sorted(EVIDENCE_DIR.glob("session_*"), key=lambda f: f.stat().st_mtime)
        if len(sessions) > keep:
            for s in sessions[:len(sessions) - keep]:
                shutil.rmtree(s, ignore_errors=True)


# ============================================
#   Integration with Main Agent
# ============================================
def create_activity_monitor(config):
    """إنشاء كائن المراقب للاستخدام مع الوكيل الرئيسي"""
    return ActivityMonitor(config)


# ============================================
#   Standalone Mode
# ============================================
if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════════╗
║     Activity Monitor - مراقب النشاط                          ║
║     يسجل نشاط الجهاز عند اكتشاف برنامج تحكم عن بُعد         ║
╚══════════════════════════════════════════════════════════════╝
    """)

    # تحميل الإعدادات
    config_path = Path(__file__).parent / "config.json"
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    else:
        config = {"email": {"enabled": False}}
        logger.warning("config.json not found - email alerts disabled")

    monitor = ActivityMonitor(config)

    logger.info("🔍 Activity Monitor started - watching for remote access software...")
    logger.info(f"📸 Screenshot interval: {CAPTURE_INTERVAL}s")
    logger.info(f"📝 Activity log interval: {ACTIVITY_LOG_INTERVAL}s")
    logger.info(f"⏱️ Max recording: {MAX_CAPTURE_DURATION}s")

    try:
        while True:
            monitor.check_and_record()
            time.sleep(5)
    except KeyboardInterrupt:
        logger.info("⏹ Monitor stopped")
