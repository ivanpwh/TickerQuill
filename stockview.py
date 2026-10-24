"""Jendela harga saham: harga terakhir, grafik dengan level dari video, dan pergerakan sejak tiap video.

Data dari market.py (Yahoo Finance, tertunda ±15 menit), diambil di thread dan diperbarui tiap 60 detik selama bursa
buka. Konteks (level yang digambar, daftar video) diberikan oleh pembuka: kartu Dashboard atau halaman RINGKASAN PASAR.
"""
import threading
import tkinter as tk

import market
import report
from dashboard import open_url
from theme import FONT, FONT_B, FONT_BIG, T, font, mix

REFRESH_MS = 60_000
LEVEL_ROLES = {"entry": "AMBER", "target": "GOOD", "stop_loss": "RED"}
_T = {
    "title": ("Harga {s}", "{s} price"), "candle": ("[ GRAFIK CANDLE ]", "[ CANDLE CHART ]"), "symbol": ("SIMBOL>", "SYMBOL>"), "go": ("[ CARI ]", "[ GO ]"),
    "reload": ("[ MUAT ULANG ]", "[ RELOAD ]"),
    "loading": ("Memuat harga {s}...", "Loading {s}..."),
    "stats": ("tinggi {h} · rendah {l} · volume {v}", "high {h} · low {l} · volume {v}"),
    "time": ("update {t} WIB · tertunda ±15 menit (Yahoo Finance) · {state}",
             "updated {t} WIB · delayed about 15 min (Yahoo Finance) · {state}"),
    "open": ("bursa buka, diperbarui otomatis tiap 60 detik", "market open, refreshes every 60 s"),
    "closed": ("bursa tutup", "market closed"),
    "not_found": ("{s} tidak ditemukan di Yahoo Finance. Ticker mungkin salah dengar; perbaiki di kolom SIMBOL lalu tekan CARI.",
                  "{s} was not found on Yahoo Finance. The ticker may be misheard; correct it in SYMBOL and press GO."),
    "network": ("Gagal mengambil harga: {e}. Cek koneksi lalu tekan MUAT ULANG.",
                "Could not fetch the price: {e}. Check the connection and press RELOAD."),
    "bad_data": ("Data dari Yahoo Finance tidak terbaca: {e}", "Yahoo Finance returned unreadable data: {e}"),
    "stale": (" Data terakhir yang berhasil tetap ditampilkan.", " The last good data is still shown."),
    "lv_entry": ("beli", "buy"), "lv_target": ("target", "target"), "lv_stop_loss": ("batas rugi", "stop"),
    "off_chart": ("Di luar grafik: {list}", "Off the chart: {list}"),
    "no_data": ("Tidak ada data untuk rentang ini.", "No data for this range."),
    "t_since": ("SEJAK VIDEO", "SINCE THE VIDEO"),
    "c_date": ("TANGGAL", "DATE"), "c_video": ("VIDEO", "VIDEO"), "c_stance": ("SIKAP", "STANCE"),
    "c_move": ("SAAT VIDEO -> SEKARANG", "AT VIDEO -> NOW"), "c_target": ("TARGET", "TARGET"),
    "c_stop": ("BATAS RUGI", "LOSS LIMIT"),
    "hit": ("tersentuh", "hit"), "safe": ("aman", "not hit"), "no_since": ("belum ada data", "no data yet"),
    "no_dates": ("Tanggal video belum diketahui, jadi pergerakan sejak video tidak bisa dihitung. Lengkapi tanggal di halaman RINGKASAN PASAR.",
                 "The video date is unknown, so the move since the video cannot be computed. Fill in dates on the MARKET OVERVIEW page."),
    "fallback": ("* tanggal analisis (tanggal upload belum ada)", "* analysis date (no upload date yet)"),
    "disclaimer": ("! Harga dari Yahoo Finance (tidak resmi, tertunda ±15 menit). Bukan nasihat investasi.",
                   "! Prices from Yahoo Finance (unofficial, delayed about 15 min). Not investment advice."),
    "million": ("{x} jt", "{x}M"),
}


def t(ui, key, **kw):
    s = _T[key][1 if ui == "EN" else 0]
    return s.format(**kw) if kw else s


