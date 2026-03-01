#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║     Intruder IP Tracker - تتبع IP المخترق                    ║
║                                                              ║
║     • كشف IP الجهاز اللي بيحاول يدخل                        ║
║     • تحديد الموقع الجغرافي والمدينة والدولة                 ║
║     • معرفة مزود الإنترنت (ISP)                              ║
║     • تسجيل كل محاولة اتصال مع الوقت                        ║
║     • إرسال البيانات مباشرة للداشبورد                        ║
╚══════════════════════════════════════════════════════════════╝
"""

import os
import sys
import time
import json
import socket
import platform
import subprocess
import threading
import logging
from datetime import datetime
from pathlib import Path

try:
    import urllib.request
    HAS_URLLIB = True
except:
    HAS_URLLIB = False

logger = logging.getLogger("IntruderTracker")
SYSTEM = platform.system()


# ============================================
#   بورتات برامج التحكم المعروفة
# ============================================
REMOTE_ACCESS_PORTS = {
    # AnyDesk
    7070: "AnyDesk",
    # TeamViewer
    5938: "TeamViewer",
    # VNC
    5900: "VNC", 5901: "VNC", 5902: "VNC", 5903: "VNC",
    5800: "VNC (HTTP)",
    # RustDesk
    21115: "RustDesk", 21116: "RustDesk", 21117: "RustDesk",
    21118: "RustDesk", 21119: "RustDesk",
    # Radmin
    4899: "Radmin",
    # NoMachine
    4000: "NoMachine",
    # SSH (ممكن يُستخدم للتحكم)
    22: "SSH",
    # RDP
    3389: "RDP (Remote Desktop)",
    # Splashtop
    6783: "Splashtop",
    # Parsec
    8000: "Parsec",
    # ScreenConnect
    8040: "ScreenConnect", 8041: "ScreenConnect",
    # NetSupport
    5405: "NetSupport",
}

# بورتات إضافية مشبوهة (نطاقات تحكم عن بعد)
SUSPICIOUS_PORT_RANGES = [
    (5900, 5910, "VNC"),
    (6560, 6570, "AnyDesk (alt)"),
    (8200, 8210, "ScreenConnect (alt)"),
]


# ============================================
#   Network Connection Scanner
# ============================================
class ConnectionScanner:
    """فحص الاتصالات الشبكية النشطة"""

    @staticmethod
    def get_remote_connections():
        """
        الحصول على جميع الاتصالات الواردة من أجهزة خارجية
        يرجع: [{remote_ip, remote_port, local_port, app_name, state}]
        """
        connections = []

        try:
            if SYSTEM == "Windows":
                connections = ConnectionScanner._scan_windows()
            elif SYSTEM == "Linux":
                connections = ConnectionScanner._scan_linux()
            elif SYSTEM == "Darwin":
                connections = ConnectionScanner._scan_mac()
        except Exception as e:
            logger.error(f"Connection scan error: {e}")

        # تصفية — فقط الاتصالات من IPs خارجية
        external = []
        for conn in connections:
            ip = conn.get("remote_ip", "")
            if ip and not ConnectionScanner._is_local_ip(ip):
                external.append(conn)

        return external

    @staticmethod
    def _scan_windows():
        """فحص على ويندوز باستخدام netstat + PowerShell"""
        connections = []

        # netstat مع اسم العملية
        try:
            result = subprocess.run(
                ["netstat", "-ano", "-p", "tcp"],
                capture_output=True, text=True, timeout=10
            )

            for line in result.stdout.strip().split('\n'):
                line = line.strip()
                if 'ESTABLISHED' not in line and 'SYN_RECEIVED' not in line:
                    continue

                parts = line.split()
                if len(parts) < 5:
                    continue

                local_addr = parts[1]
                remote_addr = parts[2]
                state = parts[3]
                pid = parts[4]

                try:
                    local_port = int(local_addr.rsplit(':', 1)[1])
                    remote_ip = remote_addr.rsplit(':', 1)[0]
                    remote_port = int(remote_addr.rsplit(':', 1)[1])
                except:
                    continue

                # هل البورت المحلي من بورتات التحكم؟
                app_name = REMOTE_ACCESS_PORTS.get(local_port, "")

                # فحص نطاقات مشبوهة
                if not app_name:
                    for start, end, name in SUSPICIOUS_PORT_RANGES:
                        if start <= local_port <= end:
                            app_name = name
                            break

                # هل البورت البعيد من بورتات التحكم؟
                if not app_name:
                    app_name = REMOTE_ACCESS_PORTS.get(remote_port, "")

                if app_name or local_port > 1024:
                    # الحصول على اسم العملية من PID
                    proc_name = ConnectionScanner._get_process_name_win(pid)

                    # تحقق إضافي — هل العملية برنامج تحكم؟
                    if not app_name:
                        app_name = ConnectionScanner._identify_by_process(proc_name)

                    if app_name:
                        connections.append({
                            "remote_ip": remote_ip.strip("[]"),
                            "remote_port": remote_port,
                            "local_port": local_port,
                            "app_name": app_name,
                            "state": state,
                            "pid": pid,
                            "process": proc_name,
                        })

        except Exception as e:
            logger.error(f"Windows netstat error: {e}")

        return connections

    @staticmethod
    def _scan_linux():
        """فحص على لينكس"""
        connections = []

        try:
            # ss أسرع من netstat
            result = subprocess.run(
                ["ss", "-tnp", "state", "established"],
                capture_output=True, text=True, timeout=10
            )

            for line in result.stdout.strip().split('\n')[1:]:
                parts = line.split()
                if len(parts) < 5:
                    continue

                local_addr = parts[3]
                remote_addr = parts[4]

                try:
                    local_port = int(local_addr.rsplit(':', 1)[1])
                    remote_ip = remote_addr.rsplit(':', 1)[0]
                    remote_port = int(remote_addr.rsplit(':', 1)[1])
                except:
                    continue

                app_name = REMOTE_ACCESS_PORTS.get(local_port, "")
                if not app_name:
                    app_name = REMOTE_ACCESS_PORTS.get(remote_port, "")

                # اسم العملية
                proc_name = ""
                if len(parts) > 5:
                    proc_info = parts[5] if len(parts) > 5 else ""
                    if "users:" in proc_info:
                        proc_name = proc_info.split('"')[1] if '"' in proc_info else ""

                if not app_name:
                    app_name = ConnectionScanner._identify_by_process(proc_name)

                if app_name:
                    connections.append({
                        "remote_ip": remote_ip.strip("[]"),
                        "remote_port": remote_port,
                        "local_port": local_port,
                        "app_name": app_name,
                        "state": "ESTABLISHED",
                        "process": proc_name,
                    })

        except FileNotFoundError:
            # fallback to netstat
            try:
                result = subprocess.run(
                    ["netstat", "-tnp"],
                    capture_output=True, text=True, timeout=10
                )
                for line in result.stdout.strip().split('\n'):
                    if 'ESTABLISHED' in line:
                        parts = line.split()
                        if len(parts) >= 5:
                            try:
                                local_port = int(parts[3].rsplit(':', 1)[1])
                                remote_ip = parts[4].rsplit(':', 1)[0]
                                remote_port = int(parts[4].rsplit(':', 1)[1])
                                app_name = REMOTE_ACCESS_PORTS.get(local_port, "")
                                if not app_name:
                                    app_name = REMOTE_ACCESS_PORTS.get(remote_port, "")
                                if app_name:
                                    connections.append({
                                        "remote_ip": remote_ip,
                                        "remote_port": remote_port,
                                        "local_port": local_port,
                                        "app_name": app_name,
                                        "state": "ESTABLISHED",
                                    })
                            except:
                                pass
            except:
                pass

        return connections

    @staticmethod
    def _scan_mac():
        """فحص على ماك"""
        connections = []

        try:
            result = subprocess.run(
                ["lsof", "-i", "-n", "-P"],
                capture_output=True, text=True, timeout=10
            )

            for line in result.stdout.strip().split('\n')[1:]:
                if 'ESTABLISHED' not in line:
                    continue
                parts = line.split()
                if len(parts) < 9:
                    continue

                proc_name = parts[0]
                connection_info = parts[8]

                if '->' in connection_info:
                    local_part, remote_part = connection_info.split('->')
                    try:
                        local_port = int(local_part.rsplit(':', 1)[1])
                        remote_ip = remote_part.rsplit(':', 1)[0]
                        remote_port = int(remote_part.rsplit(':', 1)[1])
                    except:
                        continue

                    app_name = REMOTE_ACCESS_PORTS.get(local_port, "")
                    if not app_name:
                        app_name = REMOTE_ACCESS_PORTS.get(remote_port, "")
                    if not app_name:
                        app_name = ConnectionScanner._identify_by_process(proc_name)

                    if app_name:
                        connections.append({
                            "remote_ip": remote_ip,
                            "remote_port": remote_port,
                            "local_port": local_port,
                            "app_name": app_name,
                            "state": "ESTABLISHED",
                            "process": proc_name,
                        })

        except Exception as e:
            logger.error(f"macOS scan error: {e}")

        return connections

    @staticmethod
    def _get_process_name_win(pid):
        """الحصول على اسم العملية من PID على ويندوز"""
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                capture_output=True, text=True, timeout=5
            )
            parts = result.stdout.strip().strip('"').split('","')
            return parts[0] if parts else ""
        except:
            return ""

    @staticmethod
    def _identify_by_process(proc_name):
        """تحديد البرنامج من اسم العملية"""
        if not proc_name:
            return ""

        proc_lower = proc_name.lower()

        known_processes = {
            "anydesk": "AnyDesk",
            "teamviewer": "TeamViewer",
            "rustdesk": "RustDesk",
            "remoting_host": "Chrome Remote Desktop",
            "splashtop": "Splashtop",
            "parsec": "Parsec",
            "logmein": "LogMeIn",
            "vnc": "VNC",
            "winvnc": "VNC",
            "x11vnc": "VNC",
            "radmin": "Radmin",
            "rserver": "Radmin",
            "supremo": "Supremo",
            "ammyy": "Ammyy Admin",
            "meshagent": "MeshCentral",
            "dwagent": "DWService",
            "nxserver": "NoMachine",
            "nxd": "NoMachine",
            "screenconnect": "ScreenConnect",
            "rfusclient": "Remote Utilities",
            "rutserv": "Remote Utilities",
            "netsupport": "NetSupport",
            "client32": "NetSupport",
            "zohoassist": "Zoho Assist",
            "sshd": "SSH",
            "mstsc": "RDP",
        }

        for key, name in known_processes.items():
            if key in proc_lower:
                return name

        return ""

    @staticmethod
    def _is_local_ip(ip):
        """هل الـ IP محلي؟"""
        if not ip:
            return True
        return (
            ip.startswith("127.") or
            ip.startswith("0.") or
            ip == "::1" or
            ip == "0.0.0.0" or
            ip == "*"
        )


# ============================================
#   IP Info Lookup (معلومات الـ IP)
# ============================================
class IPInfoLookup:
    """البحث عن معلومات IP — الموقع، الدولة، ISP"""

    _cache = {}

    @classmethod
    def lookup(cls, ip):
        """
        البحث عن معلومات IP
        يرجع: {ip, country, city, region, isp, org, timezone, lat, lon}
        """
        # كاش عشان ما نكرر الطلبات
        if ip in cls._cache:
            return cls._cache[ip]

        # تجاوز IPs الخاصة
        if cls._is_private(ip):
            info = {
                "ip": ip,
                "country": "شبكة محلية",
                "city": "LAN",
                "region": "-",
                "isp": "Local Network",
                "org": "-",
                "timezone": "-",
                "lat": 0, "lon": 0,
                "is_private": True,
            }
            cls._cache[ip] = info
            return info

        info = cls._lookup_ipapi(ip)

        if info:
            cls._cache[ip] = info

        return info

    @classmethod
    def _lookup_ipapi(cls, ip):
        """البحث عبر ip-api.com (مجاني، بدون مفتاح)"""
        if not HAS_URLLIB:
            return cls._basic_info(ip)

        try:
            url = f"http://ip-api.com/json/{ip}?fields=status,message,country,countryCode,region,regionName,city,zip,lat,lon,timezone,isp,org,as,query&lang=ar"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode())

            if data.get("status") == "success":
                return {
                    "ip": ip,
                    "country": data.get("country", "غير معروف"),
                    "country_code": data.get("countryCode", ""),
                    "city": data.get("city", "غير معروف"),
                    "region": data.get("regionName", ""),
                    "isp": data.get("isp", "غير معروف"),
                    "org": data.get("org", ""),
                    "as": data.get("as", ""),
                    "timezone": data.get("timezone", ""),
                    "lat": data.get("lat", 0),
                    "lon": data.get("lon", 0),
                    "zip": data.get("zip", ""),
                    "is_private": False,
                }
        except Exception as e:
            logger.debug(f"ip-api lookup failed: {e}")

        # Fallback: ipinfo.io
        try:
            url = f"https://ipinfo.io/{ip}/json"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode())

            loc = data.get("loc", "0,0").split(",")
            return {
                "ip": ip,
                "country": data.get("country", "غير معروف"),
                "country_code": data.get("country", ""),
                "city": data.get("city", "غير معروف"),
                "region": data.get("region", ""),
                "isp": data.get("org", "غير معروف"),
                "org": data.get("org", ""),
                "timezone": data.get("timezone", ""),
                "lat": float(loc[0]) if len(loc) > 0 else 0,
                "lon": float(loc[1]) if len(loc) > 1 else 0,
                "is_private": False,
            }
        except Exception as e:
            logger.debug(f"ipinfo lookup failed: {e}")

        return cls._basic_info(ip)

    @classmethod
    def _basic_info(cls, ip):
        """معلومات أساسية بدون API"""
        # محاولة reverse DNS
        hostname = ""
        try:
            hostname = socket.gethostbyaddr(ip)[0]
        except:
            pass

        return {
            "ip": ip,
            "country": "غير معروف",
            "city": "غير معروف",
            "region": "",
            "isp": hostname or "غير معروف",
            "org": "",
            "timezone": "",
            "lat": 0, "lon": 0,
            "hostname": hostname,
            "is_private": cls._is_private(ip),
        }

    @classmethod
    def _is_private(cls, ip):
        """هل IP خاص (شبكة محلية)؟"""
        return (
            ip.startswith("10.") or
            ip.startswith("172.16.") or ip.startswith("172.17.") or
            ip.startswith("172.18.") or ip.startswith("172.19.") or
            ip.startswith("172.2") or ip.startswith("172.3") or
            ip.startswith("192.168.") or
            ip.startswith("169.254.") or
            ip.startswith("127.") or
            ip == "::1"
        )


# ============================================
#   Intruder Tracker Engine
# ============================================
class IntruderTracker:
    """المحرك الرئيسي لتتبع المخترقين"""

    LOG_FILE = Path(__file__).parent / "intrusion_log.json"

    def __init__(self, sio_client=None):
        self.sio = sio_client
        self.monitoring = False
        self.known_connections = {}  # {ip: last_seen}
        self.intrusion_log = []

    def start(self):
        """بدء المراقبة"""
        self.monitoring = True
        threading.Thread(target=self._monitor_loop, daemon=True).start()
        logger.info("🔍 Intruder IP tracker started")

    def stop(self):
        self.monitoring = False

    def scan_now(self):
        """فحص فوري — يرجع قائمة الاتصالات المشبوهة مع بياناتها"""
        connections = ConnectionScanner.get_remote_connections()
        results = []

        for conn in connections:
            ip = conn["remote_ip"]
            ip_info = IPInfoLookup.lookup(ip)

            result = {
                **conn,
                **ip_info,
                "detected_at": datetime.now().isoformat(),
            }
            results.append(result)

        return results

    def _monitor_loop(self):
        """حلقة المراقبة المستمرة"""
        while self.monitoring:
            try:
                connections = ConnectionScanner.get_remote_connections()

                for conn in connections:
                    ip = conn["remote_ip"]

                    # اتصال جديد؟
                    if ip not in self.known_connections:
                        # IP جديد — البحث عن معلوماته
                        ip_info = IPInfoLookup.lookup(ip)

                        intrusion = {
                            **conn,
                            **ip_info,
                            "detected_at": datetime.now().isoformat(),
                            "hostname": socket.gethostname(),
                        }

                        self.intrusion_log.append(intrusion)
                        self._save_log()

                        # تنبيه!
                        logger.warning(
                            f"🚨 INTRUDER DETECTED!"
                            f" IP: {ip}"
                            f" | {ip_info.get('city', '?')}, {ip_info.get('country', '?')}"
                            f" | ISP: {ip_info.get('isp', '?')}"
                            f" | App: {conn.get('app_name', '?')}"
                        )

                        # إرسال للداشبورد
                        self._notify_dashboard(intrusion)

                    # تحديث وقت آخر مشاهدة
                    self.known_connections[ip] = time.time()

                # تنظيف الاتصالات القديمة (أكثر من 5 دقائق)
                cutoff = time.time() - 300
                self.known_connections = {
                    ip: t for ip, t in self.known_connections.items()
                    if t > cutoff
                }

            except Exception as e:
                logger.error(f"Monitor error: {e}")

            time.sleep(3)

    def _notify_dashboard(self, intrusion):
        """إرسال تنبيه للداشبورد"""
        if not self.sio:
            return

        try:
            self.sio.emit("intruder_detected", {
                "agent_id": socket.gethostname(),
                "hostname": socket.gethostname(),
                "intruder_ip": intrusion.get("remote_ip", ""),
                "country": intrusion.get("country", "غير معروف"),
                "city": intrusion.get("city", "غير معروف"),
                "isp": intrusion.get("isp", "غير معروف"),
                "org": intrusion.get("org", ""),
                "app_name": intrusion.get("app_name", ""),
                "local_port": intrusion.get("local_port", 0),
                "remote_port": intrusion.get("remote_port", 0),
                "process": intrusion.get("process", ""),
                "lat": intrusion.get("lat", 0),
                "lon": intrusion.get("lon", 0),
                "is_private": intrusion.get("is_private", False),
                "detected_at": intrusion.get("detected_at", ""),
            })
        except Exception as e:
            logger.error(f"Dashboard notification error: {e}")

    def _save_log(self):
        """حفظ سجل الاختراقات"""
        try:
            # آخر 1000 سجل فقط
            recent = self.intrusion_log[-1000:]
            with open(self.LOG_FILE, 'w', encoding='utf-8') as f:
                json.dump(recent, f, ensure_ascii=False, indent=2)
        except:
            pass

    def get_log(self):
        """قراءة سجل الاختراقات"""
        if self.LOG_FILE.exists():
            with open(self.LOG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []


# ============================================
#   Integration
# ============================================
def create_intruder_tracker(sio_client=None):
    """إنشاء متتبع المخترقين"""
    tracker = IntruderTracker(sio_client)
    return tracker


# ============================================
#   CLI
# ============================================
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')

    print("""
