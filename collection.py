"""Halaman RINGKASAN PASAR: semua analisis tersimpan, dikelompokkan per tanggal video, dan perbandingan emiten lintas video.

Angka dari archive.py; ringkasan AI hanya saat tombolnya ditekan, lalu disimpan. Bicara dengan aplikasi hanya lewat
method App (collection_records, archive_dir, fill_video_dates, open_record, llm_ready, llm_complete, button, tr).
"""
import json
import threading
import tkinter as tk
from datetime import datetime
from tkinter import messagebox

import archive
import report
from dashboard import DashboardView, stance_color
from theme import FONT, FONT_B, T

_T = {
    "info": ("{v} video · {s} emiten · {m} dibahas di lebih dari 1 video", "{v} videos · {s} stocks · {m} discussed in more than 1 video"),
    "empty": ("Belum ada analisis tersimpan. Analisis video di halaman ANALISIS; hasilnya otomatis masuk ke sini.",
              "No saved analyses yet. Analyse a video on the ANALYSIS page; the result is added here automatically."),
    "fill_btn": ("[ LENGKAPI TANGGAL VIDEO ]", "[ FILL IN VIDEO DATES ]"), "reload": ("[ MUAT ULANG ]", "[ RELOAD ]"),
    "fill_running": ("Mengambil tanggal upload {n} video lewat yt-dlp...", "Fetching the upload date of {n} videos with yt-dlp..."),
    "fill_done": ("Tanggal upload {ok} video diperbarui.", "Upload date updated for {ok} videos."),
    "fill_failed": (" {n} gagal (cek koneksi), coba lagi nanti.", " {n} failed (check the connection); try again later."),
    "fill_err": ("Gagal mengambil tanggal: {e}", "Could not fetch dates: {e}"),
    "dates_h": ("TANGGAL VIDEO", "VIDEO DATE"), "all_dates": ("SEMUA TANGGAL", "ALL DATES"),
    "stocks_h": ("EMITEN", "STOCKS"), "search": ("CARI>", "FIND>"),
    "fallback": ("* belum ada tanggal upload; memakai tanggal analisis. Tekan LENGKAPI TANGGAL VIDEO.",
                 "* no upload date yet; the analysis date is used. Press FILL IN VIDEO DATES."),
    "t_trending": ("EMITEN PALING SERING DIBAHAS", "MOST-DISCUSSED STOCKS"),
    "t_tone": ("SUASANA PASAR PER TANGGAL", "MARKET TONE PER DATE"), "t_videos": ("VIDEO", "VIDEOS"),
    "t_videos_day": ("VIDEO TANGGAL {d}", "VIDEOS ON {d}"),
    "t_compare": ("EMITEN YANG DIBAHAS DI LEBIH DARI 1 VIDEO", "STOCKS DISCUSSED IN MORE THAN 1 VIDEO"),
    "others": ("Dibahas di 1 video: {list}", "Discussed in 1 video: {list}"),
    "none_multi": ("Tidak ada emiten yang dibahas di lebih dari satu video pada tanggal ini.",
                   "No stock was discussed in more than one video on this date."),
    "tone_cap": ("{tone:+.2f} · {n} video", "{tone:+.2f} · {n} videos"),
    "c_ticker": ("EMITEN", "STOCK"), "c_videos": ("VIDEO", "VIDEOS"), "c_consensus": ("KONSENSUS", "CONSENSUS"),
    "c_agree": ("SEPAKAT", "AGREE"), "c_target": ("TARGET", "TARGET"), "c_date": ("TANGGAL", "DATE"),
    "c_source": ("SUMBER", "SOURCE"), "c_stance": ("SIKAP", "STANCE"), "c_levels": ("LEVEL HARGA", "PRICE LEVELS"),
    "c_conf": ("YAKIN", "CONF."), "c_tone": ("NADA", "TONE"), "c_per_video": ("SIKAP PER VIDEO", "STANCE PER VIDEO"),
    "disagree": ("! BEDA", "! SPLIT"), "delete": ("[ HAPUS ]", "[ DELETE ]"),
    "del_q": ("Hapus video ini dari RINGKASAN PASAR (semua versi analisisnya)? Transkrip di Riwayat tidak ikut terhapus.",
              "Remove this video from the MARKET OVERVIEW (all its analysis versions)? The transcript in History is kept."),
    "missing_entry": ("Transkrip video ini sudah tidak ada di Riwayat, jadi hasilnya tidak bisa dibuka di halaman ANALISIS.",
                      "This video's transcript is no longer in History, so it cannot be opened on the ANALYSIS page."),
    "back": ("‹ kembali", "‹ back"),
    "head": ("{t} · dibahas di {n} video ({a} sampai {b})", "{t} · discussed in {n} videos ({a} to {b})"),
    "head_one": ("{t} · dibahas di 1 video ({a})", "{t} · discussed in 1 video ({a})"),
    "t_consensus": ("KONSENSUS", "CONSENSUS"),
    "consensus": ("{counts}  ->  mayoritas {dom} ({p}% video sepakat)", "{counts}  ->  majority {dom} ({p}% of videos agree)"),
    "consensus_tie": ("{counts}  ->  seri, tidak ada mayoritas ({dom})", "{counts}  ->  tied, no majority ({dom})"),
    "conflict": ("(!) Beda pendapat: ada video yang menyarankan BELI dan ada yang menyarankan JUAL/HINDARI. Bandingkan alasannya di timeline.",
                 "(!) Disagreement: some videos say BUY and others SELL/AVOID. Compare their reasons in the timeline."),
    "t_timeline": ("TIMELINE", "TIMELINE"),
    "t_zone": ("ZONA HARGA GABUNGAN", "COMBINED PRICE ZONE"),
    "zone": ("{label}: {lo} sampai {hi} (nilai tengah {mid}, disebut di {n} video)", "{label}: {lo} to {hi} (median {mid}, stated in {n} videos)"),
    "zone_one": ("{label}: {mid} (disebut di 1 video)", "{label}: {mid} (stated in 1 video)"),
    "zone_none": ("Belum ada video yang menyebut harga beli, target, atau batas rugi.", "No video stated a buy price, target or loss limit yet."),
    "repeated": ("Angka yang disebut di beberapa video: {list}", "Numbers stated in several videos: {list}"),
    "rep_item": ("{p} ({n} video)", "{p} ({n} videos)"),
    "rr": ("Untung:Rugi dari nilai tengah: beli {e}, target {t}, batas rugi {s}  ->  {r}",
           "Reward:Risk from the medians: buy {e}, target {t}, loss limit {s}  ->  {r}"),
    "rr_none": ("Untung:Rugi gabungan tidak bisa dihitung (butuh nilai tengah batas rugi < beli < target).",
                "Combined reward:risk cannot be computed (needs median loss limit < buy < target)."),
    "t_changes": ("PERUBAHAN PANDANGAN", "CHANGES OF VIEW"),
    "ch_stance": ("{d}: sikap {a} -> {b} ({title})", "{d}: stance {a} -> {b} ({title})"),
    "ch_target": ("{d}: target {a} -> {b} ({title})", "{d}: target {a} -> {b} ({title})"),
    "ch_stop_loss": ("{d}: batas rugi {a} -> {b} ({title})", "{d}: loss limit {a} -> {b} ({title})"),
    "no_changes": ("Tidak ada perubahan sikap, target, atau batas rugi antar video.", "No change of stance, target or loss limit between videos."),
    "t_reliability": ("KEANDALAN", "RELIABILITY"),
    "rel": ("{d} dari {n} video menandai nama/angka emiten ini meragukan (mungkin salah dengar).",
            "{d} of {n} videos marked this stock's name/numbers as doubtful (possibly misheard)."),
    "rel_conf": (" Rata-rata keyakinan pembicara: {c} (dari {r} video).", " Average speaker confidence: {c} (from {r} videos)."),
    "t_reasons": ("ALASAN PER VIDEO", "REASON PER VIDEO"),
    "price_btn": ("[ HARGA SAHAM ]", "[ STOCK PRICE ]"),
    "t_ai": ("RINGKASAN AI", "AI SUMMARY"), "ai_btn": ("[ RANGKUM AI ]", "[ AI SUMMARY ]"),
    "ai_update": ("[ PERBARUI RINGKASAN AI ]", "[ UPDATE AI SUMMARY ]"),
    "ai_running": ("Merangkum dengan {m}...", "Summarising with {m}..."),
    "ai_meta": ("Dibuat {at} dengan {m}. Dibuat AI dari hasil ekstraksi di halaman ini; bisa keliru, bukan nasihat investasi.",
                "Made {at} with {m}, by AI from the extracted data on this page; it can be wrong and is not investment advice."),
    "ai_stale": ("Ringkasan ini dibuat sebelum ada analisis baru untuk {k}; tekan PERBARUI untuk menyertakannya.",
                 "This summary predates newer analyses for {k}; press UPDATE to include them."),
    "ai_hint": ("Rangkuman kesamaan, perbedaan, dan perubahan pendapat dari video-video ini (1 panggilan LLM, hasil disimpan).",
                "A summary of what these videos agree on, disagree on and how their views changed (1 LLM call, saved)."),
    "ai_off": ("Atur API key dan model LLM di Alat > Pengaturan untuk memakai ringkasan AI.",
               "Set the LLM API key and model in Tools > Settings to use AI summaries."),
    "ai_err": ("Gagal membuat ringkasan: {e}", "Could not create the summary: {e}"),
    "lang_rule": ("Tulis dalam Bahasa Indonesia.", "Write in English."),
}

