"""GUI tests. They share ONE Tk root: creating and destroying several roots in one process can make Tcl fail to
initialise again, so no other test module may create a Tk window."""
import json
import tkinter as tk

import pytest

pytest.importorskip("tkinter")
from tickerquill import app  # noqa: E402
from tickerquill import theme  # noqa: E402
from tickerquill.system import MOD  # noqa: E402
from tickerquill.widgets import RetroButton  # noqa: E402


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
    monkeypatch.setattr("tickerquill.dashboard.open_url", opened.append)
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
    txt.event_generate(f"<{MOD}-o>")
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


@pytest.fixture
def collection(root):
    """Two videos about TLKM (WATCH then BUY on another day) and a SELL on the same day: a disagreement."""
    import shutil
    from datetime import datetime

    from tickerquill import archive

    def add(vid, date, *stocks, at="2026-10-23 10:00"):
        reply = json.dumps({"summary": "s", "stocks": [{"ticker": tk_, "stance": st, "levels": lv} for tk_, st, lv in stocks]})
        meta = {"title": f"Video {vid}", "url": f"https://youtu.be/{vid}", "vid": vid, "video_date": date,
                "channel": f"Kanal {vid}"}
        archive.save_record(app.ARCHIVE, archive.build_record(reply, "", meta, f"{vid}.id.json", "m",
                                                              datetime.strptime(at, "%Y-%m-%d %H:%M")))

    app.ARCHIVE.mkdir(parents=True, exist_ok=True)
    (app.ARCHIVE / archive.MARKER).write_text("x", encoding="utf-8")
    add("v1", "2026-10-21", ("TLKM", "WATCH", {"entry": "2.100"}), ("BBCA", "BUY", {}))
    add("v2", "2026-10-22", ("TLKM", "BUY", {"entry": "2.060", "target": "2.200"}))
    add("v3", "2026-10-22", ("TLKM", "SELL", {}), ("BBRI", "HOLD", {}))
    root.show_page("collection")
    yield root.pages["collection"]
    root.show_page("analysis")
    shutil.rmtree(app.ARCHIVE, ignore_errors=True)


def texts(widget):
    return [w.cget("text") for w in all_widgets(widget) if isinstance(w, tk.Label)]


def test_collection_lists_dates_and_stocks_with_disagreement(collection):
    page = collection
    assert page.dates.get(0, "end") == (f"{root_tr(page, 'all_dates')} (3)", "2026-10-22  (2)", "2026-10-21  (1)")
    stocks = page.stocks.get(0, "end")
    assert stocks[0].startswith("TLKM") and stocks[0].rstrip().endswith("!") and len(stocks) == 3
    page.dates.selection_clear(0, "end")
    page.dates.selection_set(1)
    page.pick_day()
    assert [s.split()[0] for s in page.stocks.get(0, "end")] == ["TLKM", "BBRI"]
    shown = texts(page.view.inner)
    assert any("Video v2" in x for x in shown) and any("Video v3" in x for x in shown)
    assert root_tr(page, "disagree") in shown  # TLKM: BUY in v2, SELL in v3 on the same day


def root_tr(page, key):
    from tickerquill import collection as col

    return col.t(page.ui, key)


def test_collection_stock_detail_shows_consensus_zone_and_changes(collection):
    from tickerquill import collection as col

    page = collection
    page.select_ticker("TLKM")
    shown = " | ".join(texts(page.view.inner))
    assert col.t(page.ui, "conflict") in shown
    assert "TLKM" in shown and "3" in shown
    assert "2.060" in shown or "2,060" in shown  # buy-price zone
    assert col.t(page.ui, "t_changes") in shown
    page.clear_ticker()
    assert page.ticker is None


