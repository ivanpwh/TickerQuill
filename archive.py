"""Arsip analisis (folder analyses/) dan perhitungan lintas video untuk halaman KOLEKSI. Tanpa Tk.

Satu berkas JSON per analisis. Dashboard gabungan memakai analisis terbaru per video; semua angka dihitung di sini.
"""
import hashlib
import json
import statistics
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import report

STANCES = ("BUY", "WATCH", "HOLD", "SELL", "AVOID")  # urutan juga penentu bila jumlah suara sama
BEARISH = ("SELL", "AVOID")
ZONE_KEYS = ("entry", "target", "stop_loss")
CONF_SCORE = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
MARKER = ".imported"  # impor sekali dari cache sudah dilakukan


# --- rekaman -----------------------------------------------------------------------------------------------------
def build_record(raw, transcript, meta, entry, model, analyzed_at):
    """Rekaman arsip dari balasan LLM + metadata entri cache. ValueError bila balasan tidak bisa dibaca."""
    obj, truncated = report.parse_report(raw)
    d = report.compute(obj, transcript, model, truncated=truncated)
    rep = d["report"]
    is_file = meta.get("lang") == "file" or str(meta.get("vid", "")).startswith("file-")
    vid = meta.get("vid") or Path(entry).name.split(".")[0]
    return {
        "id": f"{analyzed_at.strftime('%Y%m%d-%H%M%S')}-{vid}", "vid": vid, "entry": Path(entry).name,
        "source": "file" if is_file else "youtube", "title": meta.get("title") or vid, "url": meta.get("url") or "",
        "channel": meta.get("channel") or "", "video_date": meta.get("video_date") or "",
        "analyzed_at": analyzed_at.strftime("%Y-%m-%d %H:%M"), "llm_model": model or "", "raw": raw,
        "tone": round(d["tone"], 3), "sentiment": rep["market_sentiment"], "summary": rep["summary"],
        "outlook": rep["market_outlook"], "risks": rep["risks"],
        "stocks": [{"ticker": s["ticker"], "name": s["name"], "stance": s["stance"], "share": round(s["share"], 1),
                    "levels": {k: v for k, v in s["levels"].items() if v},
                    "prices": {k: report.parse_price(s["levels"][k]) for k in report.LEVEL_KEYS},
                    "reason": s["reason"], "expectation": s["expectation"], "confidence": s["confidence"],
                    "doubtful": s["doubtful"]} for s in d["stocks"]],
    }


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def save_record(folder, record):
    path = Path(folder) / f"{record['id']}.json"
    write_json(path, record)
    return path


def load_records(folder):
    """Semua rekaman (semua versi); berkas rusak dilewati."""
    out = []
    for path in sorted(Path(folder).glob("*.json")):
        try:
            rec = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(rec, dict) and rec.get("vid") and isinstance(rec.get("stocks"), list):
            out.append(rec)
    return out


def latest_per_video(records):
    best = {}
    for rec in records:
        if rec["vid"] not in best or rec["analyzed_at"] >= best[rec["vid"]]["analyzed_at"]:
            best[rec["vid"]] = rec
    return sorted(best.values(), key=lambda r: (date_of(r), r["analyzed_at"]), reverse=True)


def delete_video(folder, vid):
    """Hapus semua versi arsip satu video; kembalikan jumlah berkas yang dihapus."""
    n = 0
    for path in Path(folder).glob(f"*-{vid}.json"):
        try:
            if json.loads(path.read_text(encoding="utf-8")).get("vid") == vid:
                path.unlink()
                n += 1
        except (OSError, ValueError):
            continue
    return n


def import_entries(folder, entries):
    """Impor sekali dari cache. entries: (path entri cache, meta berisi 'analysis' dan 'transcript').
    Setelah itu penanda ditulis, jadi video yang dihapus dari KOLEKSI tidak muncul lagi."""
    folder = Path(folder)
    if (folder / MARKER).exists():
        return 0
    n = 0
    for path, meta in entries:
        try:
            when = datetime.fromtimestamp(Path(path).stat().st_mtime)
            rec = build_record(meta["analysis"], meta.get("transcript", ""), meta, path,
                               meta.get("analysis_model", ""), when)
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            continue
        save_record(folder, rec)
        n += 1
    folder.mkdir(parents=True, exist_ok=True)
    (folder / MARKER).write_text(datetime.now().isoformat(timespec="seconds"), encoding="utf-8")
    return n


def missing_dates(records):
    """vid -> url untuk video YouTube yang belum punya tanggal upload."""
    return {r["vid"]: r["url"] for r in records if r["source"] == "youtube" and not r.get("video_date") and r["url"]}


def set_video_meta(folder, vid, video_date, channel):
    """Isi tanggal upload/channel pada semua versi arsip satu video."""
    for path in Path(folder).glob(f"*-{vid}.json"):
        try:
            rec = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if rec.get("vid") == vid:
            rec["video_date"] = video_date or rec.get("video_date", "")
            rec["channel"] = channel or rec.get("channel", "")
            write_json(path, rec)


def upload_date(info):
    """'20261021' dari yt-dlp -> '2026-10-21'; kosong bila tidak ada."""
    d = str(info.get("upload_date") or "")
    return f"{d[:4]}-{d[4:6]}-{d[6:8]}" if len(d) == 8 and d.isdigit() else ""