AI_SYSTEM = """Kamu merangkum hasil ekstraksi beberapa video YouTube tentang saham (data JSON di bawah, bukan transkrip).
Aturan:
- Hanya pakai data yang diberikan. Jangan menambah harga, target, ticker, atau fakta yang tidak ada di data.
- Sebutkan: apa yang disepakati, apa yang berbeda (siapa/video mana), bagaimana pandangan berubah dari tanggal ke tanggal, risiko yang disebut, dan apa yang perlu dicek ulang (misalnya data yang ditandai doubtful).
- 4 sampai 8 butir pendek diawali "- ". Tanpa judul, tanpa penutup.
- Ini rangkuman isi video, bukan nasihat investasi; jangan memberi saran beli/jual sendiri.
"""


def t(ui, key, **kw):
    s = _T[key][1 if ui == "EN" else 0]
    return s.format(**kw) if kw else s


class CollectionView(DashboardView):
    """DashboardView + blok tabel, batang nada, tombol, dan link."""

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app

    def cell(self, parent, cell):
        cell = {"text": cell} if isinstance(cell, str) else cell
        if "badges" in cell:
            frame = tk.Frame(parent, bg=T.BG)
            for stance, label in cell["badges"]:
                tk.Label(frame, text=f" {label} ", fg=T.BG, bg=stance_color(stance), font=FONT_B).pack(side="left", padx=(0, 3))
            return frame
        lbl = tk.Label(parent, text=cell["text"], fg=getattr(T, cell.get("fg", "FG")), bg=T.BG, anchor="w", justify="left",
                       font=FONT_B if cell.get("bold") else FONT, wraplength=cell.get("wrap", 0))
        if cell.get("cmd"):
            lbl.config(cursor="hand2", font=(*FONT, "underline"))
            lbl.bind("<Button-1>", lambda e: cell["cmd"]())
        return lbl

    def b_table(self, p, v):
        frame = tk.Frame(p, bg=T.BG)
        frame.pack(fill="x", pady=(4, 6))
        for c, head in enumerate(v["cols"]):
            tk.Label(frame, text=head, font=FONT_B, bg=T.BG, fg=T.DIM, anchor="w").grid(row=0, column=c, sticky="w", padx=(0, 14))
        for r, row in enumerate(v["rows"], start=1):
            for c, cell in enumerate(row):
                self.cell(frame, cell).grid(row=r, column=c, sticky="w", padx=(0, 14), pady=1)

    def b_bars(self, p, rows):
        w = 240
        for label, value, caption in rows:
            row = tk.Frame(p, bg=T.BG)
            row.pack(fill="x", pady=1)
            tk.Label(row, text=label, font=FONT, bg=T.BG, fg=T.FG, width=12, anchor="w").pack(side="left")
            c = tk.Canvas(row, width=w, height=12, bg=T.BG, highlightthickness=0)
            c.pack(side="left", padx=6)
            c.create_rectangle(0, 0, w - 1, 11, outline=T.DIM)
            mid, x = w / 2, w / 2 + max(-1.0, min(value, 1.0)) * (w / 2 - 2)
            c.create_rectangle(min(mid, x), 1, max(mid, x), 10, fill=T.GOOD if value >= 0 else T.RED, outline="")
            c.create_line(mid, 0, mid, 12, fill=T.DIM)
            tk.Label(row, text=caption, font=FONT, bg=T.BG, fg=T.DIM, anchor="w").pack(side="left")

    def b_actions(self, p, items):
        row = tk.Frame(p, bg=T.BG)
        row.pack(fill="x", pady=(4, 4))
        for text, cmd, enabled in items:
            b = self.app.button(row, text, cmd)
            b.pack(side="left", padx=(0, 8))
            if not enabled:
                b.config(state="disabled")

    def b_link(self, p, v):
        text, cmd = v
        lbl = self.label(p, text, fg=T.CYAN, pady=(0, 4))
        lbl.configure(cursor="hand2", font=(*FONT, "underline"))
        lbl.bind("<Button-1>", lambda e: cmd())


