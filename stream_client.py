#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║     Live Stream Client - وكيل البث المباشر                    ║
║     يرسل بث الشاشة للداشبورد عند اكتشاف برنامج تحكم         ║
║     يشتغل على أجهزة الموظفين                                 ║
╚══════════════════════════════════════════════════════════════╝
"""

import os
import sys
import io
import time
import json
import base64
import socket
import platform
import subprocess
import threading
import logging
from datetime import datetime
from pathlib import Path

# ============================================
#   تثبيت المكتبات
# ============================================
def install_deps():
    deps = ["socketio[client]", "websocket-client", "Pillow", "mss"]
    for dep in deps:
        try:
            name = dep.split("[")[0]
            __import__(name.replace("-", "_").lower().replace("pillow", "PIL"))
        except ImportError:
            print(f"[i] Installing {dep}...")
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", dep, "--quiet"],
                stderr=subprocess.DEVNULL
            )

install_deps()

import socketio as sio_module

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(str(Path(__file__).parent / "stream.log"), encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("StreamClient")

# ============================================
#   Configuration
# ============================================
CONFIG_FILE = Path(__file__).parent / "config.json"

DEFAULT_STREAM_CONFIG = {
    "dashboard_url": "http://192.168.1.100:5000",
    "stream_fps": 3,
    "stream_quality": 40,
    "stream_scale": 50,
    "always_stream": False
}

# قائمة البرامج المراقبة
REMOTE_ACCESS_PROCESSES = {
    "anydesk", "teamviewer", "teamviewer_service", "rustdesk",
    "remoting_host", "chrome_remote_desktop", "splashtopstreamer",
    "parsecd", "logmein", "lmiguardiansvc", "vncserver", "vncviewer",
    "winvnc", "x11vnc", "radmin", "rserver3", "supremo",
    "supremoservice", "aa_v3", "ammyy", "meshagent", "dwagent",
    "nxd", "nxserver", "remotepc", "screenconnect",
    "connectwisecontrol", "zohoassist", "zohomeeting",
    "client32", "rfusclient", "rutserv",
}

PROCESS_NAMES_MAP = {
    "anydesk": "AnyDesk", "teamviewer": "TeamViewer",
    "teamviewer_service": "TeamViewer", "rustdesk": "RustDesk",
    "remoting_host": "Chrome Remote Desktop", "splashtopstreamer": "Splashtop",
    "parsecd": "Parsec", "logmein": "LogMeIn", "vncserver": "VNC",
    "winvnc": "VNC", "radmin": "Radmin", "supremo": "Supremo",
    "meshagent": "MeshCentral", "dwagent": "DWService",
    "screenconnect": "ScreenConnect", "nxserver": "NoMachine",
}


# ============================================
#   Screen Capturer
# ============================================
class ScreenCapturer:
    """التقاط الشاشة وتحويلها لـ base64"""

    def __init__(self, quality=40, scale=50):
        self.quality = quality
        self.scale = scale
        self.system = platform.system()
        self._init_capturer()

    def _init_capturer(self):
        """تحديد طريقة الالتقاط"""
        self.method = None

        try:
            import mss
            self.method = "mss"
            logger.info("Capture method: mss")
            return
        except ImportError:
            pass

        try:
            from PIL import ImageGrab
            self.method = "pillow"
            logger.info("Capture method: Pillow")
            return
        except ImportError:
            pass

        self.method = "native"
        logger.info(f"Capture method: native ({self.system})")

    def capture_frame(self):
        """التقاط فريم وإرجاعه كـ base64 JPEG"""
        try:
            if self.method == "mss":
                return self._capture_mss()
            elif self.method == "pillow":
                return self._capture_pillow()
            elif self.method == "native":
                return self._capture_native()
        except Exception as e:
            logger.error(f"Capture error: {e}")
        return None

    def _capture_mss(self):
        import mss
        from PIL import Image

        with mss.mss() as sct:
            monitor = sct.monitors[1]
            shot = sct.grab(monitor)
            img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")

        # تصغير الصورة
        if self.scale < 100:
            new_w = int(img.width * self.scale / 100)
            new_h = int(img.height * self.scale / 100)
            img = img.resize((new_w, new_h), Image.LANCZOS)

        # تحويل لـ JPEG base64
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=self.quality, optimize=True)
        return base64.b64encode(buffer.getvalue()).decode('utf-8')

    def _capture_pillow(self):
        from PIL import ImageGrab, Image

        img = ImageGrab.grab()

        if self.scale < 100:
            new_w = int(img.width * self.scale / 100)
            new_h = int(img.height * self.scale / 100)
            img = img.resize((new_w, new_h), Image.LANCZOS)

        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=self.quality, optimize=True)
        return base64.b64encode(buffer.getvalue()).decode('utf-8')

    def _capture_native(self):
        """التقاط باستخدام أدوات النظام"""
        import tempfile
        tmp = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)
        tmp_path = tmp.name
        tmp.close()

        try:
            if self.system == "Windows":
                ps_cmd = f"""