# --- tanggal dan pengelompokan --------------------------------------------------------------------------------------
def date_of(rec):
    return rec.get("video_date") or rec["analyzed_at"][:10]


def date_is_fallback(rec):
    return not rec.get("video_date")


def group_by_date(records):
    groups = defaultdict(list)
    for rec in records:
        groups[date_of(rec)].append(rec)
    return dict(sorted(groups.items(), reverse=True))


def views(records, ticker):
    """Pendapat tiap video tentang satu emiten, urut tanggal lalu waktu analisis."""
    out = []
    for rec in records:
        for s in rec["stocks"]:
            if s["ticker"] == ticker:
                out.append({**s, "date": date_of(rec), "fallback": date_is_fallback(rec), "title": rec["title"],
                            "channel": rec.get("channel", ""), "vid": rec["vid"], "analyzed_at": rec["analyzed_at"]})
                break
    return sorted(out, key=lambda v: (v["date"], v["analyzed_at"]))


def tickers(records):
    return sorted({s["ticker"] for rec in records for s in rec["stocks"]})


# --- perhitungan -----------------------------------------------------------------------------------------------------
def consensus(vs):
    counts = Counter(v["stance"] for v in vs)
    if not vs:
        return {"counts": {}, "dominant": None, "agreement": 0}
    dominant = max(STANCES, key=lambda s: (counts[s], -STANCES.index(s)))
    return {"counts": {s: counts[s] for s in STANCES if counts[s]}, "dominant": dominant,
            "agreement": round(100 * counts[dominant] / len(vs))}


def conflict(vs):
    stances = {v["stance"] for v in vs}
    return "BUY" in stances and bool(stances & set(BEARISH))


def price_zone(vs):
    zone = {}
    for key in ZONE_KEYS:
        vals = [v["prices"].get(key) for v in vs if v["prices"].get(key)]
        if vals:
            zone[key] = {"min": min(vals), "max": max(vals), "median": statistics.median(vals), "n": len(vals)}
    seen = Counter()
    for v in vs:
        seen.update({p for p in v["prices"].values() if p})  # satu video dihitung sekali per angka
    repeated = sorted((p, n) for p, n in seen.items() if n >= 2)
    rr = None
    if all(k in zone for k in ZONE_KEYS):
        e, tg, sl = (zone[k]["median"] for k in ZONE_KEYS)
        if sl < e < tg:
            rr = {"entry": e, "target": tg, "stop_loss": sl, "ratio": (tg - e) / (e - sl)}
    return {"levels": zone, "repeated": repeated, "rr": rr}


def changes(vs):
    out = []
    for a, b in zip(vs, vs[1:]):
        if a["stance"] != b["stance"]:
            out.append({"kind": "stance", "from": a["stance"], "to": b["stance"], "date": b["date"], "title": b["title"]})
        for key in ("target", "stop_loss"):
            x, y = a["prices"].get(key), b["prices"].get(key)
            if x and y and x != y:
                out.append({"kind": key, "from": x, "to": y, "date": b["date"], "title": b["title"]})
    return out


def reliability(vs):
    scores = [CONF_SCORE[v["confidence"]] for v in vs if v.get("confidence") in CONF_SCORE]
    avg = None
    if scores:
        mean = sum(scores) / len(scores)
        avg = min(CONF_SCORE, key=lambda k: abs(CONF_SCORE[k] - mean))
    return {"doubtful": sum(bool(v["doubtful"]) for v in vs), "n": len(vs), "confidence": avg,
            "rated": len(scores)}


def trending(records):
    rows = []
    for t in tickers(records):
        vs = views(records, t)
        c = consensus(vs)
        rows.append({"ticker": t, "videos": len(vs), "share": sum(v["share"] for v in vs) / len(vs),
                     "dominant": c["dominant"], "agreement": c["agreement"], "conflict": conflict(vs)})
    return sorted(rows, key=lambda r: (-r["videos"], -r["share"], r["ticker"]))


def tone_by_date(records):
    return [(day, sum(r["tone"] for r in recs) / len(recs), len(recs)) for day, recs in group_by_date(records).items()]


# --- cache ringkasan AI ----------------------------------------------------------------------------------------------
def ai_path(folder, kind, key, records, ui):
    """Kunci berubah bila himpunan analisis (atau bahasa) berubah: ringkasan lama dianggap usang."""
    digest = hashlib.sha1((",".join(sorted(r["id"] for r in records)) + ui).encode("utf-8")).hexdigest()[:10]
    safe = "".join(ch for ch in key if ch.isalnum() or ch in "-_")
    return Path(folder) / "ai" / f"{kind}-{safe}-{digest}.json"


def latest_ai(folder, kind, key):
    """Ringkasan AI terbaru untuk kind/key, apa pun hash-nya (untuk ditampilkan sebagai usang)."""
    safe = "".join(ch for ch in key if ch.isalnum() or ch in "-_")
    best = None
    for path in (Path(folder) / "ai").glob(f"{kind}-{safe}-*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if best is None or data.get("created", "") > best[1].get("created", ""):
            best = (path, data)
    return best