def test_collection_ai_summary_is_requested_once_and_cached(collection, root, monkeypatch):
    import time

    from tickerquill import collection as col

    calls = []
    monkeypatch.setattr(root, "llm_ready", lambda: True)
    monkeypatch.setattr(root, "llm_complete", lambda system, user: calls.append(user) or "- semua membahas TLKM")
    page = collection
    page.select_ticker("TLKM")
    button = next(w for w in all_widgets(page.view.inner)
                  if isinstance(w, RetroButton) and w.cget("text") == col.t(page.ui, "ai_btn"))
    button.invoke()
    for _ in range(100):
        root.update()
        if page.ai_running is None:
            break
        time.sleep(0.02)
    assert len(calls) == 1 and all(f'"{s}"' in calls[0] for s in ("WATCH", "BUY", "SELL"))  # extracted data only
    assert "- semua membahas TLKM" in texts(page.view.inner)
    assert len(list((app.ARCHIVE / "ai").glob("ticker-TLKM-*.json"))) == 1
    page.render()
    assert not any(isinstance(w, RetroButton) and w.cget("text") == col.t(page.ui, "ai_btn")
                   for w in all_widgets(page.view.inner))


def test_collection_open_record_without_history_entry_says_so(collection):
    from tickerquill import collection as col

    page = collection
    page.open_record(page.records[0])
    assert page.info.cget("text") == col.t(page.ui, "missing_entry")


def test_collection_imports_saved_analyses_from_history_once(root):
    import shutil

    from tickerquill import archive

    done, _ = app.cache_paths("abcdefghijk", "id")
    app.write_json_atomic(done, {"title": "Lama", "url": "https://youtu.be/abcdefghijk", "vid": "abcdefghijk",
                                 "lang": "Indonesia", "whisper_model": "tiny", "duration": 1, "created": "2026-10-21 09:00",
                                 "transcript": "BBCA", "analysis": '{"stocks": [{"ticker": "BBCA", "stance": "BUY"}]}'})
    try:
        root.show_page("collection")
        page = root.pages["collection"]
        assert [r["vid"] for r in page.records] == ["abcdefghijk"]
        assert (app.ARCHIVE / archive.MARKER).exists()
    finally:
        root.show_page("analysis")
        done.unlink()
        shutil.rmtree(app.ARCHIVE, ignore_errors=True)


@pytest.fixture
def fake_market(monkeypatch):
    """Yahoo stand-in: TLKM.JK at 2.240 (prev 2.200); daily history 20-23/10; anything else is not found."""
    from datetime import datetime as dt

    from tickerquill import market

    def chart(stamps, closes, highs, lows, price=2240.0):
        return {"chart": {"result": [{"meta": {"symbol": "TLKM.JK", "shortName": "Telkom Indonesia", "currency": "IDR",
                                               "regularMarketPrice": price, "previousClose": 2200.0,
                                               "regularMarketDayHigh": 2250.0, "regularMarketDayLow": 2160.0,
                                               "regularMarketVolume": 238905400, "regularMarketTime": stamps[-1]},
                                      "timestamp": stamps, "indicators": {"quote": [{"close": closes, "high": highs,
                                                                                     "low": lows}]}}]}}

    days = [int(dt(2026, 10, d, 9, tzinfo=market.WIB).timestamp()) for d in (20, 21, 22, 23)]
    calls = []

    def fetch(symbol, rng="1d", interval="5m", timeout=15):
        calls.append((symbol, rng))
        if symbol != "TLKM.JK":
            raise market.MarketError("not_found", symbol)
        if rng == "1d":
            return chart([days[-1], days[-1] + 300], [2230.0, 2240.0], [2235.0, 2250.0], [2160.0, 2230.0])
        return chart(days, [2060.0, 2180.0, 2200.0, 2240.0], [2070.0, 2190.0, 2210.0, 2250.0],
                     [2040.0, 2100.0, 2170.0, 2160.0])

    monkeypatch.setattr(market, "fetch_chart", fetch)
    monkeypatch.setattr(market, "market_open", lambda now=None: False)  # no 60 s refresh timer in tests
    return calls


def wait_loaded(root, window):
    import time

    for _ in range(200):
        root.update()
        if not window.loading:
            return
        time.sleep(0.01)
    raise AssertionError("price window did not finish loading")


