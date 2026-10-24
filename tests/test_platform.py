"""Platform helpers: system.py, fonts, mouse wheel and shortcuts (no display needed)."""
import types

import pytest

from tickerquill import dashboard
from tickerquill import system
from tickerquill import theme


def test_open_url_only_opens_http_links(monkeypatch):
    opened = []
    monkeypatch.setattr(system.webbrowser, "open", opened.append)
    system.open_url("https://youtu.be/x")
    system.open_url("file:///etc/passwd")
    system.open_url("")
    assert opened == ["https://youtu.be/x"]


def test_open_path_uses_the_os_opener(monkeypatch, tmp_path):
    f = tmp_path / "guide.md"
    f.write_text("x", encoding="utf-8")
    assert system.open_path(tmp_path / "missing.md") is False
    calls = []
    monkeypatch.setattr(system, "IS_WIN", False)
    monkeypatch.setattr(system, "IS_MAC", True)
    monkeypatch.setattr(system.subprocess, "Popen", lambda args, **kw: calls.append(args))
    assert system.open_path(f) is True and calls == [["open", str(f)]]
    monkeypatch.setattr(system, "IS_MAC", False)
    assert system.open_path(f) is True and calls[-1] == ["xdg-open", str(f)]

    def missing(args, **kw):
        raise FileNotFoundError("xdg-open")

    monkeypatch.setattr(system.subprocess, "Popen", missing)
    assert system.open_path(f) is False


def test_gui_python_prefers_pythonw_on_windows_only(monkeypatch, tmp_path):
    exe = tmp_path / "python.exe"
    (tmp_path / "pythonw.exe").write_text("", encoding="utf-8")
    monkeypatch.setattr(system.sys, "executable", str(exe))
    monkeypatch.setattr(system, "IS_WIN", True)
    assert system.gui_python().name == "pythonw.exe"
    monkeypatch.setattr(system, "IS_WIN", False)
    assert system.gui_python() == exe


def test_font_uses_the_platform_monospace():
    assert theme.font(11) == (theme.MONO, 11 + theme.SIZE_DELTA)
    assert theme.font(9, "bold") == (theme.MONO, 9 + theme.SIZE_DELTA, "bold")
    assert theme.FONT_B == theme.font(11, "bold")


@pytest.mark.parametrize("num, delta, mac, expected", [
    (4, 0, False, -1), (5, 0, False, 1),          # Linux/X11 buttons
    (None, 120, False, -1), (None, -240, False, 2),  # Windows
    (None, 30, False, -1),                          # high-resolution wheels still move
    (None, 3, True, -3), (None, -1, True, 1),       # macOS small deltas
])
def test_wheel_steps_per_platform(monkeypatch, num, delta, mac, expected):
    monkeypatch.setattr(dashboard, "IS_MAC", mac)
    assert dashboard.wheel_steps(types.SimpleNamespace(num=num, delta=delta)) == expected


def test_shortcut_modifier_matches_the_platform():
    assert (system.MOD, system.MOD_LABEL) == (("Command", "Cmd") if system.IS_MAC else ("Control", "Ctrl"))
