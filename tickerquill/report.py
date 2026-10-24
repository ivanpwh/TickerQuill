"""Logika laporan: parsing JSON dari model, perhitungan lokal, metode, saran, dan blok dashboard.

Semua angka di dashboard dihitung di sini (bukan oleh AI) dari hasil ekstraksi + transkrip.
"""
import json
import re

STANCE_VALUE = {"BUY": 1.0, "WATCH": 0.25, "HOLD": 0.0, "SELL": -1.0, "AVOID": -1.0}
LEVEL_KEYS = ("entry", "target", "stop_loss", "support", "resistance")
CONFIDENCE = ("HIGH", "MEDIUM", "LOW")
SENTIMENTS = ("BULLISH", "BEARISH", "NEUTRAL", "MIXED")

# (Indonesia, English)
_T = {
    "stance_BUY": ("BELI", "BUY"), "stance_HOLD": ("TAHAN", "HOLD"), "stance_SELL": ("JUAL", "SELL"),
    "stance_WATCH": ("PANTAU", "WATCH"), "stance_AVOID": ("HINDARI", "AVOID"),
    "expl_BUY": ("Pembicara menyarankan membeli saham ini.", "The speaker suggests buying this stock."),
    "expl_HOLD": ("Pembicara menyarankan menahan (belum perlu menjual).",
                  "The speaker suggests holding (no need to sell yet)."),
    "expl_SELL": ("Pembicara menyarankan menjual saham ini.", "The speaker suggests selling this stock."),
    "expl_WATCH": ("Baru dipantau dulu, belum ada saran jelas untuk membeli.",
                   "Only on the watchlist for now, no clear buy suggestion."),
    "expl_AVOID": ("Pembicara menyarankan menghindari saham ini.", "The speaker suggests avoiding this stock."),
    "sent_BULLISH": ("Optimis (cenderung naik)", "Optimistic (leaning up)"),
    "sent_BEARISH": ("Pesimis (cenderung turun)", "Pessimistic (leaning down)"),
    "sent_NEUTRAL": ("Netral", "Neutral"), "sent_MIXED": ("Campuran", "Mixed"),
    "conf_HIGH": ("Tinggi", "High"), "conf_MEDIUM": ("Sedang", "Medium"), "conf_LOW": ("Rendah", "Low"),
    "tone_vpos": ("Sangat positif", "Very positive"), "tone_pos": ("Cenderung positif", "Leaning positive"),
    "tone_neu": ("Netral / campuran", "Neutral / mixed"), "tone_neg": ("Cenderung negatif", "Leaning negative"),
    "tone_vneg": ("Sangat negatif", "Very negative"),
    "lv_entry": ("Harga beli", "Buy price"), "lv_target": ("Target jual", "Sell target"),
    "lv_stop_loss": ("Batas rugi (stop loss)", "Loss limit (stop loss)"),
    "lv_support": ("Support (penahan)", "Support"), "lv_resistance": ("Resistance (hambatan)", "Resistance"),

    "t_summary": ("RINGKASAN SINGKAT", "QUICK SUMMARY"),
    "t_tone": ("SUASANA VIDEO (NADA PASAR)", "VIDEO MOOD (MARKET TONE)"),
    "t_stocks": ("SAHAM YANG DIBAHAS", "STOCKS DISCUSSED"),
    "t_method": ("METODE & PERHITUNGAN", "METHOD & CALCULATIONS"),
    "t_advice": ("SARAN UNTUK ANDA", "TIPS FOR YOU"),
    "t_risks": ("RISIKO YANG DISEBUT", "RISKS MENTIONED"),
    "t_quality": ("CATATAN KUALITAS TRANSKRIP", "TRANSCRIPT QUALITY NOTES"),
    "t_glossary": ("KAMUS ISTILAH", "GLOSSARY"),
    "g_neg": ("NEGATIF", "NEGATIVE"), "g_pos": ("POSITIF", "POSITIVE"),
    "tone_line": ("Skor nada: {tone:+.2f} (skala -1 sampai +1) = {label}",
                  "Tone score: {tone:+.2f} (scale -1 to +1) = {label}"),
    "ai_sent": ("Kesimpulan pembicara tentang pasar: {s}", "Speaker's overall view of the market: {s}"),
    "outlook": ("Prediksi pasar: {t}", "Market outlook: {t}"),
    "stats": ("{n} saham dibahas | {m} total sebutan di transkrip | keandalan transkrip {r}",
              "{n} stocks discussed | {m} total mentions in the transcript | transcript reliability {r}"),
    "no_stocks": ("Tidak ada saham spesifik yang berhasil dikenali dari transkrip ini.",
                  "No specific stock could be identified from this transcript."),
    "mentions": ("Disebut {n}x ({p}% dari semua sebutan saham)", "Mentioned {n}x ({p}% of all stock mentions)"),
    "complete": ("Kelengkapan rencana: {s}/100", "Plan completeness: {s}/100"),
    "rr": ("Untung:Rugi = ({t} - {e}) / ({e} - {s}) = {r}  ->  potensi untung {g}%, potensi rugi {l}%",
           "Reward:Risk = ({t} - {e}) / ({e} - {s}) = {r}  ->  potential gain {g}%, potential loss {l}%"),
    "rr_none": ("Untung:Rugi tidak bisa dihitung (butuh harga beli, target, dan batas rugi yang jelas).",
                "Reward:Risk cannot be computed (needs a clear buy price, target and loss limit)."),
    "doubtful": ("(!) Nama/angka saham ini meragukan, kemungkinan salah dengar. Cek ulang di video.",
                 "(!) This stock's name/numbers are doubtful, possibly misheard. Re-check in the video."),
    "confidence": ("Keyakinan pembicara: {c}", "Speaker confidence: {c}"),
    "times": ("Dibahas di video pada: {t}", "Discussed in the video at: {t}"),
    "reason": ("Alasan: {t}", "Reason: {t}"), "expect": ("Perkiraan: {t}", "Expectation: {t}"),
    "note": ("Catatan: {t}", "Note: {t}"),
    "unknown": ("tidak disebut", "not stated"),
    "trunc_warn": ("(!) Jawaban model terpotong sebelum selesai. Yang berhasil dibaca ditampilkan ({n} saham); "
                   "saham terakhir{l} mungkin tidak lengkap dan saham sesudahnya tidak ikut terbaca. "
                   "Tekan [ PROSES ] lagi (transkrip dipakai ulang dari cache) atau pilih model lain untuk hasil lengkap.",
                   "(!) The model's reply was cut off before it finished. What could be read is shown ({n} stocks); "
                   "the last stock{l} may be incomplete and any after it were not read. Press [ RUN ] again "
                   "(the transcript is reused from cache) or pick another model for a complete result."),
    "trunc_stock": ("(!) Data saham ini terpotong dari jawaban model dan mungkin tidak lengkap.",
                    "(!) This stock's data was cut off in the model's reply and may be incomplete."),
    "a_trunc": ("Dashboard ini mungkin belum memuat semua saham karena jawaban model terpotong. Analisis ulang "
                "sebelum memakai hasilnya.",
                "This dashboard may be missing stocks because the model's reply was cut off. Re-run the analysis "
                "before relying on it."),

    "m1h": ("1. Dari suara jadi teks", "1. From speech to text"),
    "m1": ("Audio diubah menjadi teks oleh Whisper (pengenalan suara). Hasilnya tidak sempurna: "
            "nama saham dan angka bisa salah dengar.",
            "Whisper (speech recognition) turns the audio into text. It is not perfect: "
            "stock names and numbers can be misheard."),
    "m2h": ("2. Dari teks jadi data", "2. From text to data"),
    "m2": ("Model AI ({model}) membaca transkrip lalu mengisi formulir: saham apa saja, sikap pembicara, "
            "alasan, dan level harga. AI diminta hanya mencatat yang benar-benar diucapkan.",
            "An AI model ({model}) reads the transcript and fills in a form: which stocks, the speaker's "
            "stance, reasons and price levels. It is told to record only what was actually said."),
    "m3h": ("3. Perhitungan oleh aplikasi (bukan AI)", "3. Calculations done by the app (not the AI)"),
    "m3a": ("Disebut = berapa kali ticker/nama saham muncul di transkrip. "
            "Porsi = Disebut / total semua sebutan x 100%.",
            "Mentions = how often the ticker/name appears in the transcript. "
            "Share = Mentions / all mentions x 100%."),
    "m3a_f": ("Video ini: total {T} sebutan dari {n} saham.", "This video: {T} mentions across {n} stocks."),
    "m3b": ("Nilai sikap: BELI = +1, PANTAU = +0,25, TAHAN = 0, JUAL = -1, HINDARI = -1.",
            "Stance values: BUY = +1, WATCH = +0.25, HOLD = 0, SELL = -1, AVOID = -1."),
    "m3c": ("Skor Nada = jumlah(nilai sikap x bobot) / jumlah bobot, bobot = jumlah sebutan (minimal 1). "
            "Hasil -1 = sangat negatif, 0 = netral, +1 = sangat positif.",
            "Tone Score = sum(stance value x weight) / sum(weights), weight = mentions (at least 1). "
            "-1 = very negative, 0 = neutral, +1 = very positive."),
    "m3d": ("Kelengkapan Rencana (0-100): masing-masing 20 poin bila ada harga beli, target jual, batas rugi, "
            "alasan, dan nama/angka tidak meragukan.",
            "Plan Completeness (0-100): 20 points each for a buy price, sell target, loss limit, a reason, "
            "and non-doubtful name/numbers."),
    "m3e": ("Untung:Rugi = (target - harga beli) / (harga beli - batas rugi). "
            "Potensi untung % = (target - beli) / beli x 100; potensi rugi % = (beli - batas rugi) / beli x 100. "
            "Hanya dihitung jika ketiga angka disebut dan urutannya masuk akal.",
            "Reward:Risk = (target - buy price) / (buy price - loss limit). "
            "Potential gain % = (target - buy) / buy x 100; potential loss % = (buy - loss limit) / buy x 100. "
            "Only computed when all three numbers are stated and in a sensible order."),
    "m3f": ("Keandalan transkrip = 100 x (1 - saham meragukan / total saham).",
            "Transcript reliability = 100 x (1 - doubtful stocks / total stocks)."),
    "m3f_f": ("Video ini: 100 x (1 - {k} / {n}) = {r}%", "This video: 100 x (1 - {k} / {n}) = {r}%"),
    "m4h": ("4. Batasan", "4. Limitations"),
    "m4": ("Semua angka berasal dari ucapan di video, bukan data pasar. Aplikasi tidak mengecek harga sebenarnya, "
           "kinerja perusahaan, atau apakah prediksi pembicara pernah terbukti benar.",
           "All numbers come from what was said in the video, not market data. The app does not check real prices, "
           "company performance, or whether the speaker's past predictions came true."),

    "a_base": ("Ini rangkuman OPINI pembicara di video, bukan fakta dan bukan rekomendasi resmi. Cocokkan dengan "
               "data sendiri (harga terkini, laporan keuangan, berita) sebelum mengambil keputusan.",
               "This summarises the speaker's OPINIONS, not facts or official recommendations. Compare with your "
               "own data (current price, financial statements, news) before deciding anything."),
    "a_doubt": ("Ada {n} saham dengan nama/angka yang meragukan ({l}). Putar ulang bagian videonya dan pastikan "
                "nama saham serta angkanya benar sebelum bertindak.",
                "{n} stock(s) have doubtful names/numbers ({l}). Replay those parts of the video and confirm the "
                "name and numbers before acting."),
    "a_nostop": ("{l} disarankan dibeli tetapi tidak ada batas rugi (stop loss) yang disebut. Tentukan sendiri batas "
                 "rugi yang sanggup Anda terima SEBELUM membeli; banyak panduan umum memakai kisaran 5-8% di bawah "
                 "harga beli.",
                 "{l} is suggested as a buy but no loss limit (stop loss) was mentioned. Decide your own acceptable "
                 "loss BEFORE buying; common rules of thumb use roughly 5-8% below the buy price."),
    "a_rr_low": ("Pada {l}, rasio untung:rugi hanya {r} (di bawah 1,5): potensi untung kecil dibanding risikonya.",
                 "For {l}, reward:risk is only {r} (below 1.5): the upside is small compared with the risk."),
    "a_rr_ok": ("Pada {l}, rasio untung:rugi {r} terlihat memadai berdasarkan angka yang disebut. Pastikan angkanya "
                "tidak salah dengar dan harga sekarang belum jauh dari harga beli yang disebut.",
                "For {l}, reward:risk of {r} looks reasonable on the stated numbers. Make sure the numbers were not "
                "misheard and the current price is not far from the stated buy price."),
    "a_fomo": ("Video ini sangat optimis. Waspadai FOMO (takut ketinggalan lalu ikut-ikutan). Membeli bertahap dalam "
               "beberapa kali lebih aman daripada sekaligus.",
               "This video is very optimistic. Beware of FOMO (fear of missing out). Buying in several smaller steps "
               "is safer than all at once."),
    "a_bear": ("Video ini cenderung negatif. Jika Anda sudah memegang saham yang dibahas, tinjau ulang rencana Anda, "
               "tetapi jangan panik menjual hanya karena satu video.",
               "This video leans negative. If you already hold the stocks discussed, review your plan, but do not "
               "panic-sell because of a single video."),
    "a_size": ("Jangan menaruh semua dana di satu saham. Banyak panduan umum membatasi sekitar 5-10% dana per saham "
               "dan hanya memakai uang yang siap Anda tahan jika turun.",
               "Do not put all your money into one stock. Common guidelines cap roughly 5-10% of your funds per stock "
               "and use only money you can afford to see fall."),
    "a_time": ("Saran di video bersifat jangka pendek dan cepat usang. Cek tanggal video dan harga terbaru.",
               "Advice in videos is short-term and goes stale quickly. Check the video date and the latest price."),
    "a_pro": ("Untuk keputusan besar, konsultasikan dengan penasihat investasi berlisensi.",
              "For large decisions, consult a licensed investment adviser."),
    "a_none": ("Tidak ada saham spesifik terdeteksi. Coba transkrip yang lebih lengkap atau model Whisper yang lebih besar.",
               "No specific stock detected. Try a fuller transcript or a larger Whisper model."),

    "gl": (
        [("Ticker", "Kode singkat saham di bursa, mis. BBCA, MEDC."),
         ("Harga beli (entry)", "Harga yang disebut sebagai titik masuk untuk membeli."),
         ("Target", "Harga yang diharapkan tercapai, tempat menjual untuk ambil untung."),
         ("Stop loss (batas rugi)", "Harga batas untuk keluar agar kerugian tidak membesar."),
         ("Support / Resistance", "Support: harga yang cenderung menahan penurunan. Resistance: harga yang cenderung menahan kenaikan."),
         ("Untung:Rugi", "Perbandingan potensi untung dengan potensi rugi. Angka 2 berarti potensi untung 2x lipat risikonya."),
         ("IHSG", "Indeks Harga Saham Gabungan, ukuran naik-turunnya bursa saham Indonesia secara keseluruhan."),
         ("FOMO", "Fear Of Missing Out: ikut membeli karena takut ketinggalan, bukan karena rencana.")],
        [("Ticker", "Short code of a stock on the exchange, e.g. BBCA, MEDC."),
         ("Buy price (entry)", "The price mentioned as the point to buy."),
         ("Target", "The price expected to be reached, where you would sell for profit."),
         ("Stop loss (loss limit)", "The price at which to exit so losses do not grow."),
         ("Support / Resistance", "Support: price that tends to hold a fall. Resistance: price that tends to cap a rise."),
         ("Reward:Risk", "Potential gain compared with potential loss. A value of 2 means upside is twice the risk."),
         ("IHSG", "Jakarta Composite Index, the overall measure of the Indonesian stock market."),
         ("FOMO", "Fear Of Missing Out: buying because you fear being left behind, not because of a plan.")]),

    "md_h_summary": ("RINGKASAN", "SUMMARY"), "md_h_stocks": ("SAHAM YANG DIBAHAS", "STOCKS DISCUSSED"),
    "md_h_market": ("PREDIKSI PASAR / IHSG", "MARKET OUTLOOK"), "md_h_risks": ("RISIKO & CATATAN", "RISKS & NOTES"),
    "src_label": ("Sumber", "Source"), "src_file": ("Berkas", "File"),
    "md_disclaimer": ("Ini rangkuman isi video, bukan nasihat investasi.",
                      "This is a summary of the video content, not investment advice."),
}