def test_stock_window_shows_price_chart_levels_and_move_since_video(root, fake_market):
    ctx = {"levels": {"entry": 2080.0, "target": 2200.0, "stop_loss": 1985.0},
           "videos": [{"date": "2026-10-20", "title": "14 Saham Rebound", "stance": "BUY",
                       "prices": {"entry": None, "target": 2200.0, "stop_loss": 1985.0}}]}
    w = root.open_stock("tlkm", ctx)
    try:
        wait_loaded(root, w)
        assert w.symbol == "TLKM.JK" and w.price_lbl.cget("text") in ("2.240", "2,240")
        assert w.change_lbl.cget("text").startswith("+40")
        shown = [x.cget("text") for x in w.since.winfo_children()]
        assert any(x.startswith(("2.060 -> 2.240", "2,060 -> 2,240")) for x in shown)
        assert any(x in ("2.200 tersentuh", "2,200 hit") for x in shown)  # target reached after the video
        assert any(x in ("1.985 aman", "1,985 not hit") for x in shown)  # loss limit never touched
        assert w.canvas.find_all() and "1985" not in w.legend_lbl.cget("text")
        assert ("TLKM.JK", "1y") in fake_market
        assert root.open_stock("TLKM", ctx) is w  # same symbol: same window
    finally:
        w.close()


def test_stock_window_explains_an_unknown_ticker(root, fake_market):
    from tickerquill import stockview

    w = root.open_stock("ZZZQ", {})
    try:
        wait_loaded(root, w)
        assert w.msg_lbl.cget("text") == stockview.t(root.ui, "not_found", s="ZZZQ.JK")
        assert w.price_lbl.cget("text") == ""
    finally:
        w.close()


def test_dashboard_ticker_opens_the_price_window_with_its_levels(root, monkeypatch):
    opened = []
    monkeypatch.setattr(root, "open_stock", lambda ticker, ctx: opened.append((ticker, ctx)))
    root.q.put(("transcript", ("Video", "BBCA", {"url": "https://youtu.be/x", "video_date": "2026-10-21"})))
    root.q.put(("report_raw", ('{"stocks": [{"ticker": "BBCA", "stance": "BUY", "levels": {"entry": "9.000", '
                               '"target": "9.500", "stop_loss": "8.800"}}]}', "stop")))
    root.poll()
    root.update()
    label = next(x for x in all_widgets(root.dash.inner) if isinstance(x, tk.Label) and x.cget("text") == "BBCA")
    label.event_generate("<Button-1>")
    [(ticker, ctx)] = opened
    assert ticker == "BBCA" and ctx["levels"] == {"entry": 9000.0, "target": 9500.0, "stop_loss": 8800.0}
    assert ctx["videos"][0]["date"] == "2026-10-21" and ctx["videos"][0]["stance"] == "BUY"


def test_market_overview_is_in_the_view_menu_and_is_the_start_page(collection, root):
    from tickerquill import archive

    bar = root.menubar.bar
    labels = [bar.entrycget(i, "label") for i in range(bar.index("end") + 1)]
    assert labels == [root.tr(k) for k in ("m_file", "m_view", "m_job", "m_tools", "m_help")]  # no extra top item
    root.show_page("analysis")
    menu, i = menu_entry(root, "m_view", root.tr("m_overview"))
    menu.invoke(i)
    assert root.page == "collection" and root.page_lbl.cget("text").endswith(root.tr("page_collection"))
    root.show_page("analysis")
    root.start_page()
    assert root.page == "collection"  # saved analyses exist
    for rec in collection.records:
        archive.delete_video(app.ARCHIVE, rec["vid"])
    root.start_page()
    assert root.page == "analysis"  # nothing to show yet


def test_price_window_uses_international_ranges_and_opens_tradingview(root, fake_market, monkeypatch):
    from tickerquill import stockview

    opened = []
    monkeypatch.setattr(stockview, "open_url", opened.append)
    w = root.open_stock("TLKM", {})
    try:
        wait_loaded(root, w)
        assert [b.cget("text") for b in w.range_btns.values()] == ["[ 1Y ]", "[ 3M ]", "[ 1M ]", "[ 5D ]", "[ 1D ]"]
        button = next(x for x in all_widgets(w) if isinstance(x, RetroButton) and x.cget("text") == "[ TRADINGVIEW ]")
        button.invoke()
        assert opened == ["https://www.tradingview.com/chart/?symbol=IDX%3ATLKM"]
    finally:
        w.close()