╔══════════════════════════════════════════════════════════════╗
║     🔍 Intruder IP Tracker                                   ║
║     تتبع IP المخترقين                                       ║
╚══════════════════════════════════════════════════════════════╝
    """)

    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--scan", action="store_true", help="Scan now")
    parser.add_argument("--monitor", action="store_true", help="Continuous monitoring")
    parser.add_argument("--lookup", type=str, help="Lookup specific IP")
    parser.add_argument("--log", action="store_true", help="Show intrusion log")
    args = parser.parse_args()

    if args.lookup:
        print(f"  🔍 البحث عن: {args.lookup}")
        info = IPInfoLookup.lookup(args.lookup)
        print(f"""
  ╔════════════════════════════════════════╗
  ║  IP:      {info.get('ip', '?'):>27} ║
  ║  الدولة:  {info.get('country', '?'):>27} ║
  ║  المدينة: {info.get('city', '?'):>27} ║
  ║  المنطقة: {info.get('region', '?'):>27} ║
  ║  ISP:     {info.get('isp', '?'):>27} ║
  ║  المنظمة: {info.get('org', '?'):>27} ║
  ║  التوقيت: {info.get('timezone', '?'):>27} ║
  ╚════════════════════════════════════════╝
        """)

    elif args.scan:
        print("  🔍 جاري الفحص...")
        tracker = IntruderTracker()
        results = tracker.scan_now()
        if results:
            for r in results:
                print(f"""
  🚨 اتصال مكتشف:
     IP:       {r.get('remote_ip', '?')}
     البرنامج: {r.get('app_name', '?')}
     الدولة:   {r.get('country', '?')}
     المدينة:  {r.get('city', '?')}
     ISP:      {r.get('isp', '?')}
     البورت:   {r.get('local_port', '?')} ← {r.get('remote_port', '?')}
     العملية:  {r.get('process', '?')}
                """)
        else:
            print("  ✅ لا توجد اتصالات مشبوهة حالياً")

    elif args.monitor:
        print("  👁️ مراقبة مستمرة... (Ctrl+C للإيقاف)")
        tracker = IntruderTracker()
        tracker.start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            tracker.stop()

    elif args.log:
        tracker = IntruderTracker()
        log = tracker.get_log()
        if log:
            print(f"  📋 {len(log)} محاولة مسجلة:\n")
            for entry in log[-20:]:
                print(f"  [{entry.get('detected_at', '?')[:19]}] "
                      f"{entry.get('remote_ip', '?'):>15} "
                      f"| {entry.get('country', '?'):>10} "
                      f"| {entry.get('city', '?'):>12} "
                      f"| {entry.get('app_name', '?')}")
        else:
            print("  📋 لا توجد سجلات")

    else:
        print("  --scan     فحص فوري")
        print("  --monitor  مراقبة مستمرة")
        print("  --lookup IP  بحث عن IP معين")
        print("  --log      عرض السجل")
