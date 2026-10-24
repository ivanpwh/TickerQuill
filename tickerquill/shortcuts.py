"""Shortcut untuk membuka TickerQuill tanpa terminal, dengan ikon aplikasi.

Windows: Start Menu dan Desktop (.lnk, dibuat lewat PowerShell). macOS: ~/Applications/TickerQuill.app.
Linux: menu aplikasi (~/.local/share/applications/tickerquill.desktop). Semuanya menjalankan `python -m tickerquill`
dengan interpreter yang sedang dipakai (pythonw di Windows, tanpa jendela konsol).
"""
import os
import plistlib
import shutil
import subprocess
from pathlib import Path

from . import __version__, paths
from .system import IS_MAC, IS_WIN, gui_python, no_console_flags

NAME = "TickerQuill"
BUNDLE_ID = "io.github.ivanpwh.tickerquill"
WM_CLASS = "Tickerquill"  # kelas jendela Tk (className="TickerQuill" jadi "Tickerquill"); dicocokkan di Linux
_LNK_SCRIPT = ("$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:TQ_LNK);$s.TargetPath=$env:TQ_TARGET;"
               "$s.Arguments='-m tickerquill';$s.WorkingDirectory=$env:TQ_DIR;"
               "if($env:TQ_ICON){$s.IconLocation=$env:TQ_ICON};$s.Description='TickerQuill';$s.Save()")


def working_dir():
    """Dijalankan dari source tanpa instalasi: `-m tickerquill` butuh folder repo sebagai folder kerja."""
    return paths.SOURCE if paths.is_source_checkout() else Path.home()


def icon(name):
    path = paths.ICONS / name
    return path if path.exists() else None


def _xdg_data():
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")


def _windows_folders():
    out = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                          "[Environment]::GetFolderPath('Programs');[Environment]::GetFolderPath('Desktop')"],
                         capture_output=True, text=True, timeout=60, check=True, creationflags=no_console_flags())
    return [Path(line.strip()) for line in out.stdout.splitlines() if line.strip()][:2]


def targets():
    """Berkas yang dibuat create() di OS ini."""
    if IS_WIN:
        return [folder / f"{NAME}.lnk" for folder in _windows_folders()]
    if IS_MAC:
        return [Path.home() / "Applications" / f"{NAME}.app"]
    return [_xdg_data() / "applications" / "tickerquill.desktop", _xdg_data() / "icons" / "hicolor" / "256x256" / "apps" / "tickerquill.png"]


def create():
    if IS_WIN:
        return _create_windows()
    if IS_MAC:
        return _create_mac()
    return _create_linux()


def remove():
    removed = []
    for path in targets():
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()
        else:
            continue
        removed.append(path)
    return removed


def _create_windows():
    made = []
    ico = icon("tickerquill.ico")
    for lnk in targets():
        lnk.parent.mkdir(parents=True, exist_ok=True)
        env = {**os.environ, "TQ_LNK": str(lnk), "TQ_TARGET": str(gui_python()), "TQ_DIR": str(working_dir()),
               "TQ_ICON": str(ico) if ico else ""}  # nilai lewat variabel lingkungan: aman dari masalah tanda kutip
        subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", _LNK_SCRIPT], env=env,
                       capture_output=True, text=True, timeout=60, check=True, creationflags=no_console_flags())
        made.append(lnk)
    return made


def _create_mac():
    app = targets()[0]
    contents = app / "Contents"
    (contents / "MacOS").mkdir(parents=True, exist_ok=True)
    (contents / "Resources").mkdir(parents=True, exist_ok=True)
    launcher = contents / "MacOS" / NAME
    launcher.write_text(f'#!/bin/sh\ncd "{working_dir()}"\nexec "{gui_python()}" -m tickerquill "$@"\n', encoding="utf-8")
    launcher.chmod(0o755)
    info = {"CFBundleName": NAME, "CFBundleDisplayName": NAME, "CFBundleIdentifier": BUNDLE_ID,
            "CFBundleExecutable": NAME, "CFBundlePackageType": "APPL", "CFBundleShortVersionString": __version__,
            "CFBundleVersion": __version__, "NSHighResolutionCapable": True}
    icns = icon("tickerquill.icns")
    if icns:
        shutil.copy2(icns, contents / "Resources" / f"{NAME}.icns")
        info["CFBundleIconFile"] = NAME
    with open(contents / "Info.plist", "wb") as f:
        plistlib.dump(info, f)
    return [app]


def _create_linux():
    desktop, icon_dest = targets()
    made = []
    png = icon("tickerquill-256.png")
    if png:
        icon_dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(png, icon_dest)
        made.append(icon_dest)
    desktop.parent.mkdir(parents=True, exist_ok=True)
    desktop.write_text("\n".join([
        "[Desktop Entry]", "Type=Application", f"Name={NAME}", "Version=1.5",  # versi spesifikasi .desktop
        "Comment=YouTube stock videos -> Whisper -> structured summary",
        f'Exec="{gui_python()}" -m tickerquill', f"Path={working_dir()}",
        f"Icon={'tickerquill' if png else 'utilities-terminal'}", "Terminal=false", "Categories=Office;Finance;",
        f"StartupWMClass={WM_CLASS}", ""]), encoding="utf-8")
    desktop.chmod(0o755)
    made.insert(0, desktop)
    return made