class StockWindow(tk.Toplevel):
    def __init__(self, app, ticker, context):
        super().__init__(app)
        self.app, self.context = app, context or {}
        self.symbol = market.symbol_for(ticker)
        self.range = "1D"
        self.quote, self.points, self.daily = None, [], None
        self.error = None
        self.result = None  # hasil thread: ("ok", data) | ("err", MarketError)
        self.loading = False
        self.auto_id = None
        self.configure(bg=T.BG)
        self.geometry("960x700")

        top = tk.Frame(self, bg=T.BG)
        top.pack(fill="x", padx=12, pady=(12, 4))
        self.symbol_lbl = tk.Label(top, text="", font=FONT_B, bg=T.BG, fg=T.FG)
        self.symbol_lbl.pack(side="left")
        self.symbol_var = tk.StringVar(value=self.symbol)
        entry = tk.Entry(top, textvariable=self.symbol_var, font=FONT, width=12, bg=T.BG, fg=T.FG, insertbackground=T.FG,
                         relief="flat", highlightthickness=1, highlightbackground=T.DIM, highlightcolor=T.FG)
        entry.pack(side="left", padx=6, ipady=2)
        entry.bind("<Return>", lambda e: self.change_symbol())
        self.go_btn = app.button(top, "", self.change_symbol)
        self.go_btn.pack(side="left")
        app.button(top, "[ TRADINGVIEW ]", self.open_tradingview).pack(side="left", padx=(6, 0))
        self.candle_btn = app.button(top, "", lambda: app.open_chart(self.symbol, self.context))
        self.candle_btn.pack(side="left", padx=(6, 0))
        self.reload_btn = app.button(top, "", lambda: self.load(full=True))
        self.reload_btn.pack(side="right")
        self.range_btns = {}
        for key in reversed(list(market.RANGES)):  # 1D 5D 1M 3M 1Y: konvensi TradingView di kedua bahasa
            b = app.button(top, f"[ {key} ]", lambda k=key: self.set_range(k))
            b.pack(side="right", padx=(0, 4))
            self.range_btns[key] = b

        self.name_lbl = self.line(FONT_B, T.AMBER, pady=(6, 0))
        row = tk.Frame(self, bg=T.BG)
        row.pack(fill="x", padx=12)
        self.price_lbl = tk.Label(row, text="", font=FONT_BIG, bg=T.BG, fg=T.FG, anchor="w")
        self.price_lbl.pack(side="left")
        self.change_lbl = tk.Label(row, text="", font=FONT_B, bg=T.BG, fg=T.FG, anchor="w")
        self.change_lbl.pack(side="left", padx=12)
        self.stats_lbl = tk.Label(row, text="", font=FONT, bg=T.BG, fg=T.DIM, anchor="w")
        self.stats_lbl.pack(side="left", padx=12)
        self.time_lbl = self.line(FONT, T.DIM)
        self.msg_lbl = self.line(FONT, T.RED)
        self.canvas = tk.Canvas(self, height=260, bg=T.BG, highlightthickness=1, highlightbackground=T.DIM)
        self.canvas.pack(fill="x", padx=12, pady=(6, 2))
        self.canvas.bind("<Configure>", lambda e: self.draw_chart())
        self.legend_lbl = self.line(FONT, T.DIM)
        self.since_title = self.line(FONT_B, T.AMBER, pady=(8, 2))
        self.since = tk.Frame(self, bg=T.BG)
        self.since.pack(fill="x", padx=12)
        self.disclaimer_lbl = self.line(font(9), T.DIM, pady=(8, 8))
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.apply_lang()
        self.load(full=True)

    def line(self, font, fg, pady=0):
        lbl = tk.Label(self, text="", font=font, bg=T.BG, fg=fg, anchor="w", justify="left", wraplength=930)
        lbl.pack(fill="x", padx=12, pady=pady)
        return lbl

    @property
    def ui(self):
        return self.app.ui

    def num(self, x):
        return report.fmt_num(x, self.ui) if x is not None else "-"

    def short(self, x):
        """238.9 -> '238,9' (ID) / '238.9' (EN); angka bulat tanpa desimal."""
        s = f"{x:.1f}".rstrip("0").rstrip(".")
        return s.replace(".", ",") if self.ui != "EN" else s

    def pct(self, x):
        s = f"{x:+.2f}%"
        return s.replace(".", ",") if self.ui != "EN" else s

    def apply_lang(self):
        self.title(t(self.ui, "title", s=self.symbol))
        self.symbol_lbl.config(text=t(self.ui, "symbol"))
        self.go_btn.config(text=t(self.ui, "go"))
        self.candle_btn.config(text=t(self.ui, "candle"))
        self.reload_btn.config(text=t(self.ui, "reload"))
        self.app.mark_tabs(self.range_btns, self.range)
        self.disclaimer_lbl.config(text=t(self.ui, "disclaimer"))
        self.render()

    # --- data ------------------------------------------------------------------------------------------------------
    def set_context(self, context):
        self.context = context or {}
        self.render()
        if self.context.get("videos") and self.daily is None and not self.loading:
            self.load(full=True)  # data harian untuk 'sejak video' belum pernah diambil

    def set_range(self, key):
        self.range = key
        self.app.mark_tabs(self.range_btns, key)
        self.load()

    def open_tradingview(self):
        open_url(market.tradingview_url(self.symbol))

    def change_symbol(self):
        symbol = market.symbol_for(self.symbol_var.get())
        if symbol and symbol != self.symbol:
            self.symbol, self.quote, self.points, self.daily = symbol, None, [], None
            self.symbol_var.set(symbol)
            self.title(t(self.ui, "title", s=symbol))
        self.load(full=True)

    def load(self, full=False):
        """Ambil harga (dan data harian untuk 'sejak video' bila perlu) di thread; hasil dibaca poll()."""
        if self.auto_id:
            self.after_cancel(self.auto_id)
            self.auto_id = None
        if self.loading:
            return
        self.loading, self.result = True, None
        self.msg_lbl.config(text=t(self.ui, "loading", s=self.symbol), fg=T.DIM)
        symbol, rng = self.symbol, self.range
        need_daily = bool(self.context.get("videos")) and (full or self.daily is None)

        def work():
            try:
                quote = market.parse_chart(market.fetch_chart(symbol, "1d", "5m"))
                chart = quote if rng == "1D" else market.parse_chart(market.fetch_chart(symbol, *market.RANGES[rng]))
                daily = market.parse_chart(market.fetch_chart(symbol, "1y", "1d"))["points"] if need_daily else None
                self.result = ("ok", (symbol, quote, chart["points"], daily))
            except market.MarketError as e:
                self.result = ("err", e)

        threading.Thread(target=work, daemon=True).start()
        self.after(150, self.poll)

    def poll(self):
        if not self.winfo_exists():
            return
        if self.result is None:
            self.after(150, self.poll)
            return
        status, value = self.result
        self.result, self.loading = None, False
        if status == "ok":
            symbol, quote, points, daily = value
            if symbol == self.symbol:  # simbol bisa diganti selama memuat
                self.quote, self.points, self.error = quote, points, None
                if daily is not None:
                    self.daily = daily
        else:
            self.error = value
        self.render()
        if market.market_open() and self.error is None:
            self.auto_id = self.after(REFRESH_MS, self.load)

    def close(self):
        if self.auto_id:
            self.after_cancel(self.auto_id)
        self.destroy()

    # --- tampilan --------------------------------------------------------------------------------------------------
    def render(self):
        ui, q = self.ui, self.quote
        if q:
            self.name_lbl.config(text=f"{self.symbol}  {q['name']}")
            self.price_lbl.config(text=self.num(q["price"]))
            if q["change"] is not None:
                self.change_lbl.config(text=f"{'+' if q['change'] >= 0 else ''}{self.num(q['change'])} ({self.pct(q['change_pct'])})",
                                       fg=T.GOOD if q["change"] >= 0 else T.RED)
            vol = q["volume"]
            volume = t(ui, "million", x=self.short(vol / 1e6)) if vol else "-"
            self.stats_lbl.config(text=t(ui, "stats", h=self.num(q["high"]), l=self.num(q["low"]), v=volume))
            when = q["time"].strftime("%d/%m %H:%M") if q["time"] else "-"
            self.time_lbl.config(text=t(ui, "time", t=when, state=t(ui, "open" if market.market_open() else "closed")))
        else:
            self.name_lbl.config(text=self.symbol)
        if self.error is not None:
            e = self.error
            text = (t(ui, "not_found", s=self.symbol) if e.kind == "not_found"
                    else t(ui, "network" if e.kind == "network" else "bad_data", e=e.detail))
            self.msg_lbl.config(text=text + (t(ui, "stale") if q else ""), fg=T.RED)
        elif not self.loading:
            self.msg_lbl.config(text="")
        self.draw_chart()
        self.render_since()

    def levels(self):
        lv = self.context.get("levels") or {}
        return [(k, lv[k]) for k in LEVEL_ROLES if lv.get(k)]

    def draw_chart(self):
        c, ui = self.canvas, self.ui
        c.delete("all")
        w, h = max(c.winfo_width(), 400), int(c["height"])
        pts = self.points
        if not pts:
            c.create_text(w / 2, h / 2, text=t(ui, "no_data") if self.quote else "", fill=T.DIM, font=FONT)
            self.legend_lbl.config(text="")
            return
        closes = [p[1] for p in pts]
        lo, hi = min(closes), max(closes)
        span = max(hi - lo, hi * 0.01)
        shown, off = [], []
        for key, val in self.levels():  # level yang terlalu jauh membuat grafik harga jadi garis datar
            (shown if lo - 0.3 * span <= val <= hi + 0.3 * span else off).append((key, val))
        lo2, hi2 = min([lo] + [v for _, v in shown]), max([hi] + [v for _, v in shown])
        pad = (hi2 - lo2) * 0.08 or hi2 * 0.01
        lo2, hi2 = lo2 - pad, hi2 + pad
        left, right, top, bottom = 10, w - 80, 10, h - 22

        def y(v):
            return bottom - (v - lo2) / (hi2 - lo2) * (bottom - top)

        def x(i):
            return left + i * (right - left) / max(len(pts) - 1, 1)

        for k in range(5):
            v = lo2 + k * (hi2 - lo2) / 4
            c.create_line(left, y(v), right, y(v), fill=mix(T.BG, T.DIM, 0.45))
            c.create_text(right + 6, y(v), text=self.num(round(v)), anchor="w", fill=T.DIM, font=font(9))
        color = T.GOOD if closes[-1] >= closes[0] else T.RED
        if len(pts) > 1:
            c.create_line(*[n for i, p in enumerate(pts) for n in (x(i), y(p[1]))], fill=color, width=2)
        c.create_oval(x(len(pts) - 1) - 3, y(closes[-1]) - 3, x(len(pts) - 1) + 3, y(closes[-1]) + 3, fill=color, outline="")
        for key, val in shown:
            fg = getattr(T, LEVEL_ROLES[key])
            c.create_line(left, y(val), right, y(val), fill=fg, dash=(5, 3))
            c.create_text(left + 4, y(val) - 2, text=f"{t(ui, 'lv_' + key)} {self.num(val)}", anchor="sw", fill=fg,
                          font=font(9, "bold"))
        fmt = "%H:%M" if self.range in ("1D", "5D") else "%d/%m"
        if self.range == "5D":
            fmt = "%d/%m %H:%M"
        c.create_text(left, h - 4, text=pts[0][0].strftime(fmt), anchor="sw", fill=T.DIM, font=font(9))
        c.create_text(right, h - 4, text=pts[-1][0].strftime(fmt), anchor="se", fill=T.DIM, font=font(9))
        self.legend_lbl.config(text=t(ui, "off_chart", list=", ".join(f"{t(ui, 'lv_' + k)} {self.num(v)}" for k, v in off))
                               if off else "")

    def render_since(self):
        ui = self.ui
        for wdg in self.since.winfo_children():
            wdg.destroy()
        videos = self.context.get("videos") or []
        self.since_title.config(text=t(ui, "t_since"))
        if not videos:
            tk.Label(self.since, text=t(ui, "no_dates"), font=FONT, bg=T.BG, fg=T.DIM, anchor="w", justify="left",
                     wraplength=930).grid(row=0, column=0, sticky="w")
            return
        heads = ("c_date", "c_video", "c_stance", "c_move", "c_target", "c_stop")
        for col, key in enumerate(heads):
            self.cell(0, col, t(ui, key), T.DIM, FONT_B)
        for row, v in enumerate(videos, start=1):
            s = market.since(self.daily, v["date"], v["prices"]) if self.daily else None
            self.cell(row, 0, v["date"] + ("*" if v.get("fallback") else ""))
            self.cell(row, 1, v["title"][:30])
            self.cell(row, 2, report.t(ui, "stance_" + v["stance"]))
            if s is None:
                self.cell(row, 3, t(ui, "no_since") if self.daily is not None else "...", T.DIM)
            else:
                self.cell(row, 3, f"{self.num(s['start'])} -> {self.num(s['now'])} ({self.pct(s['change_pct'])})",
                          T.GOOD if s["change_pct"] >= 0 else T.RED)
            target, stop = v["prices"].get("target"), v["prices"].get("stop_loss")
            if not target:
                self.cell(row, 4, "-", T.DIM)
            elif s and s["target_hit"]:
                self.cell(row, 4, f"{self.num(target)} {t(ui, 'hit')}", T.GOOD)
            else:
                self.cell(row, 4, self.num(target) + (f" ({self.pct(s['to_target_pct'])})" if s else ""), T.FG)
            if not stop:
                self.cell(row, 5, "-", T.DIM)
            else:
                hit = s and s["stop_hit"]
                self.cell(row, 5, f"{self.num(stop)} {t(ui, 'hit' if hit else 'safe')}" if s else self.num(stop),
                          T.RED if hit else T.FG)
        if any(v.get("fallback") for v in videos):
            tk.Label(self.since, text=t(ui, "fallback"), font=FONT, bg=T.BG, fg=T.DIM, anchor="w"
                     ).grid(row=len(videos) + 1, column=0, columnspan=6, sticky="w", pady=(4, 0))

    def cell(self, row, col, text, fg=None, font=FONT):
        tk.Label(self.since, text=text, font=font, bg=T.BG, fg=fg or T.FG, anchor="w"
                 ).grid(row=row, column=col, sticky="w", padx=(0, 14), pady=1)
