"""Data folder, migration, command line and app shortcuts (paths.py, __main__.py, shortcuts.py)."""
import plistlib
import subprocess
import sys
from pathlib import Path

import pytest

from tickerquill import __main__ as cli
from tickerquill import __version__, paths, shortcuts


@pytest.fixture
def no_home(monkeypatch):
    monkeypatch.delenv("TICKERQUILL_HOME", raising=False)


def test_data_dir_prefers_env_then_a_source_checkout_with_data_then_the_user_folder(monkeypatch, tmp_path, no_home):
    repo = tmp_path / "repo"
    (repo / "tickerquill").mkdir(parents=True)
    (repo / "pyproject.toml").write_text("", encoding="utf-8")
    monkeypatch.setattr(paths, "SOURCE", repo)
    monkeypatch.setattr(paths, "user_data_dir", lambda: tmp_path / "user")
    assert paths.data_dir() == tmp_path / "user"  # fresh checkout without data
    (repo / "cache").mkdir()
    assert paths.data_dir() == repo  # an existing install keeps its data next to the code
    monkeypatch.setenv("TICKERQUILL_HOME", str(tmp_path / "custom"))
    assert paths.data_dir() == (tmp_path / "custom").resolve()


@pytest.mark.parametrize("platform, env, expected", [
    ("win32", {"APPDATA": "C:/Users/me/AppData/Roaming"}, Path("C:/Users/me/AppData/Roaming/TickerQuill")),
    ("darwin", {}, Path.home() / "Library" / "Application Support" / "TickerQuill"),
    ("linux", {"XDG_DATA_HOME": "/home/me/.data"}, Path("/home/me/.data/tickerquill")),
    ("linux", {}, Path.home() / ".local" / "share" / "tickerquill"),
])
def test_user_data_dir_per_platform(monkeypatch, platform, env, expected):
    monkeypatch.setattr(paths.sys, "platform", platform)
    for key in ("APPDATA", "XDG_DATA_HOME"):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    assert paths.user_data_dir() == expected


def test_migrate_copies_settings_and_history_but_never_overwrites(tmp_path):
    old, new = tmp_path / "old", tmp_path / "new"
    (old / "cache").mkdir(parents=True)
    (old / "work").mkdir()
    (old / ".env").write_text("APP_LANG=EN\n", encoding="utf-8")
    (old / "cache" / "v.id.json").write_text("{}", encoding="utf-8")
    (old / "work" / "v.ogg").write_bytes(b"audio")
    (new).mkdir()
    (new / ".env").write_text("APP_LANG=ID\n", encoding="utf-8")
    copied = paths.migrate(old, new)
    assert copied == [new / "cache" / "v.id.json"]  # .env exists already; audio in work/ is skipped
    assert (new / ".env").read_text(encoding="utf-8") == "APP_LANG=ID\n"
    assert paths.migrate(new, new) == []
    with pytest.raises(FileNotFoundError):
        paths.migrate(tmp_path / "missing", new)


def test_command_line_version_and_where(monkeypatch, capsys, tmp_path, no_home):
    with pytest.raises(SystemExit) as e:
        cli.main(["--version"])
    assert e.value.code == 0 and capsys.readouterr().out.strip() == f"TickerQuill {__version__}"
    assert cli.main(["--data", str(tmp_path), "--where"]) == 0
    assert capsys.readouterr().out.strip() == str(tmp_path.resolve())


def test_python_dash_m_runs_the_command_line(tmp_path):
    out = subprocess.run([sys.executable, "-m", "tickerquill", "--version"], capture_output=True, text=True,
                         cwd=paths.SOURCE, timeout=60)
    assert out.returncode == 0 and out.stdout.strip() == f"TickerQuill {__version__}"


@pytest.fixture
def fake_home(monkeypatch, tmp_path):
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    return tmp_path


def test_mac_shortcut_is_an_app_bundle_that_runs_python_dash_m(monkeypatch, fake_home):
    monkeypatch.setattr(shortcuts, "IS_WIN", False)
    monkeypatch.setattr(shortcuts, "IS_MAC", True)
    [app] = shortcuts.create()
    assert app == fake_home / "Applications" / "TickerQuill.app"
    launcher = (app / "Contents" / "MacOS" / "TickerQuill").read_text(encoding="utf-8")
    assert launcher.startswith("#!/bin/sh") and '-m tickerquill "$@"' in launcher
    info = plistlib.loads((app / "Contents" / "Info.plist").read_bytes())
    assert info["CFBundleExecutable"] == "TickerQuill" and info["CFBundleShortVersionString"] == __version__
    assert shortcuts.remove() == [app] and not app.exists()


def test_linux_shortcut_is_a_desktop_entry(monkeypatch, fake_home):
    monkeypatch.setattr(shortcuts, "IS_WIN", False)
    monkeypatch.setattr(shortcuts, "IS_MAC", False)
    made = shortcuts.create()
    desktop = fake_home / ".local" / "share" / "applications" / "tickerquill.desktop"
    assert made[0] == desktop
    text = desktop.read_text(encoding="utf-8")
    assert "[Desktop Entry]" in text and "-m tickerquill" in text and "StartupWMClass=Tickerquill" in text
    assert "Terminal=false" in text
    assert set(shortcuts.remove()) == set(made)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows shortcuts need PowerShell and WScript.Shell")
def test_windows_shortcut_points_to_pythonw_dash_m(monkeypatch, tmp_path):
    monkeypatch.setattr(shortcuts, "_windows_folders", lambda: [tmp_path / "Programs", tmp_path / "Desktop"])
    made = shortcuts.create()
    assert made == [tmp_path / "Programs" / "TickerQuill.lnk", tmp_path / "Desktop" / "TickerQuill.lnk"]
    read = subprocess.run(["powershell", "-NoProfile", "-Command",
                           f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{made[0]}');"
                           "$s.TargetPath;$s.Arguments;$s.WorkingDirectory"], capture_output=True, text=True, timeout=60)
    target, args, workdir = read.stdout.splitlines()[:3]
    assert Path(target).name.lower() in ("pythonw.exe", "python.exe") and args == "-m tickerquill"
    assert Path(workdir) == shortcuts.working_dir()
    assert shortcuts.remove() == made


def test_icon_files_exist_in_every_format():
    """Read the headers directly: the app and CI do not need Pillow (only tools/make_icon.py does)."""
    import struct

    for size in (16, 32, 48, 64, 128, 256, 512, 1024):
        head = (paths.ICONS / f"tickerquill-{size}.png").read_bytes()[:24]
        assert head[:8] == bytes.fromhex("89504e470d0a1a0a") and struct.unpack(">II", head[16:24]) == (size, size)
    ico = (paths.ICONS / "tickerquill.ico").read_bytes()
    count = struct.unpack("<HHH", ico[:6])[2]
    sizes = {(ico[6 + 16 * i] or 256, ico[7 + 16 * i] or 256) for i in range(count)}  # 0 means 256 in ICO
    assert {(16, 16), (32, 32), (48, 48), (256, 256)} <= sizes
    assert (paths.ICONS / "tickerquill.icns").read_bytes()[:4] == b"icns"

