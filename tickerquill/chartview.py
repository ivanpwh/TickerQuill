"""Grafik candlestick bergaya TradingView (Lightweight Charts) di jendela pywebview, sebagai proses terpisah.

Dijalankan oleh App.open_chart: `python -m tickerquill.chartview <context.json>` (pythonw di Windows). Tk dan pywebview sama-sama butuh main thread,
jadi grafik tidak bisa berjalan di proses aplikasi. Data dari market.py (Yahoo Finance, tertunda ±15 menit); level dan
penanda video berasal dari konteks yang ditulis aplikasi. Modul ini bisa diimpor tanpa pywebview (untuk tes).
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import market, paths
from .system import IS_WIN

ASSETS = Path(__file__).resolve().parent / "assets"
LWC_JS = ASSETS / "lightweight-charts" / "lightweight-charts.standalone.production.js"
DEFAULT_RANGE = "3M"  # candle harian 3 bulan: cukup untuk melihat posisi harga terhadap level dari video
LEVEL_ROLES = {"entry": "AMBER", "target": "GOOD", "stop_loss": "RED"}
_T = {
    "title": ("{s} · grafik candle", "{s} · candle chart"),
    "loading": ("Memuat...", "Loading..."),
    "foot": ("Data: Yahoo Finance (tidak resmi, tertunda ±15 menit) · Grafik: TradingView Lightweight Charts™ · Bukan nasihat investasi.",
             "Data: Yahoo Finance (unofficial, delayed about 15 min) · Chart: TradingView Lightweight Charts™ · Not investment advice."),
    "status": ("update {t} WIB · {state}", "updated {t} WIB · {state}"),
    "open": ("bursa buka, diperbarui tiap 60 detik", "market open, refreshes every 60 s"),
    "closed": ("bursa tutup", "market closed"),
    "not_found": ("{s} tidak ditemukan di Yahoo Finance (ticker mungkin salah dengar).",
                  "{s} was not found on Yahoo Finance (the ticker may be misheard)."),
    "network": ("Gagal mengambil harga: {e}", "Could not fetch the price: {e}"),
    "bad_data": ("Data dari Yahoo Finance tidak terbaca: {e}", "Yahoo Finance returned unreadable data: {e}"),
    "lv_entry": ("beli", "buy"), "lv_target": ("target", "target"), "lv_stop_loss": ("batas rugi", "stop"),
    "no_webview": ("Jendela grafik candle tidak bisa dibuka. Windows: pasang Microsoft Edge WebView2 Runtime. "
                   "Linux: pasang pywebview dengan dukungan Qt (pip install \"pywebview[qt]\") atau GTK. Lihat bagian "
                   "troubleshooting di dokumentasi.\n\n{e}",
                   "The candle chart window could not open. Windows: install the Microsoft Edge WebView2 Runtime. "
                   "Linux: install pywebview with Qt (pip install \"pywebview[qt]\") or GTK support. See the "
                   "troubleshooting page.\n\n{e}"),
}


def t(ui, key, **kw):
    s = _T[key][1 if ui == "EN" else 0]
    return s.format(**kw) if kw else s


def num(x, ui):
    s = f"{x:,.0f}" if abs(x - round(x)) < 1e-9 else f"{x:,.2f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".") if ui != "EN" else s


def bar_date(bar):
    """Tanggal (YYYY-MM-DD) sebuah batang: harian berupa teks, intraday berupa detik yang sudah digeser ke WIB."""
    time = bar["time"]
    return time if isinstance(time, str) else datetime.fromtimestamp(time, timezone.utc).date().isoformat()


def video_markers(bars, videos, colors, labels):
    """Penanda di batang pertama pada/sesudah tanggal tiap video; beberapa video di batang yang sama digabung."""
    by_time = {}
    for v in videos:
        bar = next((b for b in bars if bar_date(b) >= v["date"]), None)
        if bar is None or v["date"] < bar_date(bars[0]):  # di luar rentang yang ditampilkan
            continue
        stance = v["stance"]
        text = f"{labels.get(stance, stance)} {v['date'][8:10]}/{v['date'][5:7]}"
        m = by_time.get(bar["time"])
        if m:
            m["text"] += " · " + text
            continue
        up, down = stance == "BUY", stance in ("SELL", "AVOID")
        by_time[bar["time"]] = {"time": bar["time"], "position": "belowBar" if up else "aboveBar",
                                "shape": "arrowUp" if up else "arrowDown" if down else "circle",
                                "color": colors.get(stance, "#888888"), "text": text}
    return sorted(by_time.values(), key=lambda m: (isinstance(m["time"], str), m["time"]))


class Api:
    """Dipanggil dari JavaScript lewat window.pywebview.api."""

    def __init__(self, ctx):
        self.ctx = ctx
        self.ui = ctx.get("ui", "ID")

    def init(self):
        levels = [{"price": price, "role": LEVEL_ROLES[key], "label": t(self.ui, "lv_" + key)}
                  for key, price in (self.ctx.get("levels") or {}).items() if key in LEVEL_ROLES and price]
        idx = self.ctx["symbol"].endswith(market.SUFFIX)  # harga saham IDX selalu bilangan bulat (rupiah)
        return {"symbol": self.ctx["symbol"], "palette": self.ctx["palette"], "levels": levels,
                "precision": 0 if idx else 2,
                "ranges": list(market.RANGES), "range": DEFAULT_RANGE,
                "strings": {"loading": t(self.ui, "loading"), "foot": t(self.ui, "foot")}}

    def bars(self, rng):
        ui, symbol = self.ui, self.ctx["symbol"]
        try:
            quote = market.parse_chart(market.fetch_chart(symbol, "1d", "5m"))
            data = quote if rng == "1D" else market.parse_chart(market.fetch_chart(symbol, *market.RANGES[rng]))
        except market.MarketError as e:
            return {"error": t(ui, "not_found", s=symbol) if e.kind == "not_found" else t(ui, e.kind, e=e.detail)}
        bars = market.ohlc_bars(data["points"], daily=market.RANGES[rng][1] == "1d")
        change = quote["change"] or 0.0
        pct = f"{quote['change_pct'] or 0:+.2f}%"
        is_open = market.market_open()
        when = quote["time"].strftime("%d/%m %H:%M") if quote["time"] else "-"
        return {"bars": bars,
                "markers": video_markers(bars, self.ctx.get("videos") or [], self.ctx.get("stance_colors") or {},
                                         self.ctx.get("stance_labels") or {}),
                "quote": {"name": quote["name"], "price": num(quote["price"], ui) if quote["price"] else "-",
                          "change": f"{'+' if change >= 0 else ''}{num(change, ui)} ({pct if ui == 'EN' else pct.replace('.', ',')})",
                          "up": change >= 0},
                "open": is_open,
                "status": t(ui, "status", t=when, state=t(ui, "open" if is_open else "closed"))}


def page_html():
    return (ASSETS / "chart.html").read_text(encoding="utf-8").replace(
        "/*LIGHTWEIGHT_CHARTS*/", LWC_JS.read_text(encoding="utf-8"))


def show_error(text):
    """Proses ini berjalan tanpa konsol (pythonw di Windows), jadi kegagalan ditampilkan sebagai kotak pesan Tk."""
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("TickerQuill", text, parent=root)
        root.destroy()
    except Exception:  # tanpa layar/Tk: cukup tulis ke stderr
        sys.stderr.write(text + "\n")


def main(argv):
    ctx = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    ui = ctx.get("ui", "ID")
    try:
        import webview

        webview.create_window(t(ui, "title", s=ctx["symbol"]), html=page_html(), js_api=Api(ctx), width=1040,
                              height=680, min_size=(640, 420), background_color=ctx["palette"]["BG"])
        # Windows: paksa Edge WebView2 (mesin IE lama tidak cukup). macOS: WebKit bawaan. Linux: Qt atau GTK.
        # Ikon jendela hanya bisa diatur pywebview di GTK/Qt (Linux); Windows/macOS memakai ikon interpreter.
        icon = paths.ICONS / "tickerquill-256.png"
        webview.start(gui="edgechromium" if IS_WIN else None,
                      icon=str(icon) if sys.platform.startswith("linux") and icon.exists() else None)
    except Exception as e:  # WebView2 tidak ada, pythonnet gagal, dsb.
        show_error(t(ui, "no_webview", e=f"{type(e).__name__}: {e}"))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