def t(ui, key, **kw):
    s = _T[key][1 if ui == "EN" else 0]
    return s.format(**kw) if kw else s


def _strip_trailing_commas(s):
    return re.sub(r",\s*([}\]])", r"\1", s)


def repair_truncated(s):
    """Perbaiki JSON yang terpotong di tengah: potong di titik aman terakhir (setelah nilai lengkap)
    lalu tutup semua kurung yang masih terbuka. Elemen terakhir yang belum lengkap ikut terbuang."""
    stack, safe = [], None  # safe = (indeks potong, penutup kurung yang diperlukan)
    i, n, in_str, esc = 0, len(s), False, False
    while i < n:
        c = s[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
                j = i + 1
                while j < n and s[j].isspace():
                    j += 1
                if j < n and s[j] != ":":  # string nilai (bukan nama kunci), dan sudah ada karakter sesudahnya
                    safe = (i + 1, "".join(reversed(stack)))
        elif c == '"':
            in_str = True
        elif c in "{[":
            stack.append("}" if c == "{" else "]")
        elif c in "}]":
            if stack:
                stack.pop()
            safe = (i + 1, "".join(reversed(stack)))
        elif c in "-0123456789tfn":  # angka / true / false / null
            j = i
            while j < n and s[j] not in ",}] \t\r\n":
                j += 1
            if j < n:  # token lengkap hanya bila diikuti pembatas
                safe = (j, "".join(reversed(stack)))
            i = j - 1
        i += 1
    if safe is None:
        raise ValueError("JSON terpotong terlalu awal untuk diperbaiki")
    return s[:safe[0]] + safe[1]


def parse_report(raw):
    """Return (objek, terpotong). terpotong=True bila JSON harus diperbaiki karena jawaban model tidak lengkap."""
    s = re.sub(r"<think>.*?</think>", "", raw, flags=re.S).strip()
    s = re.sub(r"^```(?:json)?\s*", "", s)
    a = s.find("{")
    if a < 0:
        raise ValueError("no JSON object in model output")
    s = re.sub(r"\s*```\s*$", "", s[a:])
    complete = s[:s.rfind("}") + 1]
    for candidate in (complete, _strip_trailing_commas(complete)):
        try:
            return json.loads(candidate), False
        except ValueError:
            pass
    return json.loads(_strip_trailing_commas(repair_truncated(s))), True


def extract_json(raw):
    return parse_report(raw)[0]


def _truthy(v):
    return v is True or str(v).strip().lower() in ("true", "1", "yes", "ya")


def _text(v):
    return "" if v is None or str(v).strip().lower() in ("null", "none") else str(v).strip()


def normalize(raw):
    stocks = []
    for s in raw.get("stocks") or []:
        if not isinstance(s, dict) or not _text(s.get("ticker")):
            continue
        lv = s.get("levels") if isinstance(s.get("levels"), dict) else {}
        stance = _text(s.get("stance")).upper()
        conf = _text(s.get("speaker_confidence")).upper()
        spoken = s.get("spoken_as") or []
        times = s.get("times") or []
        stocks.append({
            "ticker": _text(s["ticker"]).upper(),
            "name": _text(s.get("name")),
            "spoken_as": [_text(x) for x in (spoken if isinstance(spoken, list) else [spoken]) if _text(x)],
            "stance": stance if stance in STANCE_VALUE else "WATCH",
            "reason": _text(s.get("reason")), "expectation": _text(s.get("expectation")),
            "levels": {k: _text(lv.get(k)) for k in LEVEL_KEYS},
            "confidence": conf if conf in CONFIDENCE else "",
            "times": [_text(x) for x in (times if isinstance(times, list) else [times]) if _text(x)],
            "doubtful": _truthy(s.get("doubtful")), "note": _text(s.get("note")), "truncated": False,
        })
    sentiment = _text(raw.get("market_sentiment")).upper()
    risks = raw.get("risks") or []
    return {
        "summary": _text(raw.get("summary")), "market_sentiment": sentiment if sentiment in SENTIMENTS else "",
        "market_outlook": _text(raw.get("market_outlook")), "stocks": stocks,
        "risks": [_text(x) for x in (risks if isinstance(risks, list) else [risks]) if _text(x)],
        "transcript_quality": _text(raw.get("transcript_quality")),
    }


def parse_price(text):
    """'1.250' -> 1250, '1,5' -> 1.5, 'Rp 1.200 - 1.250' -> 1200 (angka pertama)."""
    m = re.search(r"\d[\d.,]*", text or "")
    if not m:
        return None
    num = m.group(0).rstrip(".,")
    if re.fullmatch(r"\d{1,3}([.,]\d{3})+", num):
        return float(re.sub(r"[.,]", "", num))
    if num.count(",") + num.count(".") > 1:
        return None
    return float(num.replace(",", "."))


def fmt_num(x, ui):
    s = f"{x:,.0f}" if abs(x - round(x)) < 1e-9 else f"{x:,.2f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".") if ui != "EN" else s


def tone_key(tone):
    if tone >= 0.5:
        return "tone_vpos"
    if tone >= 0.15:
        return "tone_pos"
    if tone <= -0.5:
        return "tone_vneg"
    if tone <= -0.15:
        return "tone_neg"
    return "tone_neu"


def compute(raw, transcript, model="", truncated=False):
    rep = normalize(raw)
    stocks = rep["stocks"]
    if truncated and stocks:
        stocks[-1]["truncated"] = True  # saham terakhir kemungkinan tidak lengkap
    for s in stocks:
        names = {s["ticker"], *s["spoken_as"]}
        if s["name"]:
            names.add(s["name"])
        pat = "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True) if n.strip())
        s["mentions"] = len(re.findall(rf"(?<![A-Za-z0-9])(?:{pat})(?![A-Za-z0-9])", transcript, re.I)) if pat else 0
        e, tg, sl = (parse_price(s["levels"][k]) for k in ("entry", "target", "stop_loss"))
        s["prices"] = (e, tg, sl)
        s["rr"] = None
        if e and tg and sl and sl < e < tg:
            gain, loss = (tg - e) / e * 100, (e - sl) / e * 100
            s["rr"] = {"ratio": gain / loss, "gain": gain, "loss": loss}
        s["completeness"] = 20 * sum([bool(s["levels"]["entry"]), bool(s["levels"]["target"]),
                                      bool(s["levels"]["stop_loss"]), bool(s["reason"]), not s["doubtful"]])
    total = sum(s["mentions"] for s in stocks)
    for s in stocks:
        s["share"] = s["mentions"] / total * 100 if total else 0.0
    stocks.sort(key=lambda s: -s["mentions"])
    weights = [max(s["mentions"], 1) for s in stocks]
    tone = sum(STANCE_VALUE[s["stance"]] * w for s, w in zip(stocks, weights)) / sum(weights) if stocks else 0.0
    doubtful = sum(s["doubtful"] for s in stocks)
    return {"report": rep, "stocks": stocks, "total_mentions": total, "weights": weights, "tone": tone,
            "doubtful": doubtful, "model": model, "truncated": truncated,
            "reliability": round(100 * (1 - doubtful / len(stocks))) if stocks else None}


def advice(d, ui):
    out = [t(ui, "a_base")]
    if d.get("truncated"):
        out.append(t(ui, "a_trunc"))
    stocks = d["stocks"]
    if not stocks:
        return out + [t(ui, "a_none")]
    bad = [s["ticker"] for s in stocks if s["doubtful"]]
    if bad:
        out.append(t(ui, "a_doubt", n=len(bad), l=", ".join(bad)))
    nostop = [s["ticker"] for s in stocks if s["stance"] == "BUY" and not s["levels"]["stop_loss"]]
    if nostop:
        out.append(t(ui, "a_nostop", l=", ".join(nostop)))
    for s in stocks:
        if s["rr"]:
            r = f"{s['rr']['ratio']:.1f}".replace(".", ",") if ui != "EN" else f"{s['rr']['ratio']:.1f}"
            out.append(t(ui, "a_rr_low" if s["rr"]["ratio"] < 1.5 else "a_rr_ok", l=s["ticker"], r=r))
    if d["tone"] >= 0.5:
        out.append(t(ui, "a_fomo"))
    elif d["tone"] <= -0.15:
        out.append(t(ui, "a_bear"))
    return out + [t(ui, "a_size"), t(ui, "a_time"), t(ui, "a_pro")]


def source_header(d, ui):
    """Blok judul + sumber (link video atau nama berkas), atau None bila data tidak membawa sumber."""
    src = d.get("source")
    if not src:
        return None
    url = src.get("url") or ""
    line = f"{t(ui, 'src_label')}: {url}" if url else f"{t(ui, 'src_file')}: {src.get('file') or src['title']}"
    return {"title": src["title"], "url": url, "line": line}


def blocks(d, ui):
    """Daftar blok tampilan netral-UI; dipakai oleh DashboardView dan ekspor teks."""
    rep, stocks = d["report"], d["stocks"]
    pct = lambda x: f"{x:.0f}"
    b = []
    head = source_header(d, ui)
    if head:
        b.append(("source", head))
    if d.get("truncated"):
        last = next((s["ticker"] for s in stocks if s["truncated"]), "")
        b.append(("warn", t(ui, "trunc_warn", n=len(stocks), l=f" ({last})" if last else "")))
    b.append(("title", t(ui, "t_summary")))
    b.append(("para", rep["summary"] or "-"))
    rel = f"{d['reliability']}%" if d["reliability"] is not None else "-"
    b.append(("dim", t(ui, "stats", n=len(stocks), m=d["total_mentions"], r=rel)))

    b.append(("title", t(ui, "t_tone")))
    b.append(("gauge", {"value": d["tone"], "neg": t(ui, "g_neg"), "pos": t(ui, "g_pos"),
                        "caption": t(ui, "tone_line", tone=d["tone"], label=t(ui, tone_key(d["tone"])))}))
    if rep["market_sentiment"]:
        b.append(("para", t(ui, "ai_sent", s=t(ui, "sent_" + rep["market_sentiment"]))))
    if rep["market_outlook"]:
        b.append(("para", t(ui, "outlook", t=rep["market_outlook"])))

    b.append(("title", t(ui, "t_stocks")))
    if not stocks:
        b.append(("para", t(ui, "no_stocks")))
    for s in stocks:
        e, tg, sl = s["prices"]
        levels = [f"{t(ui, 'lv_' + k)}: {s['levels'][k]}" for k in LEVEL_KEYS if s["levels"][k]]
        if s["rr"]:
            r = s["rr"]
            rr_line = t(ui, "rr", t=fmt_num(tg, ui), e=fmt_num(e, ui), s=fmt_num(sl, ui),
                        r=f"{r['ratio']:.1f}".replace(".", ",") if ui != "EN" else f"{r['ratio']:.1f}",
                        g=f"{r['gain']:.1f}".replace(".", ",") if ui != "EN" else f"{r['gain']:.1f}",
                        l=f"{r['loss']:.1f}".replace(".", ",") if ui != "EN" else f"{r['loss']:.1f}")
        else:
            rr_line = t(ui, "rr_none")
        b.append(("stock", {
            "ticker": s["ticker"], "name": s["name"], "stance": s["stance"],
            "stance_label": t(ui, "stance_" + s["stance"]), "stance_expl": t(ui, "expl_" + s["stance"]),
            "mentions_line": t(ui, "mentions", n=s["mentions"], p=pct(s["share"])), "share": s["share"],
            "complete": s["completeness"], "complete_line": t(ui, "complete", s=s["completeness"]),
            "levels_line": "  |  ".join(levels), "rr_line": rr_line,
            "reason": t(ui, "reason", t=s["reason"]) if s["reason"] else "",
            "expectation": t(ui, "expect", t=s["expectation"]) if s["expectation"] else "",
            "confidence": t(ui, "confidence", c=t(ui, "conf_" + s["confidence"])) if s["confidence"] else "",
            "times": t(ui, "times", t=", ".join(s["times"])) if s["times"] else "",
            "doubtful": t(ui, "doubtful") if s["doubtful"] else "",
            "truncated": t(ui, "trunc_stock") if s["truncated"] else "",
            "note": t(ui, "note", t=s["note"]) if s["note"] else ""}))

    if rep["risks"] or rep["transcript_quality"]:
        b.append(("title", t(ui, "t_risks")))
        b.append(("bullets", rep["risks"]))
        if rep["transcript_quality"]:
            b.append(("dim", t(ui, "t_quality") + ": " + rep["transcript_quality"]))

    b.append(("title", t(ui, "t_advice")))
    b.append(("bullets", advice(d, ui)))

    b.append(("title", t(ui, "t_method")))
    b.append(("method_h", t(ui, "m1h")))
    b.append(("para", t(ui, "m1")))
    b.append(("method_h", t(ui, "m2h")))
    b.append(("para", t(ui, "m2", model=d["model"] or "-")))
    b.append(("method_h", t(ui, "m3h")))
    b.append(("para", t(ui, "m3a")))
    b.append(("formula", t(ui, "m3a_f", T=d["total_mentions"], n=len(stocks))))
    b.append(("para", t(ui, "m3b")))
    b.append(("para", t(ui, "m3c")))
    if stocks:
        shown = list(zip(stocks, d["weights"]))[:6]
        terms = " + ".join(f"({STANCE_VALUE[s['stance']]:+g} x {w})" for s, w in shown)
        more = " + ..." if len(stocks) > 6 else ""
        b.append(("formula", f"({terms}{more}) / {sum(d['weights'])} = {d['tone']:+.2f}"))
    b.append(("para", t(ui, "m3d")))
    b.append(("para", t(ui, "m3e")))
    b.append(("para", t(ui, "m3f")))
    if stocks:
        b.append(("formula", t(ui, "m3f_f", k=d["doubtful"], n=len(stocks), r=d["reliability"])))
    b.append(("method_h", t(ui, "m4h")))
    b.append(("para", t(ui, "m4")))

    b.append(("title", t(ui, "t_glossary")))
    b.append(("terms", _T["gl"][1 if ui == "EN" else 0]))
    return b


def blocks_to_text(bl):
    lines = []
    for kind, v in bl:
        if kind == "source":
            lines += [f"# {v['title']}", v["line"]]
        elif kind == "title":
            lines += ["", "## " + v]
        elif kind == "method_h":
            lines += ["", "**" + v + "**"]
        elif kind == "gauge":
            pos = int((v["value"] + 1) / 2 * 30)
            lines.append(f"{v['neg']} [{'.' * pos}#{'.' * (30 - pos)}] {v['pos']}  {v['caption']}")
        elif kind == "stock":
            lines += ["", f"### {v['ticker']} - {v['stance_label']}" + (f" ({v['name']})" if v["name"] else ""),
                      v["stance_expl"], v["mentions_line"], v["complete_line"]]
            lines += [x for x in (v["levels_line"], v["rr_line"], v["reason"], v["expectation"], v["confidence"],
                                  v["times"], v["doubtful"], v["truncated"], v["note"]) if x]
        elif kind == "bullets":
            lines += [f"- {x}" for x in v]
        elif kind == "terms":
            lines += [f"- {a}: {b}" for a, b in v]
        elif kind == "formula":
            lines.append("    " + v)
        else:
            lines.append(v)
    return "\n".join(lines).strip() + "\n"


def report_markdown(d, ui):
    rep = d["report"]
    head = source_header(d, ui)
    out = [f"# {head['title']}", head["line"], ""] if head else []
    out += [f"## {t(ui, 'md_h_summary')}", rep["summary"], f"## {t(ui, 'md_h_stocks')}"]
    for s in d["stocks"]:
        out.append(f"### {s['ticker']} - {t(ui, 'stance_' + s['stance'])}" + (f" ({s['name']})" if s["name"] else ""))
        if s["reason"]:
            out.append("- " + t(ui, "reason", t=s["reason"]))
        for k in LEVEL_KEYS:
            if s["levels"][k]:
                out.append(f"- {t(ui, 'lv_' + k)}: {s['levels'][k]}")
        if s["expectation"]:
            out.append("- " + t(ui, "expect", t=s["expectation"]))
        if s["times"]:
            out.append("- " + t(ui, "times", t=", ".join(s["times"])))
        if s["doubtful"]:
            out.append("- " + t(ui, "doubtful"))
    out += [f"## {t(ui, 'md_h_market')}", rep["market_outlook"] or "-", f"## {t(ui, 'md_h_risks')}"]
    out += [f"- {x}" for x in rep["risks"]]
    if rep["transcript_quality"]:
        out.append(rep["transcript_quality"])
    out.append(t(ui, "md_disclaimer"))
    return "\n".join(out)
