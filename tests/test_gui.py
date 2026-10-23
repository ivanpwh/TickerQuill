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


def all_widgets(w):
    for child in w.winfo_children():
        yield child
        yield from all_widgets(child)


def test_source_link_is_shown_on_the_dashboard_and_in_the_report(root, monkeypatch):
    opened = []
    monkeypatch.setattr(app, "open_url", opened.append)
    monkeypatch.setattr("dashboard.open_url", opened.append)
    url = "https://youtu.be/abcdefghijk"
    root.q.put(("transcript", ("Video saham", "[00:00:01] BBCA", {"url": url})))
    root.q.put(("report_raw", ('{"stocks": [{"ticker": "BBCA", "stance": "BUY"}]}', "stop")))
    root.poll()
    assert root.data["source"] == {"title": "Video saham", "url": url}

    link = next(w for w in all_widgets(root.dash.inner) if isinstance(w, tk.Label) and url in w.cget("text"))
    root.update()
    link.event_generate("<Button-1>")
    txt = root.panes["ANALISIS"][1]
    start, end = txt.tag_ranges("link")[:2]
    assert txt.get(start, end) == url
    assert txt.get("1.0", "1.end") == "Video saham"
    assert opened == [url]


def test_run_button_and_export_labels_name_what_they_do(root):
    labels = lambda: (root.go_btn.cget("text"), root.copy_btn.cget("text"), root.save_btn.cget("text"))
    before = root.ui_var.get()
    try:
        root.ui_var.set("ID")
        root.apply_lang()
        root.show("DASHBOARD")
        assert labels() == ("[ PROSES ]", "[ SALIN DASHBOARD ]", "[ SIMPAN DASHBOARD ]")
        root.show("ANALISIS")
        assert root.tab_btns["ANALISIS"].cget("text") == "[ HASIL ANALISIS ]"
        assert labels()[1:] == ("[ SALIN HASIL ]", "[ SIMPAN HASIL ]")
        root.ui_var.set("EN")
        root.apply_lang()
        assert labels() == ("[ RUN ]", "[ COPY REPORT ]", "[ SAVE REPORT ]")
        root.show("TRANSKRIP")
        assert labels()[1:] == ("[ COPY TRANSCRIPT ]", "[ SAVE TRANSCRIPT ]")
    finally:
        root.ui_var.set(before)
        root.apply_lang()
        root.show("DASHBOARD")


def test_history_detail_line_shows_and_copies_the_link(root, monkeypatch):
    opened = []
    monkeypatch.setattr(app, "open_url", opened.append)
    url = "https://youtu.be/abcdefghijk"
    done, _ = app.cache_paths("abcdefghijk", "id")
    app.write_json_atomic(done, {"title": "Video saham", "url": url, "vid": "abcdefghijk", "lang": "Indonesia",
                                 "whisper_model": "tiny", "duration": 10, "created": "2026-10-21 12:03",
                                 "transcript": "[00:00:01] BBCA"})
    app.save_file_entry("my notes", "[00:00:01] TLKM", "C:/notes/my notes.txt")
    dialog = app.HistoryDialog(root)
    try:
        assert dialog.d_title.cget("text") == "" and dialog.open_link_btn.cget("state") == "disabled"
        assert dialog.copy_link_btn.cget("state") == "disabled"
        rows = {it["meta"]["title"]: i for i, it in enumerate(dialog.items)}

        dialog.list.selection_set(rows["Video saham"])
        dialog.update_detail()
        assert dialog.d_title.cget("text") == "Video saham" and dialog.d_link.cget("text") == url
        assert dialog.open_link_btn.cget("state") == "normal"
        dialog.open_link()
        dialog.copy_link()
        assert opened == [url] and root.clipboard_get() == url

        dialog.list.selection_clear(0, "end")
        dialog.list.selection_set(rows["my notes"])
        dialog.update_detail()
        assert dialog.d_link.cget("text").endswith("C:/notes/my notes.txt")
        assert dialog.open_link_btn.cget("state") == "disabled"
        dialog.copy_link()
        assert root.clipboard_get() == "C:/notes/my notes.txt"
    finally:
        dialog.destroy()
        for item in app.list_history():
            item["path"].unlink()
