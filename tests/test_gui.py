"""GUI tests. They share ONE Tk root: creating and destroying several roots in one process can make Tcl fail to
initialise again, so no other test module may create a Tk window."""
import json
import tkinter as tk

import pytest

pytest.importorskip("tkinter")
import app  # noqa: E402
import theme  # noqa: E402


@pytest.fixture(scope="module")
def root(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("gui")
    mp = pytest.MonkeyPatch()
    mp.setattr(app, "ENV_FILE", tmp / ".env")
    mp.setattr(app, "SETTINGS_FILE", tmp / "settings.json")
    mp.setattr(app, "CACHE", tmp / "cache")
    (tmp / "cache").mkdir()
    for key in ("NINEROUTER_API_KEY", "APP_LANG", "WHISPER_ENGINE", "COLAB_WHISPER_URL", "COLAB_WHISPER_TOKEN"):
        mp.delenv(key, raising=False)
    try:
        window = app.App()
    except tk.TclError as e:
        mp.undo()
        pytest.skip(f"no display available: {e}")
    yield window
    window.destroy()
    mp.undo()


@pytest.fixture(autouse=True)
def restore_theme():
    before = theme.current
    yield
    theme.apply(before)


def test_recolor_swaps_widget_colours(root):
    theme.apply("dark")
    frame = tk.Frame(root, bg=theme.T.BG)
    label = tk.Label(frame, bg=theme.T.BG, fg=theme.T.AMBER)
    text = tk.Text(frame)
    text.tag_config("x", foreground=theme.T.RED)
    old = theme.apply("light")
    theme.recolor(root, old, theme.palette())
    assert str(frame.cget("bg")).lower() == theme.THEMES["light"]["BG"]
    assert str(label.cget("fg")).lower() == theme.THEMES["light"]["AMBER"]
    assert str(text.tag_cget("x", "foreground")).lower() == theme.THEMES["light"]["RED"]
    frame.destroy()


def test_history_dialog_reanalyses_file_entries_from_the_cached_copy(root, monkeypatch):
    app.save_file_entry("my notes", "[00:00:01] BBCA", "somewhere.txt")
    started = {}
    monkeypatch.setattr(root, "start", lambda **kw: started.update(kw))
    dialog = app.HistoryDialog(root)
    try:
        assert len(dialog.items) == 1 and "my notes" in dialog.list.get(0)
        entry_path = dialog.items[0]["path"]
        dialog.list.selection_set(0)
        dialog.go("auto")
    finally:
        if dialog.winfo_exists():
            dialog.destroy()
    assert started == {"preloaded": ("my notes", "[00:00:01] BBCA"), "mode": "view", "entry": entry_path}
    for item in app.list_history():
        item["path"].unlink()


def test_settings_dialog_changes_theme_and_persists_it(root):
    dialog = app.SettingsDialog(root)
    try:
        dialog.vars["theme"].set(root.tr("theme_light"))
        dialog.save()
        assert theme.current == "light" and theme.T.BG == theme.THEMES["light"]["BG"]
        assert str(root.cget("bg")).lower() == theme.THEMES["light"]["BG"]
        assert json.loads(app.SETTINGS_FILE.read_text(encoding="utf-8"))["theme"] == "light"
        dialog.save()
        assert dialog.info.cget("text") == root.tr("set_nochange")
    finally:
        dialog.destroy()


def test_main_window_summary_shows_unset_model(root):
    root.set_model("")
    assert root.tr("not_set") in root.summary_lbl.cget("text")
    root.set_model("some/model")
    assert "some/model" in root.summary_lbl.cget("text")