def test_overview_stock_detail_links_to_tradingview(collection, monkeypatch):
    from tickerquill import collection as col

    opened = []
    monkeypatch.setattr(col, "open_url", opened.append)
    collection.select_ticker("TLKM")
    button = next(x for x in all_widgets(collection.view.inner)
                  if isinstance(x, RetroButton) and x.cget("text") == "[ TRADINGVIEW ]")
    button.invoke()
    assert opened == ["https://www.tradingview.com/chart/?symbol=IDX%3ATLKM"]


def test_candle_chart_runs_in_its_own_process_with_the_window_context(root, monkeypatch, tmp_path):
    import importlib.util
    import subprocess

    launched = []

    class Proc:
        def __init__(self, args, **kw):
            launched.append((args, kw))
            self.alive = True

        def poll(self):
            return None if self.alive else 0

        def terminate(self):
            self.alive = False

    monkeypatch.setattr(subprocess, "Popen", Proc)
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: object())
    monkeypatch.setattr(app.tempfile, "gettempdir", lambda: str(tmp_path))
    ctx = {"levels": {"entry": 2080.0}, "videos": [{"date": "2026-10-20", "stance": "BUY", "title": "v", "prices": {}}]}
    first = root.open_chart("tlkm", ctx)
    args, kw = launched[0]
    assert args[1:3] == ["-m", "tickerquill.chartview"] and kw["cwd"] in (app.paths.SOURCE, None)
    saved = json.loads((tmp_path / "tickerquill-chart-TLKM.JK.json").read_text(encoding="utf-8"))
    assert saved["symbol"] == "TLKM.JK" and saved["levels"] == {"entry": 2080.0} and saved["videos"] == ctx["videos"]
    from tickerquill import report

    assert saved["palette"]["BG"] == theme.T.BG and saved["stance_labels"]["BUY"] == report.t(root.ui, "stance_BUY")
    second = root.open_chart("TLKM", ctx)
    assert first.alive is False and second.alive is True and len(launched) == 2  # same symbol: replaced
    root.chart_procs.clear()


def test_candle_chart_explains_a_missing_pywebview(root, monkeypatch):
    import importlib.util

    shown = []
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: None)
    monkeypatch.setattr(app.messagebox, "showinfo", lambda title, text, **kw: shown.append(text))
    assert root.open_chart("TLKM", {}) is None
    assert shown == [root.tr("chart_missing")]


def test_retro_button_behaves_like_a_button(root):
    calls = []
    b = RetroButton(root, "[ OK ]", lambda: calls.append(1))
    b.invoke()
    b.config(state="disabled")
    b.invoke()
    assert calls == [1] and b["state"] == "disabled" and b.cget("text") == "[ OK ]"
    b.config(state="normal")
    b.pack()
    root.update()
    b.event_generate("<Enter>")
    assert str(b.cget("bg")).lower() == theme.T.FG.lower()  # hover: inverted colours, also on macOS
    b.event_generate("<Leave>")
    assert str(b.cget("bg")).lower() == theme.T.BG.lower()
    b.destroy()


def test_tools_menu_creates_the_app_shortcut(root, monkeypatch, tmp_path):
    assert root.winfo_class() == app.shortcuts.WM_CLASS  # Linux matches the window to its shortcut by this
    shown = []
    monkeypatch.setattr(app.shortcuts, "create", lambda: [tmp_path / "TickerQuill.lnk"])
    monkeypatch.setattr(app.messagebox, "showinfo", lambda title, text, **kw: shown.append(text))
    menu, i = menu_entry(root, "m_tools", root.tr("mi_shortcut"))
    menu.invoke(i)
    assert len(shown) == 1 and str(tmp_path / "TickerQuill.lnk") in shown[0]

    def blocked():
        raise PermissionError("denied")

    errors = []
    monkeypatch.setattr(app.shortcuts, "create", blocked)
    monkeypatch.setattr(app.messagebox, "showerror", lambda title, text, **kw: errors.append(text))
    menu.invoke(i)
    assert errors and "PermissionError: denied" in errors[0]
