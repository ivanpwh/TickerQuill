"""Tema warna. Kode lain membaca warna lewat T (T.BG, T.FG, ...) saat widget dibuat.
Ganti tema: apply(nama) mengembalikan palet lama, lalu recolor(root, lama, baru) mewarnai ulang widget yang ada.
Peran warna: BG latar, FG teks utama, DIM teks redup/garis, AMBER judul/aksen, RED negatif, CYAN info, GOOD positif.
Tiap tema harus memakai nilai hex berbeda untuk BG, FG, DIM, AMBER, RED, CYAN (GOOD boleh sama dengan FG)."""
import sys
import tkinter as tk

THEMES = {
    "retro_green": {"BG": "#0a0f0a", "FG": "#38ff6a", "DIM": "#1c7a36", "AMBER": "#ffb000", "RED": "#ff5555",
                    "CYAN": "#4dd0e1", "GOOD": "#38ff6a"},
    "retro_amber": {"BG": "#140d00", "FG": "#ffb000", "DIM": "#8a6000", "AMBER": "#ffe08a", "RED": "#ff6b5a",
                    "CYAN": "#7fd1ff", "GOOD": "#9be564"},
    "dark": {"BG": "#14161a", "FG": "#e6e8eb", "DIM": "#8b929c", "AMBER": "#f5b84b", "RED": "#ef6b6b",
             "CYAN": "#5bb5f5", "GOOD": "#4cc38a"},
    "light": {"BG": "#f7f8fa", "FG": "#1f2328", "DIM": "#6b7380", "AMBER": "#9a5b00", "RED": "#c62828",
              "CYAN": "#0b6fb8", "GOOD": "#1b7f4b"},
}
CHOICES = [*THEMES, "system"]  # "system" = ikuti mode gelap/terang OS saat aplikasi dibuka
DEFAULT = "retro_green"
ROLES = tuple(THEMES[DEFAULT])

# Monospace bawaan tiap OS. Di Linux "monospace" adalah alias fontconfig (DejaVu/Liberation/Noto Sans Mono, ...).
MONO = {"win32": "Consolas", "darwin": "Menlo"}.get(sys.platform, "monospace")
SIZE_DELTA = 2 if sys.platform == "darwin" else 0  # Tk di macOS menghitung 72 dpi: ukuran sama tampak lebih kecil


def font(size, *style):
    """Font aplikasi: (keluarga monospace OS ini, ukuran, gaya...)."""
    return (MONO, size + SIZE_DELTA, *style)


FONT = font(11)
FONT_B = font(11, "bold")
FONT_BIG = font(16, "bold")

COLOR_OPTIONS = ("bg", "fg", "activebackground", "activeforeground", "disabledforeground", "highlightbackground",
                 "highlightcolor", "insertbackground", "selectbackground", "selectforeground", "troughcolor",
                 "disabledbackground", "readonlybackground")


class Palette:
    """Palet yang sedang aktif; atribut diisi apply()."""


T = Palette()
current = DEFAULT


def system_is_dark():
    try:
        if sys.platform == "win32":
            import winreg

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as k:
                return winreg.QueryValueEx(k, "AppsUseLightTheme")[0] == 0
        if sys.platform == "darwin":
            import subprocess

            out = subprocess.run(["defaults", "read", "-g", "AppleInterfaceStyle"], capture_output=True, text=True)
            return out.stdout.strip() == "Dark"
        if sys.platform.startswith("linux"):  # GNOME dan turunannya; desktop lain: anggap gelap (bawaan aplikasi)
            import subprocess

            def gsetting(key):
                out = subprocess.run(["gsettings", "get", "org.gnome.desktop.interface", key], capture_output=True,
                                     text=True, timeout=3)
                return out.stdout.strip().strip("'").lower()

            scheme = gsetting("color-scheme")
            if scheme in ("prefer-dark", "prefer-light"):
                return scheme == "prefer-dark"
            return "dark" in gsetting("gtk-theme")
    except Exception:
        pass
    return True


def resolve(name):
    """Nama tema valid; 'system' menjadi dark/light sesuai OS."""
    if name == "system":
        return "dark" if system_is_dark() else "light"
    return name if name in THEMES else DEFAULT


def palette(name=None):
    return {role: getattr(T, role) for role in ROLES} if name is None else dict(THEMES[resolve(name)])


def apply(name):
    """Aktifkan tema; kembalikan palet sebelumnya (untuk recolor)."""
    global current
    old = palette() if hasattr(T, "BG") else None
    current = name if name in CHOICES else DEFAULT
    for role, value in THEMES[resolve(current)].items():
        setattr(T, role, value)
    return old


def mix(a, b, t):
    """Campur dua warna hex: t=0 -> a, t=1 -> b."""
    ca = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    cb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(ca, cb))


def recolor(root, old, new):
    """Ganti setiap opsi warna widget (rekursif) yang bernilai warna palet lama dengan warna peran yang sama."""
    mapping = {}
    for role in ROLES:
        mapping.setdefault(old[role].lower(), new[role])  # peran pertama menang bila hex kembar (FG vs GOOD)

    def conv(value):
        return mapping.get(str(value).lower())

    def walk(w):
        if isinstance(w, tk.Menu):  # menu bar bawaan Windows memakai warna sistem, tidak ikut tema
            return
        for opt in COLOR_OPTIONS:
            try:
                new_value = conv(w.cget(opt))
            except tk.TclError:
                continue
            if new_value:
                w.configure(**{opt: new_value})
        if isinstance(w, tk.Text):
            for tag in w.tag_names():
                for opt in ("foreground", "background"):
                    new_value = conv(w.tag_cget(tag, opt))
                    if new_value:
                        w.tag_configure(tag, **{opt: new_value})
        for child in w.winfo_children():
            walk(child)

    walk(root)


apply(DEFAULT)
