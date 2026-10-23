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
    mp.setattr(app, "ARCHIVE", tmp / "analyses")
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


def test_history_page_reanalyses_file_entries_from_the_cached_copy(root, monkeypatch):
    app.save_file_entry("my notes", "[00:00:01] BBCA", "somewhere.txt")
    started = {}
    monkeypatch.setattr(root, "start", lambda **kw: started.update(kw))
    root.show_page("history")
    page = root.pages["history"]
    try:
        assert len(page.items) == 1 and "my notes" in page.list.get(0)
        entry_path = page.items[0]["path"]
        page.list.selection_set(0)
        page.go("auto")
    finally:
        root.show_page("analysis")
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
    root.show_page("history")
    dialog = root.pages["history"]
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
        root.show_page("analysis")
        for item in app.list_history():
            item["path"].unlink()


def menu_entry(root, menu_key, label):
    """(menu, index) of the item whose label starts with `label` in the cascade named by STR key `menu_key`."""
    bar = root.menubar.bar
    for i in range(bar.index("end") + 1):
        if bar.entrycget(i, "label") == root.tr(menu_key):
            menu = root.nametowidget(bar.entrycget(i, "menu"))
            for j in range(menu.index("end") + 1):
                if menu.type(j) != "separator" and menu.entrycget(j, "label").startswith(label):
                    return menu, j
    raise AssertionError(f"no menu item {label!r} under {menu_key}")


def test_pages_switch_from_the_menu_and_keep_the_title_in_sync(root):
    menu, i = menu_entry(root, "m_view", root.tr("page_history").capitalize())
    menu.invoke(i)
    assert root.page == "history" and root.pages["history"].winfo_ismapped() is not None
    assert root.page_lbl.cget("text").endswith(root.tr("page_history"))
    menu, i = menu_entry(root, "m_view", root.tr("transcript_tab").capitalize())
    menu.invoke(i)
    assert root.page == "analysis" and root.current == "TRANSKRIP"
    root.show("DASHBOARD")


def test_job_indicator_shows_progress_and_result_on_other_pages(root):
    root.go_btn.config(state="disabled")  # as start() does while a job runs
    try:
        root.last_status = ("s_tr", 45, "")
        root.render_status()
        assert root.job_lbl.cget("text") == ""  # ANALYSIS page: the status row already shows it
        root.show_page("history")
        assert root.job_lbl.cget("text").startswith("● ") and root.job_lbl.cget("text").endswith("45%")
    finally:
        root.finish()
    assert root.job_lbl.cget("text").startswith("✓ ")
    root.show_page("analysis")
    assert root.job_lbl.cget("text") == "" and root.job_mark is None
    root.last_status = None
    root.render_status()


def test_menu_state_and_labels_follow_the_job_and_language(root):
    run_label = root.tr("analyze").strip("[] ").capitalize()
    run, i = menu_entry(root, "m_job", run_label)
    cancel, c = menu_entry(root, "m_job", root.tr("cancel").strip("[] ").capitalize())
    root.refresh_menu()
    assert run.entrycget(i, "state") == "normal" and cancel.entrycget(c, "state") == "disabled"
    root.go_btn.config(state="disabled")
    try:
        root.refresh_menu()
        assert run.entrycget(i, "state") == "disabled" and cancel.entrycget(c, "state") == "normal"
    finally:
        root.go_btn.config(state="normal")
        root.refresh_menu()

    root.show("TRANSKRIP")
    root.clear("TRANSKRIP")
    copy, k = menu_entry(root, "m_file", root.copy_btn.cget("text").strip("[] ").capitalize())
    root.refresh_menu()
    assert copy.entrycget(k, "state") == "disabled"  # nothing to copy yet
    root.write("TRANSKRIP", "text")
    root.refresh_menu()
    assert copy.entrycget(k, "state") == "normal"
    root.clear("TRANSKRIP")
    root.show("DASHBOARD")

    before = root.ui
    try:
        root.ui_var.set("EN")
        root.apply_lang()
        assert root.menubar.bar.entrycget(2, "label") == "Job"
        menu_entry(root, "m_file", "Copy dashboard")
    finally:
        root.ui_var.set(before)
        root.apply_lang()


def test_language_and_theme_radio_items_apply_and_persist(root):
    before_ui, before_theme = root.ui, theme.current
    lang = root.nametowidget(menu_entry(root, "m_view", root.tr("mi_lang"))[0].entrycget(
        menu_entry(root, "m_view", root.tr("mi_lang"))[1], "menu"))
    try:
        lang.invoke(1)  # English
        assert root.ui == "EN" and "APP_LANG=EN" in app.ENV_FILE.read_text(encoding="utf-8")
        assert root.go_btn.cget("text") == "[ RUN ]"
        menu, i = menu_entry(root, "m_view", root.tr("mi_theme"))
        themes = root.nametowidget(menu.entrycget(i, "menu"))
        themes.invoke(theme.CHOICES.index("light"))
        assert theme.current == "light" and root.theme_var.get() == "light"
        assert json.loads(app.SETTINGS_FILE.read_text(encoding="utf-8"))["theme"] == "light"
    finally:
        root.set_lang(before_ui)
        root.set_theme(before_theme)


def test_ctrl_o_in_a_text_pane_opens_the_file_dialog_once_without_editing(root, monkeypatch):
    calls = []
    monkeypatch.setattr(app.filedialog, "askopenfilename", lambda **kw: calls.append(kw) or "")
    txt = root.panes["TRANSKRIP"][1]
    root.show("TRANSKRIP")
    root.clear("TRANSKRIP")
    txt.insert("1.0", "abc")
    txt.mark_set("insert", "1.1")
    root.update()
    txt.focus_force()
    root.update()
    txt.event_generate("<Control-o>")
    root.update()
    assert len(calls) == 1 and txt.get("1.0", "end-1c") == "abc"
    root.clear("TRANSKRIP")
    root.show("DASHBOARD")


def test_history_page_stays_open_with_a_busy_message_while_a_job_runs(root, monkeypatch):
    app.save_file_entry("busy notes", "[00:00:01] BBCA", "x.txt")
    started = []
    monkeypatch.setattr(root, "start", lambda **kw: started.append(kw))
    root.show_page("history")
    page = root.pages["history"]
    root.go_btn.config(state="disabled")
    try:
        page.list.selection_set(0)
        page.go("auto")
        assert started == [] and root.page == "history"
        assert page.info.cget("text") == root.tr("busy")
    finally:
        root.go_btn.config(state="normal")
        root.show_page("analysis")
        for item in app.list_history():
            item["path"].unlink()
