"""Integrasi dengan sistem operasi (Windows, macOS, Linux): membuka link/berkas, tombol pengubah shortcut, dan
interpreter Python untuk proses tanpa jendela konsol."""
import os
import re
import subprocess
import sys
import webbrowser
from pathlib import Path

IS_WIN = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"
MOD = "Command" if IS_MAC else "Control"  # pengubah shortcut keyboard (Tk): Cmd di macOS, Ctrl di lainnya
MOD_LABEL = "Cmd" if IS_MAC else "Ctrl"  # teks shortcut di menu


def open_url(url):
    """Buka link di browser. Hanya http(s); kegagalan (misalnya tanpa browser bawaan) diabaikan."""
    if not re.match(r"^https?://", url or ""):
        return
    try:
        webbrowser.open(url)
    except (webbrowser.Error, OSError):
        pass


def open_path(path):
    """Buka berkas dengan aplikasi bawaan OS. False bila tidak bisa (berkas tidak ada, tanpa xdg-open, dsb.)."""
    path = Path(path)
    if not path.exists():
        return False
    try:
        if IS_WIN:
            os.startfile(path)
        else:
            subprocess.Popen(["open" if IS_MAC else "xdg-open", str(path)],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        return False
    return True


def gui_python():
    """Interpreter untuk proses GUI anak: pythonw.exe di Windows (tanpa jendela konsol), selain itu python biasa."""
    exe = Path(sys.executable)
    windowless = exe.with_name("pythonw.exe")
    return windowless if IS_WIN and windowless.exists() else exe


def no_console_flags():
    """creationflags untuk subprocess.Popen: tanpa jendela konsol di Windows."""
    return getattr(subprocess, "CREATE_NO_WINDOW", 0) if IS_WIN else 0