Add-Type -AssemblyName System.Windows.Forms, System.Drawing
$s = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$b = New-Object System.Drawing.Bitmap($s.Width, $s.Height)
$g = [System.Drawing.Graphics]::FromImage($b)
$g.CopyFromScreen($s.Location, [System.Drawing.Point]::Empty, $s.Size)
$enc = [System.Drawing.Imaging.Encoder]::Quality
$params = New-Object System.Drawing.Imaging.EncoderParameters(1)
$params.Param[0] = New-Object System.Drawing.Imaging.EncoderParameter($enc, {self.quality}L)
$codec = [System.Drawing.Imaging.ImageCodecInfo]::GetImageEncoders() | Where-Object {{ $_.MimeType -eq 'image/jpeg' }}
$b.Save('{tmp_path}', $codec, $params)
$g.Dispose(); $b.Dispose()
"""
                subprocess.run(["powershell", "-Command", ps_cmd],
                             capture_output=True, timeout=5)

            elif self.system == "Darwin":
                subprocess.run(["screencapture", "-x", "-t", "jpg", tmp_path],
                             capture_output=True, timeout=5)

            elif self.system == "Linux":
                for cmd in [
                    ["scrot", "-q", str(self.quality), tmp_path],
                    ["import", "-window", "root", tmp_path],
                ]:
                    try:
                        subprocess.run(cmd, capture_output=True, timeout=5)
                        break
                    except FileNotFoundError:
                        continue

            if os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 0:
                with open(tmp_path, 'rb') as f:
                    return base64.b64encode(f.read()).decode('utf-8')

        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

        return None


# ============================================
#   Window Info
# ============================================
class WindowInfo:
    """معلومات النافذة النشطة"""

    def __init__(self):
        self.system = platform.system()

    def get_active(self):
        try:
            if self.system == "Windows":
                result = subprocess.run(
                    ["powershell", "-Command",
                     "(Get-Process | Where-Object {$_.MainWindowTitle} | Select-Object -First 1).MainWindowTitle"],
                    capture_output=True, text=True, timeout=3
                )
                return result.stdout.strip()[:80]
            elif self.system == "Darwin":
                result = subprocess.run(
                    ["osascript", "-e",
                     'tell application "System Events" to get name of first application process whose frontmost is true'],
                    capture_output=True, text=True, timeout=3
                )
                return result.stdout.strip()[:80]
            elif self.system == "Linux":
                result = subprocess.run(
                    ["xdotool", "getactivewindow", "getwindowname"],
                    capture_output=True, text=True, timeout=3
                )
                return result.stdout.strip()[:80]
        except:
            pass
        return ""


# ============================================
#   Process Checker
# ============================================
def check_remote_access():
    """التحقق من وجود برامج تحكم عن بُعد"""
    found = []
    try:
        system = platform.system()
        if system == "Windows":
            output = subprocess.check_output(
                ["tasklist", "/FO", "CSV", "/NH"],
                text=True, stderr=subprocess.DEVNULL, timeout=5
            )
            for line in output.strip().split('\n'):
                parts = line.strip('"').split('","')
                if parts:
                    name = parts[0].lower().replace(".exe", "")
                    if name in REMOTE_ACCESS_PROCESSES:
                        found.append(PROCESS_NAMES_MAP.get(name, name))
        else:
            output = subprocess.check_output(
                ["ps", "-eo", "comm"],
                text=True, stderr=subprocess.DEVNULL, timeout=5
            )
            for line in output.strip().split('\n'):
                name = line.strip().lower()
                if name in REMOTE_ACCESS_PROCESSES:
                    found.append(PROCESS_NAMES_MAP.get(name, name))
    except:
        pass
    return list(set(found))


# ============================================
#   Stream Client
# ============================================
class LiveStreamClient:
    """عميل البث المباشر"""

    def __init__(self, config):
        self.config = config
        stream_cfg = config.get("live_stream", DEFAULT_STREAM_CONFIG)

        self.dashboard_url = stream_cfg.get("dashboard_url", DEFAULT_STREAM_CONFIG["dashboard_url"])
        self.fps = stream_cfg.get("stream_fps", 3)
        self.quality = stream_cfg.get("stream_quality", 40)
        self.scale = stream_cfg.get("stream_scale", 50)
        self.always_stream = stream_cfg.get("always_stream", False)

        self.capturer = ScreenCapturer(quality=self.quality, scale=self.scale)
        self.window_info = WindowInfo()

        self.agent_id = f"{socket.gethostname()}_{self._get_mac()}"
        self.hostname = socket.gethostname()
        self.os_info = f"{platform.system()} {platform.release()}"
        self.username = os.environ.get("USER", os.environ.get("USERNAME", "Unknown"))

        self.sio = sio_module.Client(reconnection=True, reconnection_delay=5)
        self.connected = False
        self.streaming = False
        self.detected_app = ""

        self._setup_events()

    def _get_mac(self):
        """الحصول على MAC address كمعرف فريد"""
        try:
            import uuid
            mac = uuid.getnode()
            return ':'.join(('%012x' % mac)[i:i+2] for i in range(0, 12, 2))[-8:]
        except:
            return "unknown"

    def _setup_events(self):
        @self.sio.on("connect")
        def on_connect():
            self.connected = True
            logger.info(f"✅ Connected to dashboard: {self.dashboard_url}")
            # تسجيل الوكيل
            self.sio.emit("register_agent", {
                "agent_id": self.agent_id,
                "hostname": self.hostname,
                "os": self.os_info,
                "user": self.username,
            })

        @self.sio.on("disconnect")
        def on_disconnect():
            self.connected = False
            self.streaming = False
            logger.warning("❌ Disconnected from dashboard")

        @self.sio.on("start_stream")
        def on_start_stream(data=None):
            if not self.streaming:
                logger.info("📡 Admin requested stream")
                self._start_streaming()

        # بدء heartbeat بعد الاتصال
        self._start_heartbeat()

    def _start_heartbeat(self):
        """إرسال نبض حياة كل 15 ثانية"""
        def heartbeat_loop():
            while True:
                try:
                    if self.connected:
                        self.sio.emit("heartbeat", {
                            "agent_id": self.agent_id,
                            "hostname": self.hostname,
                            "os": self.os_info,
                            "user": self.username,
                        })
                except Exception:
                    pass
                time.sleep(15)

        thread = threading.Thread(target=heartbeat_loop, daemon=True)
        thread.start()

    def connect(self):
        """الاتصال بالداشبورد"""
        try:
            logger.info(f"🔌 Connecting to {self.dashboard_url}...")
            self.sio.connect(self.dashboard_url, transports=['websocket', 'polling'])
            return True
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return False

    def _start_streaming(self):
        """بدء البث في thread منفصل"""
        if self.streaming:
            return
        self.streaming = True
        thread = threading.Thread(target=self._stream_loop, daemon=True)
        thread.start()

    def _stop_streaming(self):
        """إيقاف البث"""
        self.streaming = False

    def _stream_loop(self):
        """حلقة البث"""
        logger.info(f"📹 Streaming started ({self.fps} FPS, {self.quality}% quality)")
        interval = 1.0 / self.fps

        while self.streaming and self.connected:
            try:
                start = time.time()

                # التقاط الشاشة
                frame = self.capturer.capture_frame()
                if frame:
                    active_window = self.window_info.get_active()

                    # إرسال الفريم
                    self.sio.emit("screen_frame", {
                        "agent_id": self.agent_id,
                        "hostname": self.hostname,
                        "os": self.os_info,
                        "user": self.username,
                        "frame": frame,
                        "detected_app": self.detected_app,
                        "active_window": active_window,
                        "timestamp": datetime.now().isoformat(),
                    })

                    # إرسال نشاط النافذة (كل 5 فريمات)
                    if hasattr(self, '_frame_count'):
                        self._frame_count += 1
                    else:
                        self._frame_count = 0

                    if self._frame_count % 5 == 0 and active_window:
                        self.sio.emit("window_activity", {
                            "agent_id": self.agent_id,
                            "hostname": self.hostname,
                            "window_title": active_window,
                        })

                # التحكم بالسرعة
                elapsed = time.time() - start
                sleep_time = max(0, interval - elapsed)
                time.sleep(sleep_time)

            except Exception as e:
                logger.error(f"Stream error: {e}")
                time.sleep(1)

        logger.info("📹 Streaming stopped")

    def monitor_and_stream(self):
        """مراقبة البرامج وبدء البث عند الاكتشاف"""
        logger.info("🔍 Monitoring for remote access software...")

        was_detected = False

        while True:
            try:
                # التحقق من الاتصال
                if not self.connected:
                    self.connect()
                    time.sleep(5)
                    continue

                # البث الدائم (لو مفعل)
                if self.always_stream and not self.streaming:
                    self.detected_app = "مراقبة عامة"
                    self._start_streaming()

                # التحقق من برامج التحكم
                detected = check_remote_access()

                if detected:
                    self.detected_app = ", ".join(detected)

                    if not was_detected:
                        # اكتشاف جديد!
                        logger.warning(f"🚨 DETECTED: {self.detected_app}")

                        # إرسال تنبيه
                        self.sio.emit("agent_alert", {
                            "agent_id": self.agent_id,
                            "hostname": self.hostname,
                            "message": f"تم اكتشاف {self.detected_app}",
                            "severity": "HIGH",
                        })

                        was_detected = True

                    # بدء البث
                    if not self.streaming:
                        self._start_streaming()

                else:
                    if was_detected:
                        logger.info("✅ Remote access software closed")
                        self.sio.emit("agent_alert", {
                            "agent_id": self.agent_id,
                            "hostname": self.hostname,
                            "message": f"تم إغلاق {self.detected_app}",
                            "severity": "LOW",
                        })
                        was_detected = False
                        self.detected_app = ""

                    # إيقاف البث لو مافي برنامج (إلا لو always_stream)
                    if not self.always_stream and self.streaming:
                        self._stop_streaming()

                time.sleep(3)

            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Monitor error: {e}")
                time.sleep(5)

    def disconnect(self):
        self.streaming = False
        try:
            self.sio.disconnect()
        except:
            pass


# ============================================
#   Integration with main agent
# ============================================
def create_stream_client(config):
    """إنشاء عميل البث للاستخدام مع الوكيل الرئيسي"""
    return LiveStreamClient(config)


# ============================================
#   Standalone Mode
# ============================================
if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════════╗
║     📡 Live Stream Client - عميل البث المباشر               ║
╚══════════════════════════════════════════════════════════════╝
    """)

    # تحميل الإعدادات
    config = {}
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)

    # التحقق من إعدادات البث
    if "live_stream" not in config:
        print("  ⚠️  إعدادات البث غير موجودة في config.json")
        print("  سيتم استخدام الإعدادات الافتراضية")
        print()

        url = input(f"  أدخل عنوان الداشبورد [{DEFAULT_STREAM_CONFIG['dashboard_url']}]: ").strip()
        if url:
            config["live_stream"] = {"dashboard_url": url}
        else:
            config["live_stream"] = DEFAULT_STREAM_CONFIG.copy()

    client = LiveStreamClient(config)

    logger.info(f"Dashboard URL: {client.dashboard_url}")
    logger.info(f"Agent ID: {client.agent_id}")
    logger.info(f"FPS: {client.fps} | Quality: {client.quality}% | Scale: {client.scale}%")

    try:
        client.connect()
        time.sleep(2)
        client.monitor_and_stream()
    except KeyboardInterrupt:
        logger.info("⏹ Stopped")
    finally:
        client.disconnect()
