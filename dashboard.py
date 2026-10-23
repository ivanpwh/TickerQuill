"""Tampilan dashboard retro (scrollable) dari blok yang dihasilkan report.blocks()."""
import re
import tkinter as tk
import webbrowser

from theme import FONT, FONT_B, FONT_BIG, T, mix


def stance_color(stance):
    """Warna lencana sikap menurut tema yang sedang aktif."""
    return {"BUY": T.GOOD, "HOLD": T.CYAN, "SELL": T.RED, "AVOID": mix(T.RED, T.BG, 0.3), "WATCH": T.AMBER}[stance]


def open_url(url):
    """Buka link di browser. Hanya http(s); kegagalan (misalnya tanpa browser bawaan) diabaikan."""
    if not re.match(r"^https?://", url or ""):
        return
    try:
        webbrowser.open(url)
    except (webbrowser.Error, OSError):
        pass


class DashboardView(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=T.BG)
        self.canvas = tk.Canvas(self, bg=T.BG, highlightthickness=0)
        sb = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview, troughcolor=T.BG, bg=T.DIM,
                          relief="flat", bd=0, width=12)
        self.canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.inner = tk.Frame(self.canvas, bg=T.BG)
        self.win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.wrap_labels = []
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", self.on_resize)
        self.canvas.bind("<Enter>", lambda e: self.canvas.bind_all("<MouseWheel>", self.on_wheel))
        self.canvas.bind("<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>"))

    def on_wheel(self, e):
        self.canvas.yview_scroll(-1 * (e.delta // 120), "units")

    def on_resize(self, e):
        self.canvas.itemconfigure(self.win, width=e.width)
        for lbl in self.wrap_labels:
            if lbl.winfo_exists():
                lbl.configure(wraplength=max(200, e.width - 60))

    def label(self, parent, text, fg=None, font=FONT, padx=0, pady=0):
        lbl = tk.Label(parent, text=text, fg=fg or T.FG, bg=T.BG, font=font, justify="left", anchor="w")
        lbl.pack(fill="x", padx=padx, pady=pady)
        self.wrap_labels.append(lbl)
        lbl.configure(wraplength=max(200, self.canvas.winfo_width() - 60))
        return lbl

    def clear(self):
        for w in self.inner.winfo_children():
            w.destroy()
        self.wrap_labels = []
        self.canvas.yview_moveto(0)

    def message(self, text):
        self.clear()
        pad = tk.Frame(self.inner, bg=T.BG)
        pad.pack(fill="x", padx=14, pady=14)
        self.label(pad, text, fg=T.DIM)

    def render(self, blocks):
        self.clear()
        body = tk.Frame(self.inner, bg=T.BG)
        body.pack(fill="x", padx=14, pady=(10, 20))
        for kind, v in blocks:
            getattr(self, "b_" + kind)(body, v)

    # --- blok -------------------------------------------------------------------------------------
    def b_source(self, p, v):
        self.label(p, v["title"], fg=T.AMBER, font=FONT_B)
        lbl = self.label(p, v["line"], fg=T.CYAN if v["url"] else T.DIM, pady=(0, 4))
        if v["url"]:  # link video bisa diklik; berkas hanya ditampilkan
            lbl.configure(font=(*FONT, "underline"), cursor="hand2")
            lbl.bind("<Button-1>", lambda e: open_url(v["url"]))

    def b_title(self, p, text):
        tk.Frame(p, bg=T.DIM, height=1).pack(fill="x", pady=(16, 4))
        self.label(p, "> " + text, fg=T.AMBER, font=FONT_B)

    def b_para(self, p, text):
        self.label(p, text, pady=2)

    def b_warn(self, p, text):
        f = tk.Frame(p, bg=T.BG, highlightthickness=1, highlightbackground=T.RED)
        f.pack(fill="x", pady=(0, 6))
        self.label(f, text, fg=T.RED, padx=8, pady=6)

    def b_dim(self, p, text):
        self.label(p, text, fg=T.DIM, pady=2)

    def b_method_h(self, p, text):
        self.label(p, text, fg=T.CYAN, font=FONT_B, pady=(8, 0))

    def b_formula(self, p, text):
        f = tk.Frame(p, bg=T.BG, highlightthickness=1, highlightbackground=T.DIM)
        f.pack(fill="x", pady=3, padx=(14, 0))
        self.label(f, text, fg=T.AMBER, padx=6, pady=3)

    def b_bullets(self, p, items):
        for x in items:
            self.label(p, "* " + x, pady=1)

    def b_terms(self, p, items):
        for term, desc in items:
            self.label(p, f"{term}: {desc}", pady=1)

    def b_gauge(self, p, v):
        w, h = 420, 22
        row = tk.Frame(p, bg=T.BG)
        row.pack(fill="x", pady=(4, 0))
        tk.Label(row, text=v["neg"], fg=T.RED, bg=T.BG, font=FONT_B).pack(side="left")
        c = tk.Canvas(row, width=w, height=h, bg=T.BG, highlightthickness=0)
        c.pack(side="left", padx=8)
        third = w / 3
        for i, color in enumerate((mix(T.BG, T.RED, 0.35), mix(T.BG, T.DIM, 0.35), mix(T.BG, T.GOOD, 0.35))):
            c.create_rectangle(i * third, 4, (i + 1) * third, h - 4, fill=color, outline="")
        c.create_rectangle(0, 4, w, h - 4, outline=T.DIM)
        c.create_line(w / 2, 0, w / 2, h, fill=T.DIM)
        x = (v["value"] + 1) / 2 * w
        c.create_polygon(x - 6, 0, x + 6, 0, x, 9, fill=T.AMBER, outline="")
        c.create_rectangle(x - 3, 4, x + 3, h - 4, fill=T.AMBER, outline="")
        tk.Label(row, text=v["pos"], fg=T.GOOD, bg=T.BG, font=FONT_B).pack(side="left")
        self.label(p, v["caption"], fg=T.AMBER, font=FONT_B, pady=(4, 2))

    def bar(self, parent, frac, color, width=200):
        c = tk.Canvas(parent, width=width, height=12, bg=T.BG, highlightthickness=0)
        c.create_rectangle(0, 0, width - 1, 11, outline=T.DIM)
        c.create_rectangle(1, 1, 1 + (width - 3) * max(0.0, min(frac, 1.0)), 10, fill=color, outline="")
        return c

    def b_stock(self, p, v):
        card = tk.Frame(p, bg=T.BG, highlightthickness=1, highlightbackground=T.DIM)
        card.pack(fill="x", pady=6)
        pad = tk.Frame(card, bg=T.BG)
        pad.pack(fill="x", padx=10, pady=8)
        head = tk.Frame(pad, bg=T.BG)
        head.pack(fill="x")
        tk.Label(head, text=v["ticker"], fg=T.AMBER, bg=T.BG, font=FONT_BIG).pack(side="left")
        if v["name"]:
            tk.Label(head, text=v["name"], fg=T.DIM, bg=T.BG, font=FONT).pack(side="left", padx=10)
        tk.Label(head, text=f" {v['stance_label']} ", fg=T.BG, bg=stance_color(v["stance"]), font=FONT_B).pack(side="right")
        self.label(pad, v["stance_expl"], pady=(2, 6))

        for line, frac, color in ((v["mentions_line"], v["share"] / 100, T.GOOD),
                                  (v["complete_line"], v["complete"] / 100, T.CYAN)):
            row = tk.Frame(pad, bg=T.BG)
            row.pack(fill="x", pady=1)
            self.bar(row, frac, color).pack(side="left")
            tk.Label(row, text=line, fg=T.FG, bg=T.BG, font=FONT).pack(side="left", padx=8)

        for text, color in ((v["levels_line"], T.FG), (v["rr_line"], T.AMBER), (v["reason"], T.FG), (v["expectation"], T.FG),
                            (v["confidence"], T.DIM), (v["times"], T.DIM), (v["note"], T.DIM), (v["doubtful"], T.RED),
                            (v["truncated"], T.RED)):
            if text:
                self.label(pad, text, fg=color, pady=2)