class CollectionPage(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=T.BG)
        self.app = app
        self.loaded = False
        self.all_records, self.records = [], []  # semua versi / terbaru per video
        self.day = None  # None = semua tanggal
        self.ticker = None
        self.day_keys, self.ticker_rows = [], []
        self.ai_running = None  # (kind, key) selama LLM bekerja
        self.ai_result = None
        self.ai_error = {}
        self.fill_result = None

        top = tk.Frame(self, bg=T.BG)
        top.pack(fill="x", padx=14, pady=(0, 6))
        self.reload_btn = app.button(top, "", self.reload)
        self.reload_btn.pack(side="right")
        self.fill_btn = app.button(top, "", self.fill_dates)
        self.info = tk.Label(top, text="", font=FONT, bg=T.BG, fg=T.AMBER, anchor="w", justify="left")
        self.info.pack(side="left", fill="x", expand=True)

        body = tk.Frame(self, bg=T.BG)
        body.pack(fill="both", expand=True, padx=14, pady=(0, 8))
        left = tk.Frame(body, bg=T.BG, highlightthickness=1, highlightbackground=T.FG)
        left.pack(side="left", fill="y")
        self.dates_lbl = tk.Label(left, text="", font=FONT_B, bg=T.BG, fg=T.AMBER, anchor="w")
        self.dates_lbl.pack(fill="x", padx=6, pady=(6, 0))
        self.dates = self.listbox(left, 8)
        self.dates.bind("<<ListboxSelect>>", lambda e: self.pick_day())
        self.stocks_lbl = tk.Label(left, text="", font=FONT_B, bg=T.BG, fg=T.AMBER, anchor="w")
        self.stocks_lbl.pack(fill="x", padx=6, pady=(8, 0))
        row = tk.Frame(left, bg=T.BG)
        row.pack(fill="x", padx=6, pady=(2, 2))
        self.search_lbl = tk.Label(row, text="", font=FONT_B, bg=T.BG, fg=T.FG)
        self.search_lbl.pack(side="left")
        self.search = tk.StringVar()
        self.search.trace_add("write", lambda *_: self.fill_tickers())
        tk.Entry(row, textvariable=self.search, font=FONT, width=10, bg=T.BG, fg=T.FG, insertbackground=T.FG,
                 relief="flat", highlightthickness=1, highlightbackground=T.DIM, highlightcolor=T.FG
                 ).pack(side="left", fill="x", expand=True, padx=(6, 0))
        self.stocks = self.listbox(left, 0)
        self.stocks.bind("<<ListboxSelect>>", lambda e: self.pick_ticker())
        holder = tk.Frame(body, bg=T.BG, highlightthickness=1, highlightbackground=T.FG)
        holder.pack(side="left", fill="both", expand=True, padx=(8, 0))
        self.view = CollectionView(holder, app)
        self.view.pack(fill="both", expand=True)
        self.apply_lang()

    def listbox(self, parent, height):
        lb = tk.Listbox(parent, font=FONT, width=24, height=height, bg=T.BG, fg=T.FG, selectbackground=T.FG,
                        selectforeground=T.BG, relief="flat", highlightthickness=0, activestyle="none",
                        exportselection=False)  # dua daftar: pilihan di satu tidak menghapus yang lain
        lb.pack(fill="both" if not height else "x", expand=not height, padx=4, pady=4)
        return lb

    @property
    def ui(self):
        return self.app.ui

    def apply_lang(self):
        self.reload_btn.config(text=t(self.ui, "reload"))
        self.fill_btn.config(text=t(self.ui, "fill_btn"))
        self.dates_lbl.config(text=t(self.ui, "dates_h"))
        self.stocks_lbl.config(text=t(self.ui, "stocks_h"))
        self.search_lbl.config(text=t(self.ui, "search"))
        if self.loaded:
            self.fill_lists()
            self.render()

    # --- data dan daftar ------------------------------------------------------------------------------------------
    def reload(self):
        self.all_records = self.app.collection_records()
        self.records = archive.latest_per_video(self.all_records)
        vids = {r["vid"] for r in self.records}
        if self.day and self.day not in archive.group_by_date(self.records):
            self.day = None
        if self.ticker and self.ticker not in archive.tickers(self.records):
            self.ticker = None
        self.loaded = True
        n_multi = sum(1 for r in archive.trending(self.records) if r["videos"] > 1)
        self.info.config(text=t(self.ui, "info", v=len(vids), s=len(archive.tickers(self.records)), m=n_multi)
                         if self.records else "", fg=T.AMBER)
        if archive.missing_dates(self.records):
            self.fill_btn.pack(side="right", padx=6)
        else:
            self.fill_btn.pack_forget()
        self.fill_lists()
        self.render()

    def scope(self):
        return archive.group_by_date(self.records).get(self.day, []) if self.day else self.records

    def fill_lists(self):
        groups = archive.group_by_date(self.records)
        self.day_keys = [None] + list(groups)
        self.dates.delete(0, "end")
        self.dates.insert("end", f"{t(self.ui, 'all_dates')} ({len(self.records)})")
        for day, recs in groups.items():
            mark = "*" if any(archive.date_is_fallback(r) for r in recs) else " "
            self.dates.insert("end", f"{day}{mark} ({len(recs)})")
        self.dates.selection_set(self.day_keys.index(self.day))
        self.fill_tickers()

    def fill_tickers(self):
        query = self.search.get().strip().upper()
        self.ticker_rows = [r for r in archive.trending(self.scope()) if query in r["ticker"]]
        self.stocks.delete(0, "end")
        for r in self.ticker_rows:
            self.stocks.insert("end", f"{r['ticker']:<6} {r['videos']:>2}  {'!' if r['conflict'] else ''}")
        tickers = [r["ticker"] for r in self.ticker_rows]
        if self.ticker in tickers:
            self.stocks.selection_set(tickers.index(self.ticker))

    def pick_day(self):
        sel = self.dates.curselection()
        if sel:
            self.day, self.ticker = self.day_keys[sel[0]], None
            self.fill_tickers()
            self.render()

    def pick_ticker(self):
        sel = self.stocks.curselection()
        if sel:
            self.select_ticker(self.ticker_rows[sel[0]]["ticker"])

    def select_ticker(self, ticker):
        self.ticker = ticker
        self.fill_tickers()
        self.render()

    def clear_ticker(self):
        self.ticker = None
        self.stocks.selection_clear(0, "end")
        self.render()

    # --- tampilan --------------------------------------------------------------------------------------------------
    def render(self):
        if not self.loaded:
            return
        if not self.records:
            self.view.message(t(self.ui, "empty"))
        elif self.ticker:
            self.view.render(self.ticker_blocks(self.ticker))
        elif self.day:
            self.view.render(self.day_blocks(self.day))
        else:
            self.view.render(self.all_blocks())

    def stance(self, s):
        return s, report.t(self.ui, "stance_" + s)

    def num(self, x):
        return report.fmt_num(x, self.ui)

    def ticker_cell(self, ticker):
        return {"text": ticker, "fg": "AMBER", "cmd": lambda: self.select_ticker(ticker)}

    def video_rows(self, recs, with_date):
        rows = []
        for r in sorted(recs, key=lambda r: (archive.date_of(r), r["channel"], r["title"]), reverse=with_date):
            title = {"text": r["title"], "wrap": 380, "cmd": lambda r=r: self.open_record(r)}
            row = [r["channel"] or "-", title, {"text": f"{r['tone']:+.2f}", "fg": "GOOD" if r["tone"] >= 0 else "RED"},
                   {"text": t(self.ui, "delete"), "fg": "DIM", "cmd": lambda r=r: self.delete(r)}]
            if with_date:
                row.insert(0, archive.date_of(r) + ("*" if archive.date_is_fallback(r) else ""))
            rows.append(row)
        cols = [t(self.ui, "c_source"), "", t(self.ui, "c_tone"), ""]  # kanal, judul, nada, hapus
        return {"cols": ([t(self.ui, "c_date")] if with_date else []) + cols, "rows": rows}

    def all_blocks(self):
        ui, b = self.ui, []
        if any(archive.date_is_fallback(r) for r in self.records):
            b.append(("dim", t(ui, "fallback")))
        b.append(("title", t(ui, "t_trending")))
        rows = [[self.ticker_cell(r["ticker"]), str(r["videos"]), {"badges": [self.stance(s) for s in r["top"]]},
                 f"{r['agreement']}%", {"text": t(ui, "disagree") if r["conflict"] else "", "fg": "RED"}]
                for r in archive.trending(self.records)[:20]]
        b.append(("table", {"cols": [t(ui, k) for k in ("c_ticker", "c_videos", "c_consensus", "c_agree")] + [""],
                            "rows": rows}))
        b.append(("title", t(ui, "t_tone")))
        b.append(("bars", [(day, tone, t(ui, "tone_cap", tone=tone, n=n)) for day, tone, n in archive.tone_by_date(self.records)]))
        b.append(("title", t(ui, "t_videos")))
        b.append(("table", self.video_rows(self.records, True)))
        return b

    def day_blocks(self, day):
        ui, recs = self.ui, archive.group_by_date(self.records)[day]
        b = [("title", t(ui, "t_videos_day", d=day)), ("table", self.video_rows(recs, False))]
        if any(archive.date_is_fallback(r) for r in recs):
            b.append(("dim", t(ui, "fallback")))
        b += self.ai_blocks("date", day, recs, self.date_payload(recs))
        b.append(("title", t(ui, "t_compare")))
        multi = [r for r in archive.trending(recs) if r["videos"] > 1]
        rows = []
        for r in multi:
            vs = archive.views(recs, r["ticker"])
            targets = [v["prices"]["target"] for v in vs if v["prices"].get("target")]
            span = (self.num(min(targets)) + (f" - {self.num(max(targets))}" if max(targets) != min(targets) else "")) if targets else "-"
            rows.append([self.ticker_cell(r["ticker"]), str(r["videos"]), {"badges": [self.stance(v["stance"]) for v in vs]},
                         " / ".join(report.t(ui, "stance_" + s) for s in r["top"]) + f" {r['agreement']}%", span,
                         {"text": t(ui, "disagree") if r["conflict"] else "", "fg": "RED"}])
        if rows:
            b.append(("table", {"cols": [t(ui, k) for k in ("c_ticker", "c_videos", "c_per_video", "c_consensus", "c_target")] + [""],
                                "rows": rows}))
        else:
            b.append(("dim", t(ui, "none_multi")))
        single = [r["ticker"] for r in archive.trending(recs) if r["videos"] == 1]
        if single:
            b.append(("para", t(ui, "others", list=", ".join(single))))
        return b

    def ticker_blocks(self, ticker):
        ui, recs = self.ui, self.records
        vs = archive.views(recs, ticker)
        if not vs:
            return [("dim", t(ui, "empty"))]
        b = [("link", (t(ui, "back"), self.clear_ticker))]
        head = (t(ui, "head", t=ticker, n=len(vs), a=vs[0]["date"], b=vs[-1]["date"]) if len(vs) > 1
                else t(ui, "head_one", t=ticker, a=vs[0]["date"]))
        b.append(("title", head))
        c = archive.consensus(vs)
        counts = " · ".join(f"{report.t(ui, 'stance_' + s)} {n}" for s, n in c["counts"].items())
        dom = " / ".join(report.t(ui, "stance_" + s) for s in c["top"])
        b.append(("para", t(ui, "consensus" if len(c["top"]) == 1 else "consensus_tie", counts=counts, dom=dom,
                            p=c["agreement"])))
        if archive.conflict(vs):
            b.append(("warn", t(ui, "conflict")))
        b.append(("actions", [(t(ui, "price_btn"), lambda: self.open_price(ticker, vs), True)]))
        used = [r for r in recs if any(s["ticker"] == ticker for s in r["stocks"])]
        b += self.ai_blocks("ticker", ticker, used, self.ticker_payload(vs))

        b.append(("title", t(ui, "t_timeline")))
        rows = []
        for v in vs:
            rec = next(r for r in recs if r["vid"] == v["vid"])
            levels = " · ".join(f"{report.t(ui, 'lv_' + k)} {x}" for k, x in v["levels"].items()) or "-"
            rows.append([v["date"] + ("*" if v["fallback"] else ""),
                         {"text": f"{v['channel']}: {v['title']}" if v["channel"] else v["title"], "wrap": 300,
                          "cmd": lambda r=rec: self.open_record(r)},
                         {"badges": [self.stance(v["stance"])]}, {"text": levels, "wrap": 300},
                         report.t(ui, "conf_" + v["confidence"]) if v["confidence"] else "-",
                         {"text": "(!)" if v["doubtful"] else "", "fg": "RED"}])
        b.append(("table", {"cols": [t(ui, k) for k in ("c_date", "c_source", "c_stance", "c_levels", "c_conf")] + [""],
                            "rows": rows}))

        b.append(("title", t(ui, "t_zone")))
        z = archive.price_zone(vs)
        if not z["levels"]:
            b.append(("dim", t(ui, "zone_none")))
        for key, lv in z["levels"].items():
            label = report.t(ui, "lv_" + key)
            b.append(("para", t(ui, "zone", label=label, lo=self.num(lv["min"]), hi=self.num(lv["max"]),
                                mid=self.num(lv["median"]), n=lv["n"]) if lv["n"] > 1
                      else t(ui, "zone_one", label=label, mid=self.num(lv["median"]))))
        if z["repeated"]:
            b.append(("para", t(ui, "repeated", list=", ".join(t(ui, "rep_item", p=self.num(p), n=n) for p, n in z["repeated"]))))
        if z["rr"]:
            rr = z["rr"]
            b.append(("para", t(ui, "rr", e=self.num(rr["entry"]), t=self.num(rr["target"]), s=self.num(rr["stop_loss"]),
                                r=f"{rr['ratio']:.2f}")))
        elif z["levels"]:
            b.append(("dim", t(ui, "rr_none")))

        b.append(("title", t(ui, "t_changes")))
        ch = archive.changes(vs)
        if ch:
            b.append(("bullets", [t(ui, "ch_" + x["kind"], d=x["date"], title=x["title"][:50],
                                    a=report.t(ui, "stance_" + x["from"]) if x["kind"] == "stance" else self.num(x["from"]),
                                    b=report.t(ui, "stance_" + x["to"]) if x["kind"] == "stance" else self.num(x["to"]))
                                  for x in ch]))
        else:
            b.append(("dim", t(ui, "no_changes")))

        b.append(("title", t(ui, "t_reliability")))
        rel = archive.reliability(vs)
        text = t(ui, "rel", d=rel["doubtful"], n=rel["n"])
        if rel["confidence"]:
            text += t(ui, "rel_conf", c=report.t(ui, "conf_" + rel["confidence"]), r=rel["rated"])
        b.append(("para", text))

        b.append(("title", t(ui, "t_reasons")))
        b.append(("bullets", [f"{v['date']} · {v['channel'] or v['title'][:40]}: {v['reason'] or '-'}" for v in vs]))
        return b

    # --- ringkasan AI ----------------------------------------------------------------------------------------------
    def ticker_payload(self, vs):
        return json.dumps([{k: v[k] for k in ("date", "channel", "title", "stance", "levels", "reason", "expectation",
                                              "confidence", "doubtful")} for v in vs], ensure_ascii=False, indent=1)

    def date_payload(self, recs):
        return json.dumps([{"title": r["title"], "channel": r["channel"], "sentiment": r["sentiment"],
                            "summary": r["summary"], "outlook": r["outlook"],
                            "stocks": [{"ticker": s["ticker"], "stance": s["stance"], "levels": s["levels"]} for s in r["stocks"]]}
                           for r in recs], ensure_ascii=False, indent=1)

    def ai_blocks(self, kind, key, recs, payload):
        ui, folder = self.ui, self.app.archive_dir()
        path = archive.ai_path(folder, kind, key, recs, ui)
        b = [("title", t(ui, "t_ai"))]
        if self.ai_running == (kind, key):
            return b + [("dim", t(ui, "ai_running", m=self.app.model))]
        start = lambda: self.run_ai(kind, key, path, payload)  # noqa: E731
        ready = self.app.llm_ready()
        current = archive.latest_ai(folder, kind, key)
        if current and current[0] == path:
            data = current[1]
            b += [("para", data.get("text", "")), ("dim", t(ui, "ai_meta", at=data.get("created", "?"), m=data.get("model", "?")))]
        elif current:
            data = current[1]
            b += [("para", data.get("text", "")), ("warn", t(ui, "ai_stale", k=key)),
                  ("actions", [(t(ui, "ai_update"), start, ready)])]
        else:
            b += [("dim", t(ui, "ai_hint")), ("actions", [(t(ui, "ai_btn"), start, ready)])]
        if not ready and not (current and current[0] == path):
            b.append(("dim", t(ui, "ai_off")))
        if (kind, key) in self.ai_error:
            b.append(("warn", t(ui, "ai_err", e=self.ai_error[(kind, key)])))
        return b

    def run_ai(self, kind, key, path, payload):
        if self.ai_running:
            return
        self.ai_running, self.ai_result = (kind, key), None
        self.ai_error.pop((kind, key), None)
        model = self.app.model
        system = AI_SYSTEM + t(self.ui, "lang_rule")

        def work():
            try:
                self.ai_result = ("ok", self.app.llm_complete(system, payload))
            except Exception as e:  # jaringan, kunci, model: tampilkan, jangan hentikan aplikasi
                self.ai_result = ("err", f"{type(e).__name__}: {e}")

        threading.Thread(target=work, daemon=True).start()
        self.render()
        self.after(150, self.poll_ai, kind, key, path, model)

    def poll_ai(self, kind, key, path, model):
        if self.ai_result is None:
            self.after(150, self.poll_ai, kind, key, path, model)
            return
        status, value = self.ai_result
        self.ai_result, self.ai_running = None, None
        if status == "ok" and value.strip():
            archive.write_json(path, {"kind": kind, "key": key, "text": value.strip(), "model": model,
                                      "created": datetime.now().strftime("%Y-%m-%d %H:%M")})
        else:
            self.ai_error[(kind, key)] = value if status == "err" else "empty reply"
        self.render()

    # --- aksi ------------------------------------------------------------------------------------------------------
    def open_price(self, ticker, vs):
        """Jendela harga dengan nilai tengah level dari semua video dan pergerakan sejak tiap video."""
        zone = archive.price_zone(vs)["levels"]
        self.app.open_stock(ticker, {
            "levels": {k: lv["median"] for k, lv in zone.items()},
            "videos": [{"date": v["date"], "title": v["title"], "stance": v["stance"], "prices": v["prices"],
                        "fallback": v["fallback"]} for v in vs]})

    def open_record(self, rec):
        result = self.app.open_record(rec)
        if result == "busy":
            self.info.config(text=self.app.tr("busy"), fg=T.RED)
        elif result == "missing":
            self.info.config(text=t(self.ui, "missing_entry"), fg=T.RED)

    def delete(self, rec):
        if messagebox.askyesno(self.app.tr("page_collection"), t(self.ui, "del_q") + f"\n\n{rec['title']}", parent=self.app):
            archive.delete_video(self.app.archive_dir(), rec["vid"])
            self.reload()

    def fill_dates(self):
        missing = archive.missing_dates(self.records)
        if not missing or self.fill_result is not None:
            return
        self.fill_btn.config(state="disabled")
        self.info.config(text=t(self.ui, "fill_running", n=len(missing)), fg=T.AMBER)
        self.fill_result = ()

        def work():
            try:
                self.fill_result = ("ok", self.app.fill_video_dates(missing))
            except Exception as e:  # yt-dlp tidak terpasang, dsb.
                self.fill_result = ("err", f"{type(e).__name__}: {e}")

        threading.Thread(target=work, daemon=True).start()
        self.after(200, self.poll_fill)

    def poll_fill(self):
        if self.fill_result == ():
            self.after(200, self.poll_fill)
            return
        status, value = self.fill_result
        self.fill_result = None
        self.fill_btn.config(state="normal")
        self.reload()
        if status == "ok":
            ok, failed = value
            self.info.config(text=t(self.ui, "fill_done", ok=ok) + (t(self.ui, "fill_failed", n=failed) if failed else ""),
                             fg=T.RED if failed else T.AMBER)
        else:
            self.info.config(text=t(self.ui, "fill_err", e=value), fg=T.RED)
