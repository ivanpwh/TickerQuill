"""Lokasi berkas. Kode dan aset ada di dalam paket; data pengguna (.env, settings.json, cache, arsip, transkrip, audio)
ada di folder data, yang dipilih sekali saat aplikasi mulai:

1. TICKERQUILL_HOME (atau `tickerquill --data FOLDER`), bila diisi.
2. Folder source checkout (repo ini), bila di sana sudah ada data: instalasi lama tetap memakai datanya.
3. Folder data pengguna OS: %APPDATA%\\TickerQuill, ~/Library/Application Support/TickerQuill, ~/.local/share/tickerquill.
"""
import os
import shutil
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
ASSETS = PACKAGE / "assets"
ICONS = ASSETS / "icon"
SOURCE = PACKAGE.parent  # folder repo bila dijalankan dari source checkout (termasuk `pip install -e .`)
DATA_NAMES = (".env", "settings.json", "cache", "analyses", "transcripts")  # tanda folder yang sudah berisi data
MIGRATE_NAMES = DATA_NAMES  # work/ (audio) tidak disalin: besar dan bisa diunduh ulang


def user_data_dir():
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming") / "TickerQuill"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "TickerQuill"
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "tickerquill"


def is_source_checkout():
    return (SOURCE / "pyproject.toml").exists() and (SOURCE / "tickerquill").is_dir()


def data_dir():
    env = os.environ.get("TICKERQUILL_HOME")
    if env:
        return Path(env).expanduser().resolve()
    if is_source_checkout() and any((SOURCE / n).exists() for n in DATA_NAMES):
        return SOURCE
    return user_data_dir()


def migrate(old, new=None):
    """Salin data dari folder lama ke folder data. Berkas yang sudah ada di tujuan tidak ditimpa.
    Kembalikan daftar berkas yang disalin."""
    old, new = Path(old).expanduser().resolve(), Path(new or data_dir())
    if not old.is_dir():
        raise FileNotFoundError(old)
    if old == new.resolve():
        return []
    copied = []
    for name in MIGRATE_NAMES:
        src = old / name
        files = [src] if src.is_file() else sorted(p for p in src.rglob("*") if p.is_file()) if src.is_dir() else []
        for f in files:
            dest = new / f.relative_to(old)
            if dest.exists():
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dest)
            copied.append(dest)
    return copied
