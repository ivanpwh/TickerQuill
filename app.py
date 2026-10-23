"""TickerQuill: YouTube -> Whisper -> ringkasan saran & prediksi saham (tema terminal retro)."""
import hashlib
import json
import os
import queue
import re
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox

import remote
import report
from dashboard import DashboardView, open_url
from menus import MenuBar
from textclean import clean_repeats
import theme
from theme import FONT, FONT_B, T

APP_NAME = "TickerQuill"
APP_VERSION = "1.1.0"
BASE = Path(__file__).resolve().parent
CACHE = BASE / "cache"
WORK = BASE / "work"
CACHE.mkdir(exist_ok=True)
WORK.mkdir(exist_ok=True)

ENV_FILE = BASE / ".env"
GUIDE_URL = "https://github.com/ivanpwh/TickerQuill/blob/main/docs/user-guide.md"


def setting(name, default=None):
    """Baca dari app/.env (NAMA=nilai), lalu environment variable, lalu default."""
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            key, _, value = line.partition("=")
            if key.strip() == name and value.strip():
                return value.strip().strip("\"'")
    return os.environ.get(name) or default


def write_env(updates):
    """Ubah/tambah NAMA=nilai di app/.env. Komentar, baris lain, dan urutannya dibiarkan."""
    lines = ENV_FILE.read_text(encoding="utf-8").splitlines() if ENV_FILE.exists() else []
    pending = dict(updates)

    def render(key, value):
        value = value.strip()
        return f'{key}="{value}"' if re.search(r"[\s#]", value) else f"{key}={value}"

    for i, line in enumerate(lines):
        key = line.partition("=")[0].strip()
        if key in pending and not key.startswith("#"):
            lines[i] = render(key, pending.pop(key))
    lines += [render(k, v) for k, v in pending.items()]
    tmp = ENV_FILE.with_name(ENV_FILE.name + ".tmp")
    tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    tmp.replace(ENV_FILE)


NINEROUTER_URL = "http://localhost:20128/v1"
FALLBACK_MODEL = ""  # no model is assumed: every endpoint offers different ones, so a fresh install must pick one
DEFAULT_MODEL = setting("NINEROUTER_MODEL", FALLBACK_MODEL)
SETTINGS_FILE = BASE / "settings.json"


def load_settings():
    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_settings(**changes):
    SETTINGS_FILE.write_text(json.dumps({**load_settings(), **changes}, indent=2), encoding="utf-8")


def load_saved_model():
    return load_settings().get("model") or DEFAULT_MODEL


def save_model(model):
    save_settings(model=model)


def colab_conf():
    """(url, token) server Whisper di Colab: settings.json (dari dialog COLAB), lalu .env."""
    saved = load_settings()
    return (saved.get("colab_url") or setting("COLAB_WHISPER_URL", "")).strip(), \
           (saved.get("colab_token") or setting("COLAB_WHISPER_TOKEN", "")).strip()


def fetch_models():
    """Daftar model dari 9router (GET {base}/models, format OpenAI)."""
    import urllib.request

    req = urllib.request.Request(setting("NINEROUTER_BASE_URL", NINEROUTER_URL).rstrip("/") + "/models")
    key = setting("NINEROUTER_API_KEY")
    if key:
        req.add_header("Authorization", f"Bearer {key}")
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.load(resp)
    return sorted({m["id"] for m in data.get("data", []) if m.get("id")})
WHISPER_MODELS = ["large-v3", "medium", "small", "base"]
AUDIO_LANGS = {"Auto": None, "Indonesia": "id", "English": "en", "Melayu": "ms",
               "Mandarin": "zh", "Japanese": "ja", "Korean": "ko", "Arabic": "ar"}
UI_LANGS = ["ID", "EN"]
SAVE_NAME = {"DASHBOARD": "dashboard", "ANALISIS": "analysis", "TRANSKRIP": "transcript"}  # nama berkas simpan per tab
EXPORT_KEY = {"DASHBOARD": "x_dash", "ANALISIS": "x_report", "TRANSKRIP": "x_transcript"}  # isi label SALIN/SIMPAN per tab
ENGINES = ["Local", "Colab"]  # tempat Whisper berjalan: komputer ini atau GPU Google Colab

STR = {
    "ID": {
        "subtitle": "YOUTUBE >> WHISPER >> SARAN & PREDIKSI SAHAM",
        "model_btn": "[ MODEL ]", "model_title": "Pilih model 9router", "filter": "CARI>", "select": "[ PILIH ]",
        "reload": "[ MUAT ULANG ]", "close": "[ TUTUP ]", "loading": "MEMUAT DAFTAR MODEL...",
        "count": "{n} model tersedia. Klik dua kali untuk memilih.",
        "fetch_err": "Gagal memuat daftar ({e}). Ketik nama model secara manual di kolom CARI lalu tekan PILIH.",
        "open": "[ BUKA FILE ]", "open_title": "Pilih file transkrip", "empty_file": "File transkrip kosong.",
        "s_file": "2/3 MEMBACA FILE TRANSKRIP",
        "analyze": "[ PROSES ]", "cancel": "[ BATAL ]",
        "copy_fmt": "[ SALIN {x} ]", "save_fmt": "[ SIMPAN {x} ]", "x_dash": "DASHBOARD", "x_report": "HASIL",
        "x_transcript": "TRANSKRIP",
        "whisper": "MODEL WHISPER:", "audio_lang": "BAHASA AUDIO:", "ui_lang": "BAHASA APP:",
        "analysis_tab": "HASIL ANALISIS", "transcript_tab": "TRANSKRIP",
        "ready": "SIAP.", "hint": "Tempel URL video YouTube di atas, lalu tekan [ PROSES ].\n",
        "disclaimer": "! Rangkuman isi video, bukan nasihat investasi. Transkrip ASR bisa salah dengar ticker/angka.",
        "bad_url_title": "URL", "bad_url": "Masukkan URL video YouTube yang valid.",
        "cancelling": "MEMBATALKAN...", "cancelled": "DIBATALKAN", "done": "SELESAI", "error": "ERROR",
        "s_info": "1/3 MENGAMBIL INFO VIDEO", "s_dl": "1/3 UNDUH AUDIO", "s_cache": "2/3 TRANSKRIP DARI CACHE",
        "s_load": "2/3 MEMUAT MODEL WHISPER", "s_tr": "2/3 TRANSKRIP", "s_an": "3/3 ANALISIS SAHAM",
        "err_key": "NINEROUTER_API_KEY belum diset (file app/.env). Transkrip tetap tersedia di tab TRANSKRIP.",
        "lang_rule": "Tulis semua nilai teks bebas dalam Bahasa Indonesia.",
        "tab_dash": "DASHBOARD", "pause": "[ JEDA ]", "resume": "[ LANJUT ]", "paused": "DIJEDA",
        "dash_hint": "Dashboard muncul di sini setelah analisis selesai.",
        "s_resume": "2/3 MELANJUTKAN TRANSKRIP", "no_speech": "Tidak ada ucapan terdeteksi di audio ini.",
        "hist_file": "BERKAS", "hist_title": "Riwayat transkrip", "hist_empty": "Belum ada transkrip tersimpan.",
        "hist_done": "SELESAI", "hist_go": "[ PAKAI / LANJUTKAN ]", "hist_fresh": "[ ULANG DARI AWAL ]",
        "hist_del": "[ HAPUS ]", "hist_info": "{n} transkrip. Pilih satu, lalu tekan PAKAI / LANJUTKAN.",
        "hist_del_q": "Hapus transkrip ini dari riwayat? File .txt di folder transcripts tidak ikut dihapus.",
        "busy": "Proses sedang berjalan.",
        "hint_done": "[OK] Transkrip sudah ada ({model}, {date}), akan dipakai ulang.",
        "hint_part": "[..] Transkrip sebagian {pct}% ditemukan, bisa dilanjutkan.",
        "dlg_done_t": "Video sudah pernah ditranskrip",
        "dlg_done": "{title}\nModel: {model} | {date}\n\nPakai ulang transkrip ini (analisis tersimpan ditampilkan) atau transkrip ulang dari awal?",
        "dlg_part_t": "Transkrip sebagian ditemukan",
        "dlg_part": "{title}\nSelesai {pct}% (sampai {t}), model: {model}\n\nLanjutkan dari {t} atau ulangi dari awal?",
        "o_reuse": "[ PAKAI ULANG ]", "o_fresh": "[ TRANSKRIP ULANG ]", "o_resume": "[ LANJUTKAN ]",
        "o_restart": "[ ULANGI DARI AWAL ]", "o_cancel": "[ BATAL ]",
        "parse_fail": "Jawaban model bukan JSON yang valid, dashboard tidak bisa dibuat. Teks mentah ditampilkan di tab HASIL ANALISIS. Coba lagi atau pilih model lain.",
        "engine": "WHISPER DI:",
        "colab_help": "Untuk engine Colab: jalankan colab/Whisper_Server.ipynb di Google Colab (runtime GPU), lalu salin baris "
                      "\"URL TOKEN\" yang dicetak notebook dan tempel ke kolom URL. URL berubah setiap sesi Colab.",
        "colab_test": "[ TES KONEKSI ]",
        "colab_testing": "Menghubungi server...", "colab_ok": "Terhubung. Perangkat: {device}, status: {status}.",
        "colab_empty": "Isi URL dan token terlebih dulu.",
        "err_colab_cfg": "Server Colab belum diatur. Buka Alat > Pengaturan > TRANSKRIPSI, isi URL dan token dari notebook, atau pilih Whisper di Local.",
        "s_comp": "2/3 MENGOMPRESI AUDIO", "s_up": "2/3 MENGUNGGAH KE COLAB", "s_remote": "2/3 COLAB MEMUAT MODEL WHISPER",
        "err_colab": "Server Colab bermasalah: {e}\nPastikan notebook masih berjalan dan URL/token di Alat > Pengaturan > TRANSKRIPSI masih yang terbaru.",
        "s_retry_2": "2/3 MENCOBA LAGI KE COLAB", "s_retry_3": "3/3 MENCOBA LAGI ANALISIS",
        "err_step": "Langkah {step}/3 gagal: {e}", "err_tries": "Sudah dicoba {n} kali, tetap gagal.",
        "hint_tr_part": "Transkrip sebagian tersimpan. Tekan [ PROSES ], lalu pilih [ LANJUTKAN ] untuk meneruskan dari titik terakhir.",
        "hint_tr_none": "Tekan [ PROSES ] untuk mencoba lagi.",
        "hint_an": "Transkrip sudah tersimpan. Tekan [ PROSES ], lalu pilih [ PAKAI ULANG ] untuk menganalisis lagi tanpa transkripsi ulang.",
        "hint_dl_part": "Transkrip sebagian masih tersimpan: buka dari Lihat > Riwayat untuk melanjutkan setelah koneksi pulih.",
        "hist_reanalyze": "[ ANALISIS ULANG ]", "hist_open_link": "[ BUKA LINK ]", "hist_copy_link": "[ SALIN LINK ]",
        "no_saved": "Transkrip tersedia, tetapi belum ada analisis tersimpan. Tekan [ ANALISIS ULANG ] di Lihat > Riwayat untuk membuatnya.",
        "set_title": "Pengaturan",
        "m_file": "File", "m_view": "Lihat", "m_job": "Proses", "m_tools": "Alat", "m_help": "Bantuan",
        "mi_exit": "Keluar", "mi_theme": "Tema", "mi_lang": "Bahasa", "mi_colab": "Tes koneksi Colab",
        "mi_guide": "Panduan pengguna", "mi_about": "Tentang TickerQuill",
        "about": "{name} v{v}\nYouTube >> Whisper >> ringkasan saran & prediksi saham.\nLisensi MIT.\n\n{disclaimer}",
        "page_analysis": "ANALISIS", "page_history": "RIWAYAT",
        "set_help": "Langsung berlaku setelah SIMPAN. Variabel .env ditulis ke berkas .env (hanya kolom yang diubah); "
                    "pilihan lain ke settings.json. Kosongkan kolom teks untuk kembali ke nilai bawaan.",
        "set_tab_general": "UMUM", "set_tab_trans": "TRANSKRIPSI", "set_tab_llm": "ANALISIS (LLM)",
        "set_theme": "Tema tampilan", "set_whisper": "Model Whisper",
        "theme_retro_green": "Retro Hijau", "theme_retro_amber": "Retro Amber", "theme_dark": "Gelap Modern",
        "theme_light": "Terang", "theme_system": "Ikuti sistem",
        "summary": "Whisper {whisper} di {engine}  |  Audio: {audio}  |  LLM: {model}  |  klik untuk ubah",
        "set_base": "URL endpoint LLM", "set_key": "API key LLM", "set_model": "Model LLM",
        "set_applang": "Bahasa aplikasi", "set_audiolang": "Bahasa audio bawaan",
        "set_engine": "Whisper dijalankan di", "set_colab_url": "URL server Colab", "set_colab_token": "Token Colab",
        "set_pick": "[ PILIH MODEL ]",
        "err_model": "Model LLM belum diatur. Buka Alat > Pengaturan > ANALISIS (LLM), lalu ketik atau pilih model (tombol PILIH MODEL). Transkrip tetap tersedia di tab TRANSKRIP.",
        "not_set": "(belum diatur)", "llm_title": "LLM belum diatur",
        "llm_missing": "API key atau model LLM belum diisi, jadi tahap analisis akan gagal setelah transkripsi selesai (transkrip tetap tersimpan). " "Lanjutkan hanya untuk transkripsi?",
        "llm_open": "Membuka Alat > Pengaturan > ANALISIS (LLM), isi API key dan model, lalu tekan [ PROSES ] lagi.",
        "set_show": "[ TAMPIL ]", "set_hide": "[ SEMBUNYI ]", "set_save": "[ SIMPAN ]",
        "set_saved": "Tersimpan ({n} kolom) di {path}.", "set_nochange": "Tidak ada perubahan.",
        "set_err": "Gagal menyimpan: {e}",
    },
    "EN": {
        "subtitle": "YOUTUBE >> WHISPER >> STOCK ADVICE & PREDICTIONS",
        "model_btn": "[ MODEL ]", "model_title": "Select 9router model", "filter": "FIND>", "select": "[ SELECT ]",
        "reload": "[ RELOAD ]", "close": "[ CLOSE ]", "loading": "LOADING MODEL LIST...",
        "count": "{n} models available. Double-click to select.",
        "fetch_err": "Could not load the list ({e}). Type a model name manually in FIND and press SELECT.",
        "open": "[ OPEN FILE ]", "open_title": "Select transcript file", "empty_file": "The transcript file is empty.",
        "s_file": "2/3 READING TRANSCRIPT FILE",
        "analyze": "[ RUN ]", "cancel": "[ CANCEL ]",
        "copy_fmt": "[ COPY {x} ]", "save_fmt": "[ SAVE {x} ]", "x_dash": "DASHBOARD", "x_report": "REPORT",
        "x_transcript": "TRANSCRIPT",
        "whisper": "WHISPER MODEL:", "audio_lang": "AUDIO LANG:", "ui_lang": "APP LANG:",
        "analysis_tab": "REPORT", "transcript_tab": "TRANSCRIPT",
        "ready": "READY.", "hint": "Paste a YouTube video URL above, then press [ RUN ].\n",
        "disclaimer": "! Summary of the video's content, not investment advice. ASR may mishear tickers/numbers.",
        "bad_url_title": "URL", "bad_url": "Enter a valid YouTube video URL.",
        "cancelling": "CANCELLING...", "cancelled": "CANCELLED", "done": "DONE", "error": "ERROR",
        "s_info": "1/3 FETCHING VIDEO INFO", "s_dl": "1/3 DOWNLOADING AUDIO", "s_cache": "2/3 TRANSCRIPT FROM CACHE",
        "s_load": "2/3 LOADING WHISPER MODEL", "s_tr": "2/3 TRANSCRIBING", "s_an": "3/3 ANALYZING STOCKS",
        "err_key": "NINEROUTER_API_KEY is not set (app/.env). The transcript is still available in the TRANSCRIPT tab.",
        "lang_rule": "Write all free-text values in English.",
        "tab_dash": "DASHBOARD", "pause": "[ PAUSE ]", "resume": "[ RESUME ]", "paused": "PAUSED",
        "dash_hint": "The dashboard appears here once the analysis is done.",
        "s_resume": "2/3 RESUMING TRANSCRIPTION", "no_speech": "No speech was detected in this audio.",
        "hist_file": "FILE", "hist_title": "Transcript history", "hist_empty": "No saved transcripts yet.",
        "hist_done": "DONE", "hist_go": "[ USE / RESUME ]", "hist_fresh": "[ RESTART ]",
        "hist_del": "[ DELETE ]", "hist_info": "{n} transcripts. Pick one, then press USE / RESUME.",
        "hist_del_q": "Delete this transcript from history? The .txt file in the transcripts folder is kept.",
        "busy": "A job is already running.",
        "hint_done": "[OK] A transcript already exists ({model}, {date}); it will be reused.",
        "hint_part": "[..] A partial transcript ({pct}%) was found; it can be resumed.",
        "dlg_done_t": "Video already transcribed",
        "dlg_done": "{title}\nModel: {model} | {date}\n\nReuse this transcript (saved analysis is shown) or transcribe again from scratch?",
        "dlg_part_t": "Partial transcript found",
        "dlg_part": "{title}\n{pct}% done (up to {t}), model: {model}\n\nResume from {t} or start over?",
        "o_reuse": "[ REUSE ]", "o_fresh": "[ TRANSCRIBE AGAIN ]", "o_resume": "[ RESUME ]",
        "o_restart": "[ START OVER ]", "o_cancel": "[ CANCEL ]",
        "parse_fail": "The model's reply was not valid JSON, so no dashboard can be built. The raw text is shown in the REPORT tab. Try again or pick another model.",
        "engine": "WHISPER ON:",
        "colab_help": "For the Colab engine: run colab/Whisper_Server.ipynb in Google Colab (GPU runtime), then copy the "
                      "\"URL TOKEN\" line the notebook prints and paste it into the URL field. The URL changes every Colab session.",
        "colab_test": "[ TEST CONNECTION ]",
        "colab_testing": "Contacting the server...", "colab_ok": "Connected. Device: {device}, status: {status}.",
        "colab_empty": "Enter the URL and token first.",
        "err_colab_cfg": "The Colab server is not set up. Open Tools > Settings > TRANSCRIPTION, enter the URL and token from the notebook, or set Whisper to Local.",
        "s_comp": "2/3 COMPRESSING AUDIO", "s_up": "2/3 UPLOADING TO COLAB", "s_remote": "2/3 COLAB LOADING WHISPER MODEL",
        "err_colab": "Colab server problem: {e}\nMake sure the notebook is still running and the URL/token in Tools > Settings > TRANSCRIPTION are the latest.",
        "s_retry_2": "2/3 RETRYING COLAB", "s_retry_3": "3/3 RETRYING ANALYSIS",
        "err_step": "Step {step}/3 failed: {e}", "err_tries": "Tried {n} times, still failing.",
        "hint_tr_part": "A partial transcript is saved. Press [ RUN ], then choose [ RESUME ] to continue from the last point.",
        "hint_tr_none": "Press [ RUN ] to try again.",
        "hint_an": "The transcript is saved. Press [ RUN ], then choose [ REUSE ] to analyse again without transcribing.",
        "hint_dl_part": "The partial transcript is still saved: open it from View > History to resume once the connection is back.",
        "hist_reanalyze": "[ REANALYZE ]", "hist_open_link": "[ OPEN LINK ]", "hist_copy_link": "[ COPY LINK ]",
        "no_saved": "The transcript is available, but no analysis is saved yet. Press [ REANALYZE ] in View > History to create it.",
        "set_title": "Settings",
        "m_file": "File", "m_view": "View", "m_job": "Job", "m_tools": "Tools", "m_help": "Help",
        "mi_exit": "Exit", "mi_theme": "Theme", "mi_lang": "Language", "mi_colab": "Test Colab connection",
        "mi_guide": "User guide", "mi_about": "About TickerQuill",
        "about": "{name} v{v}\nYouTube >> Whisper >> stock advice & predictions summary.\nMIT licence.\n\n{disclaimer}",
        "page_analysis": "ANALYSIS", "page_history": "HISTORY",
        "set_help": "Applied right after SAVE. .env variables are written to the .env file (changed fields only); "
                    "other choices go to settings.json. Clear a text field to fall back to its default.",
        "set_tab_general": "GENERAL", "set_tab_trans": "TRANSCRIPTION", "set_tab_llm": "ANALYSIS (LLM)",
        "set_theme": "Appearance theme", "set_whisper": "Whisper model",
        "theme_retro_green": "Retro Green", "theme_retro_amber": "Retro Amber", "theme_dark": "Modern Dark",
        "theme_light": "Light", "theme_system": "Follow system",
        "summary": "Whisper {whisper} on {engine}  |  Audio: {audio}  |  LLM: {model}  |  click to change",
        "set_base": "LLM endpoint URL", "set_key": "LLM API key", "set_model": "LLM model",
        "set_applang": "App language", "set_audiolang": "Default audio language",
        "set_engine": "Run Whisper on", "set_colab_url": "Colab server URL", "set_colab_token": "Colab token",
        "set_pick": "[ PICK MODEL ]",
        "err_model": "No LLM model is set. Open Tools > Settings > ANALYSIS (LLM) and type or pick a model (PICK MODEL button). The transcript is still available in the TRANSCRIPT tab.",
        "not_set": "(not set)", "llm_title": "LLM not set up",
        "llm_missing": "The LLM API key or model is empty, so the analysis step will fail after transcription finishes (the transcript is kept). " "Continue with transcription only?",
        "llm_open": "Opening Tools > Settings > ANALYSIS (LLM). Enter the API key and model, then press [ RUN ] again.",
        "set_show": "[ SHOW ]", "set_hide": "[ HIDE ]", "set_save": "[ SAVE ]",
        "set_saved": "Saved ({n} fields) to {path}.", "set_nochange": "No changes.",
        "set_err": "Could not save: {e}",
    },
}

SYSTEM_PROMPT = """Kamu analis yang mengekstrak isi video YouTube tentang saham (kebanyakan saham Indonesia/IHSG) menjadi data terstruktur.
Tugasmu: catat APA YANG DIKATAKAN pembicara, bukan opini kamu sendiri. Jangan mengarang ticker, harga, atau target yang tidak disebut; isi null jika tidak disebut.
Transkrip dibuat oleh ASR dan sering salah dengar (nama emiten, angka). Jika ticker/angka meragukan, set "doubtful": true dan jelaskan di "note".
"times": penanda waktu "mm:ss" dari transkrip; jika transkrip tidak punya penanda waktu, isi [].
"spoken_as": tulis persis bagaimana saham itu muncul di transkrip (mis. ticker MEDC ditulis "MEDCO"), agar bisa dihitung.

Keluarkan HANYA satu objek JSON valid (tanpa teks lain, tanpa code fence) dengan skema:
{
  "summary": "2-4 kalimat inti video",
  "market_sentiment": "BULLISH | BEARISH | NEUTRAL | MIXED",
  "market_outlook": "prediksi pembicara untuk pasar/IHSG secara keseluruhan",
  "stocks": [{
    "ticker": "KODE SAHAM HURUF BESAR", "name": "nama emiten atau null", "spoken_as": ["..."],
    "stance": "BUY | HOLD | SELL | WATCH | AVOID",
    "reason": "alasan yang disebut", "expectation": "prediksi/ekspektasi yang disebut atau null",
    "levels": {"entry": null, "target": null, "stop_loss": null, "support": null, "resistance": null},
    "speaker_confidence": "HIGH | MEDIUM | LOW", "times": ["mm:ss"], "doubtful": false, "note": null
  }],
  "risks": ["peringatan/risiko yang disebut di video"],
  "transcript_quality": "bagian transkrip yang kualitasnya buruk, jika ada"
}
Jawaban harus RINGKAS agar tidak terpotong: maksimal 12 saham (pilih yang paling banyak dibahas), "reason" dan "note" maksimal 2 kalimat pendek, "spoken_as" maksimal 5 varian ejaan, "risks" maksimal 5 butir.
Nilai "levels" berupa teks angka seperti yang diucapkan (mis. "1.250"). Nilai enum (BUY, BULLISH, dst.) tetap bahasa Inggris; semua teks bebas mengikuti bahasa yang diminta di bawah.
"""


def fmt_ts(sec):
    sec = int(sec)
    return f"{sec // 3600:02d}:{sec % 3600 // 60:02d}:{sec % 60:02d}"


# --- cache transkrip: {id}.{kode}.json = selesai, {id}.{kode}.partial.json = checkpoint ------------
TXT_DIR = BASE / "transcripts"
YT_ID = re.compile(r"(?:v=|youtu\.be/|shorts/|embed/|live/)([A-Za-z0-9_-]{11})")
AUDIO_LABEL_OF = {(v or "auto"): k for k, v in AUDIO_LANGS.items()}
FILE_CODE = "file"  # pengganti kode bahasa pada entri cache yang berasal dari berkas transkrip


def video_id(url):
    m = YT_ID.search(url or "")
    return m.group(1) if m else None


def lang_code(label):
    return AUDIO_LANGS.get(label) or "auto"


def cache_paths(vid, code):
    return CACHE / f"{vid}.{code}.json", CACHE / f"{vid}.{code}.partial.json"


def read_meta(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault("title", path.stem)
    data.setdefault("transcript", "")
    data.setdefault("whisper_model", "?")
    data.setdefault("created", datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M"))
    return data


def cache_state(vid, code):
    """('done', meta) | ('partial', meta, persen) | None"""
    if not vid:
        return None
    done, partial = cache_paths(vid, code)
    try:
        if done.exists():
            return ("done", read_meta(done))
        if partial.exists():
            meta = read_meta(partial)
            pct = round(100 * meta.get("done_until", 0) / meta["duration"]) if meta.get("duration") else 0
            return ("partial", meta, pct)
    except (OSError, ValueError):
        pass
    return None


def list_history():
    items = []
    for path in sorted(CACHE.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        parts = path.name.split(".")
        if len(parts) not in (3, 4) or (len(parts) == 4 and parts[2] != "partial"):
            continue
        vid, code, partial = parts[0], parts[1], len(parts) == 4
        try:
            meta = read_meta(path)
        except (OSError, ValueError):
            continue
        pct = round(100 * meta.get("done_until", 0) / meta["duration"]) if partial and meta.get("duration") else 100
        is_file = code == FILE_CODE  # transkrip dari OPEN FILE, bukan video YouTube
        items.append({"vid": vid, "code": code, "partial": partial, "pct": pct, "meta": meta, "path": path,
                      "is_file": is_file,
                      "url": meta.get("url") or ("" if is_file else f"https://www.youtube.com/watch?v={vid}")})
    return items


def write_json_atomic(path, data):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def save_file_entry(title, text, source):
    """Catat transkrip dari berkas (OPEN FILE) di cache agar muncul di Riwayat. Isi yang sama = entri yang sama."""
    fid = "file-" + hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]
    path = CACHE / f"{fid}.{FILE_CODE}.json"
    try:
        created = read_meta(path)["created"]
    except (OSError, ValueError):
        created = datetime.now().strftime("%Y-%m-%d %H:%M")
    write_json_atomic(path, {"title": title, "url": "", "vid": fid, "lang": FILE_CODE, "whisper_model": "-",
                             "duration": 0, "created": created, "source": str(source), "transcript": text})
    return path


TRIES = 3  # percobaan otomatis untuk gangguan sementara di langkah 2 dan 3
RETRY_WAITS = (5, 15)  # detik menunggu sebelum percobaan ke-2 dan ke-3
# Langkah aktif menurut status (1 unduh, 2 transkripsi, 3 analisis); status yang tidak tercantum tidak mengubahnya
STEP_OF = {"s_info": 1, "s_dl": 1, "s_cache": 2, "s_load": 2, "s_tr": 2, "s_resume": 2, "s_comp": 2,
           "s_up": 2, "s_remote": 2, "s_retry_2": 2, "s_an": 3, "s_retry_3": 3}


class StepError(RuntimeError):
    """Gagal di langkah 2 atau 3. transient: gangguan sementara yang layak dicoba ulang otomatis."""

    def __init__(self, step, detail, transient=False, tries=1):
        super().__init__(detail)
        self.step, self.detail, self.transient, self.tries = step, detail, transient, tries


def llm_transient(e):
    """Gangguan penyedia LLM yang biasanya hilang sendiri; kunci atau model yang salah tidak termasuk."""
    import openai

    if isinstance(e, (openai.APIConnectionError, openai.RateLimitError, openai.InternalServerError)):
        return True
    # error tanpa kode HTTP, misalnya "upstream connection lost" dari router di tengah permintaan
    return isinstance(e, openai.APIError) and not isinstance(e, openai.APIStatusError)


class Cancelled(Exception):
    pass


class Pipeline:
    """Jalan di thread terpisah; kirim event (kind, payload) lewat queue."""

    def __init__(self, url, whisper_model, audio_lang, ui_lang, out_q, transcript_path=None, model=None,
                 mode="auto", engine="Local", preloaded=None, entry=None):
        self.url, self.whisper_model, self.q = url, whisper_model, out_q
        self.preloaded = preloaded  # (judul, transkrip) dari entri riwayat berkas; lewati unduh dan Whisper
        self.engine = engine  # Local | Colab
        self.mode = mode  # auto | reuse | resume | fresh
        self.audio_label = audio_lang
        self.model = model or DEFAULT_MODEL
        self.transcript_path = transcript_path
        self.audio_lang = AUDIO_LANGS[audio_lang]
        self.ui = ui_lang
        self.cancel = threading.Event()
        self.run_ev = threading.Event()  # set = berjalan, clear = dijeda
        self.run_ev.set()
        self.pct = 0
        self.step = 0  # langkah aktif (1-3) untuk pesan error; 0 = tidak ditandai, misalnya saat membuka berkas
        self.partial_path = None  # checkpoint transkripsi, untuk pesan error langkah 1 dan 2
        self.done_path = entry  # entri riwayat (transkrip selesai atau berkas); analisis yang berhasil disimpan di sini
        self.saved_analysis = None  # mode 'view': analisis tersimpan yang ditampilkan tanpa memanggil LLM

    def emit(self, kind, payload=None):
        self.q.put((kind, payload))

    def status(self, key, pct, extra=""):
        self.pct = pct
        self.step = STEP_OF.get(key, self.step)
        self.emit("status", (key, pct, extra))

    def retry_wait(self, key, attempt):
        """Jeda sebelum percobaan berikutnya; batal bila pengguna membatalkan selama jeda."""
        self.status(key, self.pct, f" ({attempt + 1}/{TRIES})")
        if self.cancel.wait(RETRY_WAITS[attempt - 1]):
            raise Cancelled()

    def failure(self, step, detail, tries=1):
        """Pesan error: langkah yang gagal, jumlah percobaan, dan langkah berikutnya yang aman dilakukan."""
        t = STR[self.ui]
        if not step:
            return detail
        lines = [t["err_step"].format(step=step, e=detail)]
        if tries > 1:
            lines.append(t["err_tries"].format(n=tries))
        saved = self.partial_path is not None and self.partial_path.exists()
        if step == 1 and saved:
            lines.append(t["hint_dl_part"])
        elif step == 2:
            lines.append(t["hint_tr_part"] if saved else t["hint_tr_none"])
        elif step == 3:
            lines.append(t["hint_an"])
        return "\n".join(lines)

    def check(self):
        if self.cancel.is_set():
            raise Cancelled()

    def pause(self):
        self.run_ev.clear()

    def resume(self):
        self.run_ev.set()

    def wait_if_paused(self, key):
        """Blok selama dijeda; pulih otomatis ke status semula saat dilanjutkan."""
        if self.run_ev.is_set():
            return
        pct = self.pct
        self.status("paused", pct, f" ({STR[self.ui][key]})")
        while not self.run_ev.wait(0.2):
            self.check()
        self.status(key, pct)

    def find_audio(self, vid):
        return next((p for p in WORK.glob(f"{vid}.*") if p.suffix not in (".part", ".ytdl")), None)

    def download_audio(self):
        import yt_dlp

        while True:
            self.status("s_dl", self.pct)

            def hook(d):
                self.check()
                if not self.run_ev.is_set():
                    raise Cancelled()  # dihentikan sementara; unduhan dilanjutkan dari file .part
                if d["status"] == "downloading" and d.get("total_bytes"):
                    self.status("s_dl", 100 * d["downloaded_bytes"] / d["total_bytes"])

            opts = {"quiet": True, "no_warnings": True, "noprogress": True, "noplaylist": True,
                    "format": "bestaudio/best", "continuedl": True,
                    "outtmpl": str(WORK / "%(id)s.%(ext)s"), "progress_hooks": [hook]}
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    ydl.download([self.url])
                return
            except Exception:
                if self.cancel.is_set():
                    raise Cancelled()
                if self.run_ev.is_set():
                    raise
                self.wait_if_paused("s_dl")

    def run(self):
        try:
            if self.preloaded:
                self.status("s_cache", 100)
                title, transcript = self.preloaded
                if self.mode != "reanalyze":  # analisis yang sudah tersimpan di entri riwayat berkas
                    self.saved_analysis = self.stored_analysis(self.done_path)
            elif self.transcript_path:
                title, transcript = self.read_transcript_file()
            else:
                _, title, transcript = self.get_transcript()
            self.emit("transcript", (title, transcript, self.source(title)))
            if self.saved_analysis is not None:  # analisis yang sudah tersimpan: tampilkan tanpa LLM
                self.emit("report_raw", (self.saved_analysis, "stop"))
                self.status("done", 100)
            elif self.mode == "view":  # buka dari riwayat: jangan memulai analisis, cukup beri tahu
                self.emit("notice", STR[self.ui]["no_saved"])
                self.status("done", 100)
            else:
                self.analyze(title, transcript)
            self.emit("done")
        except Cancelled:
            self.status("cancelled", 0)
            self.emit("done")
        except StepError as e:
            self.emit("error", self.failure(e.step, e.detail, e.tries))
        except Exception as e:
            self.emit("error", self.failure(self.step, f"{type(e).__name__}: {e}"))

    def source(self, title):
        """Asal transkrip untuk header hasil: link video, atau nama berkas (tanpa link)."""
        if self.transcript_path:
            return {"file": Path(self.transcript_path).name}
        if self.preloaded:
            try:
                return {"file": Path(read_meta(self.done_path)["source"]).name}
            except (AttributeError, OSError, ValueError, KeyError, TypeError):  # tanpa entri riwayat atau tanpa 'source'
                return {"file": title}
        return {"url": self.url}

    def read_transcript_file(self):
        self.status("s_file", 50)
        path = Path(self.transcript_path)
        transcript = clean_repeats(path.read_text(encoding="utf-8-sig", errors="replace"))
        if not transcript.strip():
            raise RuntimeError(STR[self.ui]["empty_file"])
        try:
            self.done_path = save_file_entry(path.stem, transcript, path)  # supaya muncul di Riwayat; analisis disimpan di sana
        except OSError:
            pass  # gagal mencatat riwayat tidak boleh menggagalkan analisis
        return path.stem, transcript

    def get_transcript(self):
        code = self.audio_lang or "auto"
        vid = video_id(self.url)

        if vid:  # sejak awal: dipakai pesan error dan penyimpanan analisis, termasuk saat transkrip dari cache
            self.done_path, self.partial_path = cache_paths(vid, code)

        def reuse():
            """Transkrip selesai dari cache (tanpa jaringan), kecuali mode 'fresh'/'resume'."""
            if vid and self.mode in ("auto", "reuse", "view", "reanalyze"):
                state = cache_state(vid, code)
                if state and state[0] == "done" and state[1]["transcript"].strip():
                    self.status("s_cache", 100)
                    # 'reanalyze' sengaja tidak memakai analisis tersimpan: langkah 3 dibuat ulang
                    self.saved_analysis = state[1].get("analysis") if self.mode != "reanalyze" else None
                    return vid, state[1]["title"], state[1]["transcript"]

        hit = reuse()
        if hit:
            return hit
        title = self.checkpoint_title(vid, code)  # lanjutan: judul dari checkpoint, tanpa jaringan
        if title is None:
            import yt_dlp  # hanya bila perlu jaringan; membuka riwayat dan melanjutkan dengan audio lokal tidak

            self.status("s_info", 0)
            opts = {"quiet": True, "noplaylist": True, "no_warnings": True}
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(self.url, download=False)
            vid, title = info["id"], info.get("title", info["id"])
            hit = reuse()
            if hit:
                return hit
        done_path, partial_path = cache_paths(vid, code)
        if self.mode == "fresh":
            partial_path.unlink(missing_ok=True)

        audio = self.find_audio(vid)
        if audio is None:
            self.status("s_dl", 0)
            self.download_audio()
            audio = self.find_audio(vid)

        self.partial_path, self.done_path = partial_path, done_path
        # dipakai ulang bila dibatalkan/dilanjutkan; dihapus saat selesai
        upload = WORK / "upload" / f"{vid}.ogg" if self.engine == "Colab" else None
        result = self.transcribe(audio, upload, title, vid, done_path, partial_path)
        if upload:
            upload.unlink(missing_ok=True)
        return result

    def checkpoint_title(self, vid, code):
        """Judul dari checkpoint bila audio dan checkpoint sudah ada, supaya lanjutan tidak butuh jaringan."""
        if not vid or self.mode not in ("auto", "resume"):
            return None
        partial = cache_paths(vid, code)[1]
        if not partial.exists() or self.find_audio(vid) is None:
            return None
        try:
            return read_meta(partial)["title"]
        except (OSError, ValueError, KeyError):
            return None

    def stored_analysis(self, path):
        """Analisis yang tersimpan di entri riwayat, atau None."""
        if not path or not path.exists():
            return None
        try:
            return read_meta(path).get("analysis")
        except (OSError, ValueError):
            return None

    def save_analysis(self, raw, finish):
        """Simpan analisis yang selesai di entri transkrip, supaya riwayat bisa menampilkannya tanpa LLM."""
        if not self.done_path or not self.done_path.exists() or not raw.strip() or str(finish).startswith("error"):
            return
        try:
            data = read_meta(self.done_path)
            data.update(analysis=raw, analysis_model=self.model)
            write_json_atomic(self.done_path, data)
        except (OSError, ValueError):
            pass  # gagal menyimpan salinan tidak boleh menggagalkan hasil yang sudah tampil

    def load_checkpoint(self, partial_path):
        """(baris, titik lanjut, model) dari checkpoint; kosong bila tidak ada, rusak, atau mode 'fresh'."""
        if partial_path.exists() and self.mode != "fresh":  # lanjutkan dari checkpoint
            try:
                saved = read_meta(partial_path)
                return saved["lines"], float(saved["done_until"]), saved.get("whisper_model") or self.whisper_model
            except (OSError, ValueError, KeyError):
                pass
        return [], 0.0, self.whisper_model

    def transcribe(self, audio, upload, title, vid, done_path, partial_path):
        """Langkah 2. Gangguan sementara (koneksi Colab putus) dicoba ulang dari checkpoint terakhir."""
        for attempt in range(1, TRIES + 1):
            lines, start, whisper_name = self.load_checkpoint(partial_path)  # model yang sama agar konsisten
            try:
                if upload:
                    segments, duration, device = self.colab_segments(audio, upload, whisper_name, start)
                else:
                    segments, duration, device = self.local_segments(audio, whisper_name, start)
                return self.collect(segments, duration, device, lines, start, whisper_name, title, vid,
                                    done_path, partial_path)
            except StepError as e:
                if not e.transient or attempt == TRIES:
                    e.tries = attempt
                    raise
                self.retry_wait("s_retry_2", attempt)

    def local_segments(self, audio, whisper_name, start):
        self.status("s_load", 0)
        import ctranslate2
        from faster_whisper import WhisperModel

        if ctranslate2.get_cuda_device_count() > 0:
            device, compute = "cuda", "float16"
        else:
            device, compute = "cpu", "int8"
        model = WhisperModel(whisper_name, device=device, compute_type=compute)
        kwargs = {"language": self.audio_lang, "task": "transcribe", "vad_filter": True,
                  "condition_on_previous_text": False}
        if start > 0:
            kwargs["clip_timestamps"] = str(start)
            self.status("s_resume", 0, f" ({fmt_ts(start)})")
        segments, tinfo = model.transcribe(str(audio), **kwargs)
        return segments, tinfo.duration, device.upper()

    def colab_segments(self, audio, upload, whisper_name, start):
        """Kompres audio, unggah ke server Colab, dan kembalikan aliran segmen seperti faster-whisper."""
        url, token = colab_conf()
        if not url or not token:
            raise StepError(2, STR[self.ui]["err_colab_cfg"])
        try:
            if not upload.exists():
                self.status("s_comp", 0)
                remote.compress_audio(Path(audio), upload, check=self.check)
            self.status("s_up", 0)
            events = remote.events(url, token, upload, whisper_name, self.audio_lang, start, check=self.check,
                                   on_upload=lambda frac: self.status("s_up", 100 * frac))
            for kind, value in events:
                if kind == "loading":
                    self.status("s_remote", 0)
                elif kind == "info":
                    if start > 0:
                        self.status("s_resume", 0, f" ({fmt_ts(start)})")
                    return self.guard_remote(events), value["duration"], "COLAB " + value["device"].upper()
        except remote.RemoteError as e:
            raise StepError(2, STR[self.ui]["err_colab"].format(e=e), transient=e.transient) from e
        raise StepError(2, STR[self.ui]["err_colab"].format(e="no response"))

    def guard_remote(self, events):
        """Teruskan segmen; ubah RemoteError di tengah aliran menjadi pesan yang bisa dipahami pengguna."""
        try:
            for kind, seg in events:
                if kind == "seg":
                    yield seg
        except remote.RemoteError as e:
            raise StepError(2, STR[self.ui]["err_colab"].format(e=e), transient=e.transient) from e
        finally:
            events.close()

    def collect(self, segments, duration, device, lines, start, whisper_name, title, vid, done_path,
                partial_path):
        meta = {"title": title, "url": self.url, "vid": vid, "lang": self.audio_label,
                "whisper_model": whisper_name, "duration": duration,
                "created": datetime.now().strftime("%Y-%m-%d %H:%M")}
        last_end, count = start, 0
        try:
            for seg in segments:
                self.check()
                lines.append(f"[{fmt_ts(seg.start)}] {seg.text.strip()}")
                last_end, count = seg.end, count + 1
                if count % 10 == 0:
                    write_json_atomic(partial_path, {**meta, "lines": lines, "done_until": last_end})
                self.status("s_tr", 100 * seg.end / max(duration, 1), f" ({device})")
                self.wait_if_paused("s_tr")
        except Exception:
            if lines:  # dibatalkan/error: simpan checkpoint supaya bisa dilanjutkan
                write_json_atomic(partial_path, {**meta, "lines": lines, "done_until": last_end})
            raise
        transcript = clean_repeats("\n".join(lines))
        if not transcript.strip():
            raise RuntimeError(STR[self.ui]["no_speech"])
        write_json_atomic(done_path, {**meta, "transcript": transcript})
        partial_path.unlink(missing_ok=True)
        TXT_DIR.mkdir(exist_ok=True)
        safe = re.sub(r'[\\/:*?"<>|]+', "_", title).strip()[:80]
        (TXT_DIR / f"{safe}-{vid}.txt").write_text(transcript + "\n", encoding="utf-8")
        return vid, title, transcript

    def analyze(self, title, transcript):
        self.status("s_an", 0)
        key = setting("NINEROUTER_API_KEY")
        if not key:
            raise StepError(3, STR[self.ui]["err_key"])
        if not self.model:
            raise StepError(3, STR[self.ui]["err_model"])
        from openai import OpenAI

        client = OpenAI(base_url=setting("NINEROUTER_BASE_URL", NINEROUTER_URL), api_key=key)
        messages = [{"role": "system", "content": SYSTEM_PROMPT + STR[self.ui]["lang_rule"]},
                    {"role": "user", "content": f"Judul video / Video title: {title}\n\nTRANSKRIP / TRANSCRIPT:\n{transcript}"}]
        for attempt in range(1, TRIES + 1):
            try:
                raw, finish = self.request_report(client, messages)
                break
            except Cancelled:
                raise
            except Exception as e:
                if not llm_transient(e) or attempt == TRIES:
                    raise StepError(3, f"{type(e).__name__}: {e}", tries=attempt) from e
                self.retry_wait("s_retry_3", attempt)
        self.save_analysis(raw, finish)
        self.emit("report_raw", (raw, finish))
        self.status("done", 100)

    def request_report(self, client, messages):
        """Satu permintaan analisis (streaming). Bila koneksi putus setelah sebagian jawaban diterima, jawaban itu tetap dipakai."""
        try:
            stream = client.chat.completions.create(model=self.model, stream=True, max_tokens=16000,
                                                    messages=messages)
        except Exception as e:
            if "max_tokens" not in str(e).lower():
                raise
            stream = client.chat.completions.create(model=self.model, stream=True, max_tokens=8000,
                                                    messages=messages)  # model membatasi output lebih kecil
        raw, finish = "", None
        try:
            for chunk in stream:
                self.check()
                if not chunk.choices:
                    continue
                finish = chunk.choices[0].finish_reason or finish
                text = chunk.choices[0].delta.content
                if text:
                    raw += text
                    self.status("s_an", min(95, len(raw) / 60))
        except Cancelled:
            raise
        except Exception as e:
            if not raw:
                raise
            finish = f"error: {e}"  # koneksi putus di tengah jawaban: tetap olah yang sudah diterima
        return raw, finish


class App(tk.Tk):
    def __init__(self):
        theme.apply(load_settings().get("theme") or theme.DEFAULT)  # sebelum widget apa pun dibuat
        super().__init__()
        self.title(f"{APP_NAME} v{APP_VERSION}")
        self.configure(bg=T.BG)
        self.geometry("980x720")
        self.minsize(760, 520)
        self.q = queue.Queue()
        self.pipeline = None
        self.blink = True
        self.model = load_saved_model()
        self.ui = setting("APP_LANG", "ID").upper()
        if self.ui not in STR:
            self.ui = "ID"
        self.last_status = None
        self.hint_shown = True
        self.data = None  # hasil report.compute() untuk dashboard
        self.transcript_text = ""
        self.source = None  # {"title", "url"} atau {"title", "file"}: header hasil
        self.page = "analysis"  # halaman aktif: analysis | history
        self.job_mark = None  # proses berakhir saat halaman lain terbuka: tanda di baris judul sampai ANALISIS dibuka
        self.menubar = None
        self.build()
        self.menubar = MenuBar(self, UI_LANGS)
        self.apply_lang()
        self.after(100, self.poll)
        self.after(500, self.tick_cursor)

    def tr(self, key):
        return STR[self.ui][key]

    def menu(self, parent, var, values, command=None):
        om = tk.OptionMenu(parent, var, *values, command=command)
        om.config(font=FONT, bg=T.BG, fg=T.FG, activebackground=T.FG, activeforeground=T.BG, relief="flat",
                  highlightthickness=1, highlightbackground=T.DIM, bd=0)
        om["menu"].config(font=FONT, bg=T.BG, fg=T.FG, activebackground=T.FG, activeforeground=T.BG)
        return om

    def apply_lang(self, *_):
        self.ui = self.ui_var.get()
        self.subtitle_lbl.config(text=self.tr("subtitle"))
        self.go_btn.config(text=self.tr("analyze"))
        self.stop_btn.config(text=self.tr("cancel"))
        self.open_btn.config(text=self.tr("open"))
        self.update_cache_hint()
        self.update_export_labels()
        self.page_lbl.config(text=f"›  {self.tr('page_' + self.page)}")
        self.pages["history"].apply_lang()
        if self.menubar:
            self.menubar.refresh_labels()
        self.update_summary()
        self.disclaimer_lbl.config(text=self.tr("disclaimer"))
        for pane, key in (("DASHBOARD", "tab_dash"), ("ANALISIS", "analysis_tab"), ("TRANSKRIP", "transcript_tab")):
            self.tab_btns[pane].config(text=f"[ {self.tr(key)} ]")
        self.render_status()
        if self.hint_shown:
            self.clear("ANALISIS")
            self.write("ANALISIS", self.tr("hint"), "dim")
        if self.data:
            self.render_report()
        elif self.hint_shown:
            self.dash.message(self.tr("dash_hint"))
        self.refresh_menu()

    def render_status(self):
        if self.last_status is None:
            self.status.config(text=self.tr("ready"), fg=T.AMBER)
            self.pause_btn.config(text=self.tr("pause"), state="disabled")
            self.update_indicator()
            return
        key, pct, extra = self.last_status
        self.status.config(text=self.tr(key) + extra, fg=T.AMBER)
        self.bar.config(text=self.bar_text(pct))
        pausable = key in ("s_dl", "s_load", "s_tr", "paused")
        self.pause_btn.config(text=self.tr("resume" if key == "paused" else "pause"),
                              state="normal" if pausable else "disabled")
        self.update_indicator()

    def toggle_pause(self):
        p = self.pipeline
        if not p:
            return
        if p.run_ev.is_set():
            p.pause()
            self.status.config(text=self.tr("paused") + "...")
            self.pause_btn.config(text=self.tr("resume"))
        else:
            p.resume()
            self.pause_btn.config(text=self.tr("pause"))

    def render_report(self):
        """Gambar ulang dashboard + tab ANALISIS dari self.data (juga saat ganti bahasa)."""
        self.dash.render(report.blocks(self.data, self.ui))
        self.panes["ANALISIS"][1].delete("1.0", "end")
        self.render_markdown(report.report_markdown(self.data, self.ui))

    def process_report(self, raw, finish=None):
        try:
            obj, truncated = report.parse_report(raw)
            self.data = report.compute(obj, self.transcript_text, self.model, truncated=truncated)
            if self.source:
                self.data["source"] = self.source
        except (ValueError, KeyError, TypeError, AttributeError):
            self.data = None
            self.dash.message(self.tr("parse_fail"))
            self.clear("ANALISIS")
            self.write("ANALISIS", raw)
            self.show("ANALISIS")
            return
        self.render_report()
        self.show("DASHBOARD")

    def button(self, parent, text, cmd):
        b = tk.Button(parent, text=text, command=cmd, font=FONT_B, bg=T.BG, fg=T.FG, relief="flat",
                      highlightthickness=1, highlightbackground=T.FG, activebackground=T.FG,
                      activeforeground=T.BG, disabledforeground=T.DIM, cursor="hand2", padx=10, pady=3, bd=0)
        b.bind("<Enter>", lambda e: b["state"] == "normal" and b.config(bg=T.FG, fg=T.BG))
        b.bind("<Leave>", lambda e: b.config(bg=T.BG, fg=T.AMBER if b.selected else T.FG))  # T dibaca saat event
        b.selected = False
        return b

    @staticmethod
    def mark_tabs(buttons, active):
        """Tab aktif: warna aksen + garis bawah (garis tepi tombol tidak tampil di Windows)."""
        for name, b in buttons.items():
            b.selected = name == active
            b.config(fg=T.AMBER if b.selected else T.FG, font=(*FONT_B, "underline") if b.selected else FONT_B)

    def build(self):
        head = tk.Frame(self, bg=T.BG)
        head.pack(fill="x", padx=14, pady=(12, 0))
        self.title_lbl = tk.Label(head, text="", font=("Consolas", 16, "bold"), bg=T.BG, fg=T.AMBER, anchor="w")
        self.title_lbl.pack(side="left")
        self.page_lbl = tk.Label(head, text="", font=("Consolas", 16, "bold"), bg=T.BG, fg=T.FG, anchor="w")
        self.page_lbl.pack(side="left", padx=(6, 0))
        # status proses saat halaman lain terbuka; klik untuk kembali ke ANALISIS
        self.job_lbl = tk.Label(head, text="", font=FONT_B, bg=T.BG, fg=T.CYAN, anchor="e", cursor="hand2")
        self.job_lbl.pack(side="right")
        self.job_lbl.bind("<Button-1>", lambda e: self.show_page("analysis"))
        self.subtitle_lbl = tk.Label(self, text="", font=FONT, bg=T.BG, fg=T.DIM, anchor="w")
        self.subtitle_lbl.pack(fill="x", padx=14)
        tk.Frame(self, bg=T.FG, height=1).pack(fill="x", padx=14, pady=8)
        self.disclaimer_lbl = tk.Label(self, text="", font=("Consolas", 9), bg=T.BG, fg=T.DIM, anchor="w")
        self.disclaimer_lbl.pack(side="bottom", fill="x", padx=14, pady=(0, 8))
        self.theme_var = tk.StringVar(value=theme.current)

        holder = tk.Frame(self, bg=T.BG)  # wadah halaman: satu tampil, yang lain tetap utuh di belakang
        holder.pack(fill="both", expand=True)
        page = tk.Frame(holder, bg=T.BG)  # halaman ANALISIS
        self.pages = {"analysis": page, "history": HistoryPage(holder, self)}

        row = tk.Frame(page, bg=T.BG)
        row.pack(fill="x", padx=14)
        tk.Label(row, text="URL>", font=FONT_B, bg=T.BG, fg=T.FG).pack(side="left")
        self.url_var = tk.StringVar()
        self.url = tk.Entry(row, textvariable=self.url_var, font=FONT, bg=T.BG, fg=T.FG, insertbackground=T.FG,
                            relief="flat", highlightthickness=1, highlightbackground=T.DIM, highlightcolor=T.FG)
        self.url.pack(side="left", fill="x", expand=True, padx=8, ipady=4)
        self.url.bind("<Return>", lambda e: self.start())
        self.go_btn = self.button(row, "", self.start)
        self.go_btn.pack(side="left")
        self.open_btn = self.button(row, "", self.open_file)
        self.open_btn.pack(side="left", padx=(6, 0))
        self.cache_lbl = tk.Label(page, text="", font=("Consolas", 10), bg=T.BG, fg=T.CYAN, anchor="w")
        self.cache_lbl.pack(fill="x", padx=14, pady=(4, 0))

        whisper = load_settings().get("whisper_model")
        self.model_var = tk.StringVar(value=whisper if whisper in WHISPER_MODELS else WHISPER_MODELS[0])
        self.audio_var = tk.StringVar(value=setting("AUDIO_LANG", "Indonesia"))
        if self.audio_var.get() not in AUDIO_LANGS:
            self.audio_var.set("Indonesia")
        self.ui_var = tk.StringVar(value=self.ui)
        engine = load_settings().get("engine") or setting("WHISPER_ENGINE", "Local")
        self.engine_var = tk.StringVar(value=engine if engine in ENGINES else "Local")
        self.engine_var.trace_add("write", lambda *_: save_settings(engine=self.engine_var.get()))
        self.url_var.trace_add("write", self.update_cache_hint)
        self.audio_var.trace_add("write", self.update_cache_hint)
        # pengaturan Whisper/bahasa/model ada di Alat > Pengaturan; di sini cukup ringkasan yang bisa diklik
        self.summary_lbl = tk.Label(page, text="", font=("Consolas", 10), bg=T.BG, fg=T.DIM, anchor="w", cursor="hand2")
        self.summary_lbl.pack(fill="x", padx=14, pady=(6, 0))
        self.summary_lbl.bind("<Button-1>", lambda e: self.open_settings())
        for var in (self.model_var, self.audio_var, self.engine_var):
            var.trace_add("write", lambda *_: self.update_summary())

        status_row = tk.Frame(page, bg=T.BG)  # status + kontrol proses yang sedang berjalan
        status_row.pack(fill="x", padx=14, pady=(10, 0))
        self.stop_btn = self.button(status_row, "", self.stop)
        self.stop_btn.pack(side="right")
        self.stop_btn.config(state="disabled")
        self.pause_btn = self.button(status_row, "", self.toggle_pause)
        self.pause_btn.pack(side="right", padx=6)
        self.pause_btn.config(state="disabled")
        self.status = tk.Label(status_row, text="", font=FONT_B, bg=T.BG, fg=T.AMBER, anchor="w")
        self.status.pack(side="left", fill="x", expand=True)
        self.bar = tk.Label(page, text=self.bar_text(0), font=FONT, bg=T.BG, fg=T.FG, anchor="w")
        self.bar.pack(fill="x", padx=14)

        tabs = tk.Frame(page, bg=T.BG)
        tabs.pack(fill="x", padx=14, pady=(10, 0))
        self.tab_btns = {}
        for name in ("DASHBOARD", "ANALISIS", "TRANSKRIP"):
            b = self.button(tabs, "", lambda n=name: self.show(n))
            b.pack(side="left", padx=(0, 6))
            self.tab_btns[name] = b
        self.save_btn = self.button(tabs, "", self.save)
        self.save_btn.pack(side="right")
        self.copy_btn = self.button(tabs, "", self.copy)
        self.copy_btn.pack(side="right", padx=6)

        self.panes = {}
        holder = tk.Frame(page, bg=T.BG, highlightthickness=1, highlightbackground=T.FG)
        holder.pack(fill="both", expand=True, padx=14, pady=8)
        for name in ("ANALISIS", "TRANSKRIP"):
            frame = tk.Frame(holder, bg=T.BG)
            sb = tk.Scrollbar(frame, troughcolor=T.BG, bg=T.DIM, relief="flat", bd=0, width=12)
            txt = tk.Text(frame, font=FONT, bg=T.BG, fg=T.FG, insertbackground=T.FG, relief="flat", wrap="word",
                          padx=10, pady=8, yscrollcommand=sb.set, selectbackground=T.DIM, spacing3=2)
            sb.config(command=txt.yview)
            sb.pack(side="right", fill="y")
            txt.pack(side="left", fill="both", expand=True)
            txt.tag_config("h1", foreground=T.AMBER, font=("Consolas", 13, "bold"))
            txt.tag_config("h2", foreground=T.AMBER, font=FONT_B)
            txt.tag_config("bold", font=FONT_B)
            txt.tag_config("dim", foreground=T.DIM)
            txt.tag_config("err", foreground=T.RED)
            txt.tag_config("link", foreground=T.CYAN, underline=True)
            txt.tag_bind("link", "<Enter>", lambda e, t=txt: t.config(cursor="hand2"))
            txt.tag_bind("link", "<Leave>", lambda e, t=txt: t.config(cursor="xterm"))
            self.panes[name] = (frame, txt)
        self.dash = DashboardView(holder)
        self.show("DASHBOARD")
        page.pack(fill="both", expand=True)

    def bar_text(self, pct, width=40):
        n = int(width * pct / 100)
        return f"[{'█' * n}{'░' * (width - n)}] {int(pct):3d}%"

    def tick_cursor(self):
        self.blink = not self.blink
        self.title_lbl.config(text=f"{APP_NAME} v{APP_VERSION}" + ("_" if self.blink else " "))
        self.after(500, self.tick_cursor)

    def show(self, name):
        self.current = name
        self.dash.pack_forget()
        for n, (frame, _) in self.panes.items():
            frame.pack_forget()
        (self.dash if name == "DASHBOARD" else self.panes[name][0]).pack(fill="both", expand=True)
        self.mark_tabs(self.tab_btns, name)
        self.update_export_labels()
        self.refresh_menu()

    def show_tab(self, name):
        """Dari menu Lihat: buka halaman ANALISIS pada tab hasil tertentu."""
        self.show_page("analysis")
        self.show(name)

    def show_page(self, name):
        self.page = name
        for frame in self.pages.values():
            frame.pack_forget()
        self.pages[name].pack(fill="both", expand=True)
        self.page_lbl.config(text=f"›  {self.tr('page_' + name)}")
        if name == "analysis":
            self.job_mark = None
        elif name == "history":
            self.pages["history"].reload()
        self.update_indicator()
        self.refresh_menu()

    def update_indicator(self):
        """Ringkasan proses di baris judul, hanya saat halaman lain terbuka."""
        text, color = "", T.CYAN
        if self.page != "analysis":
            if self.busy():
                pct = self.last_status[1] if self.last_status else 0
                text = f"● {self.status.cget('text')} {int(pct)}%"
            elif self.job_mark:
                text = f"{self.job_mark} {self.status.cget('text')}"
                color = T.RED if self.job_mark == "!" else T.CYAN
        self.job_lbl.config(text=text, fg=color)

    def busy(self):
        return self.go_btn["state"] == "disabled"

    def can_export(self):
        if self.page != "analysis":
            return False
        if self.current == "DASHBOARD":
            return bool(self.data)
        return bool(self.panes[self.current][1].get("1.0", "end").strip())

    def refresh_menu(self):
        if self.menubar:
            self.menubar.refresh_state()

    def update_export_labels(self):
        """SALIN/SIMPAN menyebut isi tab yang aktif."""
        x = self.tr(EXPORT_KEY[self.current])
        self.copy_btn.config(text=self.tr("copy_fmt").format(x=x))
        self.save_btn.config(text=self.tr("save_fmt").format(x=x))

    def write(self, pane, text, tag=None):
        txt = self.panes[pane][1]
        txt.insert("end", text, tag)
        txt.see("end")

    def clear(self, pane):
        self.panes[pane][1].delete("1.0", "end")

    def render_markdown(self, text):
        txt = self.panes["ANALISIS"][1]
        txt.delete("1.0", "end")
        for tag in txt.tag_names():
            if tag.startswith("url-"):  # tag per link dari render sebelumnya
                txt.tag_delete(tag)
        for line in text.splitlines():
            m = re.match(r"^(#{1,4})\s*(.*)", line)
            if m:
                tag = "h1" if len(m.group(1)) <= 2 else "h2"
                txt.insert("end", m.group(2) + "\n", tag)
                continue
            for part in re.split(r"(\*\*.+?\*\*)", line):
                if part.startswith("**") and part.endswith("**") and len(part) > 4:
                    txt.insert("end", part[2:-2], "bold")
                    continue
                for piece in re.split(r"(https?://\S+)", part):
                    if piece.startswith(("http://", "https://")):  # link bisa diklik
                        tag = f"url-{txt.index('end')}"
                        txt.insert("end", piece, ("link", tag))
                        txt.tag_bind(tag, "<Button-1>", lambda e, u=piece: open_url(u))
                    elif piece:
                        txt.insert("end", piece)
            txt.insert("end", "\n")

    def llm_ready(self):
        return bool(setting("NINEROUTER_API_KEY") and self.model)

    def set_model(self, model):
        self.model = model
        save_model(model)
        self.update_summary()

    def update_summary(self):
        self.summary_lbl.config(text=self.tr("summary").format(
            whisper=self.model_var.get(), engine=self.engine_var.get(), audio=self.audio_var.get(),
            model=self.model or self.tr("not_set")))

    def open_settings(self, page=None, **kw):
        dlg = getattr(self, "settings_dlg", None)
        if dlg is not None and dlg.winfo_exists():
            dlg.lift()
            if page:
                dlg.show(page)
            return dlg
        self.settings_dlg = SettingsDialog(self, page=page or "general", **kw)
        return self.settings_dlg

    def reopen_settings(self):
        """Tema/bahasa diganti dari menu: dialog Pengaturan yang terbuka dibuat ulang dengan nilai baru."""
        dlg = getattr(self, "settings_dlg", None)
        if dlg is not None and dlg.winfo_exists():
            page = dlg.page
            dlg.destroy()
            self.open_settings(page=page)

    def menu_theme(self, name):
        self.set_theme(name)
        self.reopen_settings()

    def set_lang(self, code):
        if code == self.ui:
            return
        write_env({"APP_LANG": code})
        self.ui_var.set(code)
        self.apply_lang()
        self.reopen_settings()

    def pick_model(self):
        ModelPicker(self)

    def test_colab(self):
        self.open_settings(page="trans").test()

    def open_guide(self):
        try:
            os.startfile(BASE / "docs" / "user-guide.md")  # salinan lokal sesuai versi aplikasi ini
        except (AttributeError, OSError):  # bukan Windows, berkas tidak ada, atau tanpa aplikasi pembuka .md
            open_url(GUIDE_URL)

    def show_about(self):
        messagebox.showinfo(self.tr("mi_about"), self.tr("about").format(
            name=APP_NAME, v=APP_VERSION, disclaimer=self.tr("disclaimer")), parent=self)

    def set_theme(self, name):
        """Ganti tema langsung: warnai ulang widget yang ada, gambar ulang dashboard (canvas), simpan pilihan."""
        save_settings(theme=name)
        self.theme_var.set(name)
        if name == theme.current:
            return
        old = theme.apply(name)
        theme.recolor(self, old, theme.palette())
        self.show(self.current)
        if self.data:
            self.render_report()

    def open_file(self):
        path = filedialog.askopenfilename(
            title=self.tr("open_title"),
            filetypes=[("Transcript", "*.txt *.md *.srt *.vtt"), ("*", "*.*")])
        if path:
            self.start(transcript_path=path)

    def update_cache_hint(self, *_):
        state = cache_state(video_id(self.url_var.get()), lang_code(self.audio_var.get()))
        if not state:
            self.cache_lbl.config(text="")
        elif state[0] == "done":
            self.cache_lbl.config(text=self.tr("hint_done").format(
                model=state[1]["whisper_model"], date=state[1]["created"]))
        else:
            self.cache_lbl.config(text=self.tr("hint_part").format(pct=state[2]))

    def ask_cache_mode(self, state):
        """Dialog pilihan bila video sudah pernah ditranskrip. Return mode atau None (batal)."""
        meta = state[1]
        if state[0] == "done":
            return ChoiceDialog.ask(
                self, self.tr("dlg_done_t"),
                self.tr("dlg_done").format(title=meta["title"], model=meta["whisper_model"], date=meta["created"]),
                [("reuse", self.tr("o_reuse")), ("fresh", self.tr("o_fresh")), (None, self.tr("o_cancel"))])
        return ChoiceDialog.ask(
            self, self.tr("dlg_part_t"),
            self.tr("dlg_part").format(title=meta["title"], pct=state[2], t=fmt_ts(meta.get("done_until", 0)),
                                       model=meta["whisper_model"]),
            [("resume", self.tr("o_resume")), ("fresh", self.tr("o_restart")), (None, self.tr("o_cancel"))])

    def start(self, transcript_path=None, mode=None, preloaded=None, entry=None):
        if self.busy():
            return
        self.show_page("analysis")
        url = self.url.get().strip()
        from_file = bool(transcript_path or preloaded)  # hanya analisis: tanpa unduh dan Whisper
        if not from_file and not re.match(r"^https?://", url):
            messagebox.showwarning(self.tr("bad_url_title"), self.tr("bad_url"))
            return
        if not self.llm_ready():  # beri tahu sebelum menunggu transkripsi yang berujung error di tahap analisis
            if from_file or not messagebox.askyesno(self.tr("llm_title"), self.tr("llm_missing")):
                messagebox.showinfo(self.tr("llm_title"), self.tr("llm_open"))
                self.open_settings(page="llm")
                return
        if not from_file and mode is None:
            state = cache_state(video_id(url), lang_code(self.audio_var.get()))
            mode = "auto"
            if state:
                mode = self.ask_cache_mode(state)
                if mode is None:
                    return
        self.hint_shown = False
        self.last_status = None
        self.data = None
        self.transcript_text = ""
        self.source = None
        self.clear("ANALISIS")
        self.clear("TRANSKRIP")
        self.dash.message(self.tr("dash_hint"))
        self.go_btn.config(state="disabled")
        self.open_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.job_mark = None
        self.pipeline = Pipeline(url, self.model_var.get(), self.audio_var.get(), self.ui, self.q,
                                 transcript_path=transcript_path, model=self.model, mode=mode or "auto",
                                 engine=self.engine_var.get(), preloaded=preloaded, entry=entry)
        threading.Thread(target=self.pipeline.run, daemon=True).start()
        self.refresh_menu()

    def stop(self):
        if self.pipeline:
            self.pipeline.cancel.set()
            self.status.config(text=self.tr("cancelling"))

    def finish(self, failed=False):
        self.go_btn.config(state="normal")
        self.open_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.pause_btn.config(state="disabled")
        self.update_cache_hint()
        if self.page != "analysis":  # tidak pindah halaman sendiri; tandai di baris judul
            cancelled = self.last_status and self.last_status[0] == "cancelled"
            self.job_mark = "!" if failed else "■" if cancelled else "✓"
        self.pages["history"].reload()  # entri atau analisis baru langsung terlihat
        self.update_indicator()
        self.refresh_menu()

    def poll(self):
        got = False
        try:
            while True:
                kind, p = self.q.get_nowait()
                if kind == "status":
                    self.last_status = p
                    self.render_status()
                elif kind == "transcript":
                    title, self.transcript_text, src = p
                    self.source = {"title": title, **src}
                    self.write("TRANSKRIP", f"{title}\n\n{self.transcript_text}")
                elif kind == "report_raw":
                    self.process_report(*p)
                elif kind == "error":
                    self.status.config(text=self.tr("error"), fg=T.RED)
                    self.write("ANALISIS", f"\n! {p}\n", "err")
                    self.dash.message(f"! {p}")
                    self.show("ANALISIS")
                    self.finish(failed=True)
                elif kind == "notice":
                    self.write("ANALISIS", f"\n{p}\n", "dim")
                    self.dash.message(p)
                    self.show("DASHBOARD")
                elif kind == "done":
                    self.finish()
                got = True
        except queue.Empty:
            pass
        if got:
            self.refresh_menu()
        self.after(100, self.poll)

    def content(self):
        if self.current == "DASHBOARD":
            return report.blocks_to_text(report.blocks(self.data, self.ui)) if self.data else ""
        if self.current == "ANALISIS" and self.data:
            return report.report_markdown(self.data, self.ui)
        return self.panes[self.current][1].get("1.0", "end").strip()

    def copy(self):
        self.clipboard_clear()
        self.clipboard_append(self.content())

    def save(self):
        ext, kind = (".txt", "Teks") if self.current == "TRANSKRIP" else (".md", "Markdown")
        path = filedialog.asksaveasfilename(defaultextension=ext, filetypes=[(kind, f"*{ext}")],
                                            initialfile=f"{APP_NAME.lower()}-{SAVE_NAME[self.current]}{ext}")
        if path:
            Path(path).write_text(self.content(), encoding="utf-8")


class ChoiceDialog(tk.Toplevel):
    """Dialog modal retro dengan beberapa tombol pilihan."""

    def __init__(self, app, title, message, options):
        super().__init__(app)
        self.choice = None
        self.title(title)
        self.configure(bg=T.BG)
        self.transient(app)
        tk.Label(self, text=message, font=FONT, bg=T.BG, fg=T.FG, justify="left", anchor="w", wraplength=520
                 ).pack(fill="x", padx=16, pady=(16, 12))
        row = tk.Frame(self, bg=T.BG)
        row.pack(fill="x", padx=16, pady=(0, 16))
        for key, label in options:
            app.button(row, label, lambda k=key: self.pick(k)).pack(side="left", padx=(0, 8))
        self.protocol("WM_DELETE_WINDOW", lambda: self.pick(None))
        self.update_idletasks()
        self.geometry(f"+{app.winfo_rootx() + 80}+{app.winfo_rooty() + 120}")
        self.grab_set()

    def pick(self, key):
        self.choice = key
        self.destroy()

    @classmethod
    def ask(cls, app, title, message, options):
        dlg = cls(app, title, message, options)
        app.wait_window(dlg)
        return dlg.choice


class HistoryPage(tk.Frame):
    """Halaman RIWAYAT: transkrip tersimpan; pakai ulang yang selesai, lanjutkan yang sebagian, atau hapus."""

    def __init__(self, parent, app):
        super().__init__(parent, bg=T.BG)
        self.app, self.items = app, []
        self.info = tk.Label(self, text="", font=FONT, bg=T.BG, fg=T.AMBER, anchor="w")
        self.info.pack(fill="x", padx=14, pady=(0, 4))
        holder = tk.Frame(self, bg=T.BG, highlightthickness=1, highlightbackground=T.FG)
        holder.pack(fill="both", expand=True, padx=14, pady=6)
        sb = tk.Scrollbar(holder, troughcolor=T.BG, bg=T.DIM, relief="flat", bd=0, width=12)
        self.list = tk.Listbox(holder, font=FONT, bg=T.BG, fg=T.FG, selectbackground=T.FG, selectforeground=T.BG,
                               relief="flat", highlightthickness=0, activestyle="none", yscrollcommand=sb.set)
        sb.config(command=self.list.yview)
        sb.pack(side="right", fill="y")
        self.list.pack(side="left", fill="both", expand=True, padx=4, pady=4)
        self.list.bind("<Double-Button-1>", lambda e: self.go("auto"))
        self.list.bind("<<ListboxSelect>>", lambda e: self.update_detail())
        detail = tk.Frame(self, bg=T.BG)  # judul lengkap + link video (atau path berkas) dari item terpilih
        detail.pack(fill="x", padx=14, pady=(0, 8))
        self.d_title = tk.Label(detail, text="", font=FONT_B, bg=T.BG, fg=T.AMBER, anchor="w", justify="left",
                                wraplength=780)
        self.d_title.pack(fill="x")
        row = tk.Frame(detail, bg=T.BG)
        row.pack(fill="x", pady=(2, 0))
        self.copy_link_btn = app.button(row, "", self.copy_link)
        self.copy_link_btn.pack(side="right")
        self.open_link_btn = app.button(row, "", self.open_link)
        self.open_link_btn.pack(side="right", padx=6)
        self.d_link = tk.Label(row, text="", font=FONT, bg=T.BG, fg=T.CYAN, anchor="w")
        self.d_link.pack(side="left", fill="x", expand=True)
        bottom = tk.Frame(self, bg=T.BG)
        bottom.pack(fill="x", padx=14, pady=(0, 8))
        self.labelled = [(self.copy_link_btn, "hist_copy_link"), (self.open_link_btn, "hist_open_link")]
        for key, cmd, pad in (("hist_go", lambda: self.go("auto"), 0), ("hist_reanalyze", lambda: self.go("reanalyze"), 6),
                              ("hist_fresh", lambda: self.go("fresh"), 0), ("hist_del", self.delete, 6)):
            b = app.button(bottom, "", cmd)
            b.pack(side="left", padx=pad)
            self.labelled.append((b, key))
        self.apply_lang()

    def apply_lang(self):
        for b, key in self.labelled:
            b.config(text=self.app.tr(key))
        self.reload()

    def reload(self):
        self.items = list_history()
        self.list.delete(0, "end")
        for it in self.items:
            m = it["meta"]
            status = f"{it['pct']:3d}%" if it["partial"] else self.app.tr("hist_done")
            label = self.app.tr("hist_file") if it["is_file"] else AUDIO_LABEL_OF.get(it["code"], it["code"])
            self.list.insert("end", f"{status:>8}  {m['title'][:46]:<46}  {label:<9} {m['whisper_model']:<9} {m['created']}")
        self.info.config(text=self.app.tr("hist_info").format(n=len(self.items)) if self.items
                         else self.app.tr("hist_empty"), fg=T.AMBER)
        self.update_detail()

    def link_of(self, it):
        """Yang disalin SALIN LINK: link video, atau path berkas untuk entri berkas."""
        return (it["meta"].get("source") or "") if it["is_file"] else it["url"]

    def update_detail(self):
        it = self.selected()
        if not it:
            self.d_title.config(text="")
            self.d_link.config(text="")
            self.open_link_btn.config(state="disabled")
            self.copy_link_btn.config(state="disabled")
            return
        link = self.link_of(it)
        self.d_title.config(text=it["meta"]["title"])
        if it["is_file"]:
            self.d_link.config(text=f"{report.t(self.app.ui, 'src_file')}: {link or '-'}", fg=T.DIM)
        else:
            self.d_link.config(text=link, fg=T.CYAN)
        self.open_link_btn.config(state="disabled" if it["is_file"] or not link else "normal")
        self.copy_link_btn.config(state="normal" if link else "disabled")

    def open_link(self):
        it = self.selected()
        if it and not it["is_file"]:
            open_url(it["url"])

    def copy_link(self):
        it = self.selected()
        if it and self.link_of(it):
            self.clipboard_clear()
            self.clipboard_append(self.link_of(it))

    def selected(self):
        sel = self.list.curselection()
        return self.items[sel[0]] if sel else None

    def go(self, mode):
        it = self.selected()
        if not it:
            return
        if self.app.busy():  # proses lain masih berjalan: tetap di halaman ini
            self.info.config(text=self.app.tr("busy"), fg=T.RED)
            return
        if it["is_file"]:  # transkrip dari berkas: tampilkan hasil tersimpan, atau analisis ulang bila diminta
            self.app.start(preloaded=(it["meta"]["title"], it["meta"]["transcript"]),
                           mode="view" if mode == "auto" else "reanalyze", entry=it["path"])
            return
        if mode == "auto":  # belum selesai: lanjutkan; selesai: tampilkan dashboard, analisis, dan transkrip
            mode = "resume" if it["partial"] else "view"
        elif mode == "reanalyze" and it["partial"]:  # analisis butuh transkrip lengkap: selesaikan dulu
            mode = "resume"
        self.app.url_var.set(it["url"])
        self.app.audio_var.set(AUDIO_LABEL_OF.get(it["code"], "Auto"))
        self.app.start(mode=mode)

    def delete(self):
        it = self.selected()
        if it and messagebox.askyesno(self.app.tr("hist_title"), self.app.tr("hist_del_q"), parent=self.app):
            it["path"].unlink(missing_ok=True)
            self.reload()
            self.app.update_cache_hint()


class SettingsDialog(tk.Toplevel):
    """Pengaturan bertab: UMUM (bahasa, tema), TRANSKRIPSI (Whisper, Colab), ANALISIS (LLM).
    Variabel .env ditulis ke .env, pilihan lain ke settings.json; semuanya langsung diterapkan."""

    # (halaman, kunci, kunci label, jenis, tempat simpan); jenis: text | secret | choice; env = variabel .env
    FIELDS = (("general", "APP_LANG", "set_applang", "choice", "env"),
              ("general", "theme", "set_theme", "choice", "json"),
              ("trans", "WHISPER_ENGINE", "set_engine", "choice", "env"),
              ("trans", "whisper_model", "set_whisper", "choice", "json"),
              ("trans", "AUDIO_LANG", "set_audiolang", "choice", "env"),
              ("trans", "COLAB_WHISPER_URL", "set_colab_url", "text", "env"),
              ("trans", "COLAB_WHISPER_TOKEN", "set_colab_token", "secret", "env"),
              ("llm", "NINEROUTER_BASE_URL", "set_base", "text", "env"),
              ("llm", "NINEROUTER_API_KEY", "set_key", "secret", "env"),
              ("llm", "NINEROUTER_MODEL", "set_model", "text", "env"))
    PAGES = (("general", "set_tab_general"), ("trans", "set_tab_trans"), ("llm", "set_tab_llm"))

    def __init__(self, app, page="general", notice=""):
        super().__init__(app)
        self.app, self.result, self.page = app, None, page
        colab_url, colab_token = colab_conf()
        self.initial = {"APP_LANG": app.ui, "theme": theme.current, "WHISPER_ENGINE": app.engine_var.get(),
                        "whisper_model": app.model_var.get(), "AUDIO_LANG": app.audio_var.get(),
                        "COLAB_WHISPER_URL": colab_url, "COLAB_WHISPER_TOKEN": colab_token,
                        "NINEROUTER_BASE_URL": setting("NINEROUTER_BASE_URL", NINEROUTER_URL),
                        "NINEROUTER_API_KEY": setting("NINEROUTER_API_KEY", ""), "NINEROUTER_MODEL": app.model}
        # kunci -> [(nilai, label tampilan)] untuk kolom pilihan
        self.choices = {"APP_LANG": [(x, x) for x in UI_LANGS],
                        "theme": [(x, app.tr("theme_" + x)) for x in theme.CHOICES],
                        "WHISPER_ENGINE": [(x, x) for x in ENGINES],
                        "whisper_model": [(x, x) for x in WHISPER_MODELS],
                        "AUDIO_LANG": [(x, x) for x in AUDIO_LANGS]}
        self.title(app.tr("set_title"))
        self.configure(bg=T.BG)
        self.transient(app)

        tabs = tk.Frame(self, bg=T.BG)
        tabs.pack(fill="x", padx=14, pady=(14, 0))
        self.tab_btns, self.frames, self.vars = {}, {}, {}
        for key, label_key in self.PAGES:
            btn = app.button(tabs, f"[ {app.tr(label_key)} ]", lambda k=key: self.show(k))
            btn.pack(side="left", padx=(0, 6))
            self.tab_btns[key] = btn
        holder = tk.Frame(self, bg=T.BG, highlightthickness=1, highlightbackground=T.FG)
        holder.pack(fill="both", expand=True, padx=14, pady=8)
        for key, _ in self.PAGES:
            self.frames[key] = tk.Frame(holder, bg=T.BG)
        for page_key, name, label_key, kind, store in self.FIELDS:
            self.build_row(self.frames[page_key], name, label_key, kind, store)
        self.build_trans_extras(self.frames["trans"])
        self.build_llm_extras(self.frames["llm"])
        tk.Label(self.frames["general"], text=app.tr("set_help"), font=("Consolas", 10), bg=T.BG, fg=T.DIM,
                 justify="left", anchor="w", wraplength=620).pack(fill="x", padx=12, pady=(12, 8))

        self.info = tk.Label(self, text=notice, font=FONT, bg=T.BG, fg=T.FG, justify="left", anchor="w", wraplength=640)
        self.info.pack(fill="x", padx=14)
        bottom = tk.Frame(self, bg=T.BG)
        bottom.pack(fill="x", padx=14, pady=12)
        app.button(bottom, app.tr("set_save"), self.save).pack(side="left")
        app.button(bottom, app.tr("close"), self.destroy).pack(side="right")

        # tinggi tetap = halaman tertinggi, supaya jendela tidak melompat saat pindah tab
        height = 0
        for frame in self.frames.values():
            frame.pack(fill="x")
            self.update_idletasks()
            height = max(height, frame.winfo_reqheight())
            frame.pack_forget()
        holder.config(height=height + 4)
        holder.pack_propagate(False)
        self.show(page)
        self.update_idletasks()
        self.geometry(f"700x{self.winfo_reqheight()}+{app.winfo_rootx() + 60}+{app.winfo_rooty() + 30}")
        self.poll()

    def build_row(self, parent, name, label_key, kind, store):
        app = self.app
        row = tk.Frame(parent, bg=T.BG)
        row.pack(fill="x", padx=12, pady=5)
        names = tk.Frame(row, bg=T.BG, width=200, height=40)
        names.pack(side="left", anchor="n")
        names.pack_propagate(False)
        tk.Label(names, text=app.tr(label_key), font=FONT, bg=T.BG, fg=T.FG, anchor="w").pack(fill="x")
        tk.Label(names, text=name if store == "env" else "settings.json", font=("Consolas", 9), bg=T.BG, fg=T.DIM,
                 anchor="w").pack(fill="x")
        if kind == "choice":
            labels = [label for _, label in self.choices[name]]
            current = next((label for value, label in self.choices[name] if value == self.initial[name]), labels[0])
            var = self.vars[name] = tk.StringVar(value=current)
            app.menu(row, var, labels).pack(side="left", anchor="n")
            return
        var = self.vars[name] = tk.StringVar(value=self.initial[name])
        entry = tk.Entry(row, textvariable=var, font=FONT, bg=T.BG, fg=T.FG, insertbackground=T.FG, relief="flat",
                         highlightthickness=1, highlightbackground=T.DIM, highlightcolor=T.FG,
                         show="*" if kind == "secret" else "")
        entry.pack(side="left", fill="x", expand=True, ipady=3, anchor="n")
        if kind == "secret":
            toggle = app.button(row, app.tr("set_show"), lambda e=entry: self.toggle(e))
            toggle.pack(side="left", padx=(6, 0), anchor="n")
            entry.toggle_btn = toggle

    def build_trans_extras(self, parent):
        tk.Label(parent, text=self.app.tr("colab_help"), font=("Consolas", 10), bg=T.BG, fg=T.DIM, justify="left",
                 anchor="w", wraplength=620).pack(fill="x", padx=12, pady=(4, 6))
        self.app.button(parent, self.app.tr("colab_test"), self.test).pack(anchor="w", padx=12, pady=(0, 8))

    def build_llm_extras(self, parent):
        self.app.button(parent, self.app.tr("set_pick"),
                        lambda: ModelPicker(self.app, done=self.model_picked)).pack(anchor="w", padx=12, pady=(4, 8))

    def model_picked(self, model):
        """ModelPicker sudah menerapkan model (settings.json); samakan kolom dan nilai awal agar tidak ditulis ulang."""
        self.vars["NINEROUTER_MODEL"].set(model)
        self.initial["NINEROUTER_MODEL"] = model

    def show(self, page):
        self.page = page
        for frame in self.frames.values():
            frame.pack_forget()
        self.frames[page].pack(fill="both", expand=True)
        self.app.mark_tabs(self.tab_btns, page)

    def toggle(self, entry):
        hidden = entry.cget("show") == "*"
        entry.config(show="" if hidden else "*")
        entry.toggle_btn.config(text=self.app.tr("set_hide" if hidden else "set_show"))

    def value(self, name):
        text = self.vars[name].get().strip()
        if name in self.choices:
            return next((value for value, label in self.choices[name] if label == text), text)
        return text

    def normalize_colab(self):
        """Terima satu baris "URL TOKEN" hasil notebook yang ditempel ke kolom URL."""
        url, token = self.vars["COLAB_WHISPER_URL"], self.vars["COLAB_WHISPER_TOKEN"]
        parts = url.get().split()
        if len(parts) == 2 and not token.get().strip():
            url.set(parts[0])
            token.set(parts[1])
        url.set(url.get().strip().rstrip("/"))

    def test(self):
        self.normalize_colab()
        url, token = self.value("COLAB_WHISPER_URL"), self.value("COLAB_WHISPER_TOKEN")
        if not url or not token:
            self.info.config(text=self.app.tr("colab_empty"), fg=T.RED)
            return
        self.info.config(text=self.app.tr("colab_testing"), fg=T.AMBER)
        self.result = None

        def work():
            try:
                self.result = ("ok", remote.health(url, token))
            except remote.RemoteError as e:
                self.result = ("err", str(e))

        threading.Thread(target=work, daemon=True).start()

    def poll(self):
        if self.result:
            kind, value = self.result
            self.result = None
            if kind == "ok":
                self.info.config(text=self.app.tr("colab_ok").format(**value), fg=T.FG)
            else:
                self.info.config(text=value, fg=T.RED)
        if self.winfo_exists():
            self.after(150, self.poll)

    def save(self):
        self.normalize_colab()
        values = {name: self.value(name) for name in self.vars}
        changes = {name: v for name, v in values.items() if v != self.initial[name]}
        if not changes:
            self.info.config(text=self.app.tr("set_nochange"), fg=T.DIM)
            return
        env = {name: v for name, v in changes.items() if name.isupper()}
        try:
            if env:
                write_env(env)
            self.apply(changes, values)
        except OSError as e:
            self.info.config(text=self.app.tr("set_err").format(e=e), fg=T.RED)
            return
        self.initial.update(values)
        notice = self.app.tr("set_saved").format(n=len(changes), path=ENV_FILE if env else SETTINGS_FILE)
        if "APP_LANG" in changes:  # bangun ulang dialog supaya semua teksnya berganti bahasa
            page = self.page
            self.destroy()
            self.app.open_settings(page=page, notice=notice)
        else:
            self.info.config(text=notice, fg=T.FG)

    def apply(self, changes, values):
        """Samakan state aplikasi yang sedang berjalan dengan nilai baru (settings.json menang atas .env)."""
        a = self.app
        if "NINEROUTER_MODEL" in changes:
            a.set_model(setting("NINEROUTER_MODEL", FALLBACK_MODEL))
        if "whisper_model" in changes:
            a.model_var.set(values["whisper_model"])
            save_settings(whisper_model=values["whisper_model"])
        if "AUDIO_LANG" in changes:
            a.audio_var.set(values["AUDIO_LANG"])
        if "WHISPER_ENGINE" in changes:
            a.engine_var.set(values["WHISPER_ENGINE"])
        if "COLAB_WHISPER_URL" in changes or "COLAB_WHISPER_TOKEN" in changes:
            save_settings(colab_url=values["COLAB_WHISPER_URL"], colab_token=values["COLAB_WHISPER_TOKEN"])
        if "theme" in changes:
            a.set_theme(values["theme"])
        if "APP_LANG" in changes:
            a.ui_var.set(values["APP_LANG"])
            a.apply_lang()


class ModelPicker(tk.Toplevel):
    """Dialog retro untuk memilih model dari 9router (atau mengetik nama model manual)."""

    def __init__(self, app, done=None):
        super().__init__(app)
        self.app, self.models, self.result, self.done = app, [], None, done
        self.title(app.tr("model_title"))
        self.configure(bg=T.BG)
        self.geometry("620x460")
        self.transient(app)
        top = tk.Frame(self, bg=T.BG)
        top.pack(fill="x", padx=12, pady=(12, 6))
        tk.Label(top, text=app.tr("filter"), font=FONT_B, bg=T.BG, fg=T.FG).pack(side="left")
        self.filter = tk.StringVar()
        self.filter.trace_add("write", lambda *_: self.refill())
        entry = tk.Entry(top, textvariable=self.filter, font=FONT, bg=T.BG, fg=T.FG, insertbackground=T.FG,
                         relief="flat", highlightthickness=1, highlightbackground=T.DIM, highlightcolor=T.FG)
        entry.pack(side="left", fill="x", expand=True, padx=8, ipady=3)
        entry.bind("<Return>", lambda e: self.choose())
        entry.focus_set()

        self.info = tk.Label(self, text="", font=FONT, bg=T.BG, fg=T.AMBER, anchor="w", justify="left", wraplength=590)
        self.info.pack(fill="x", padx=12)
        holder = tk.Frame(self, bg=T.BG, highlightthickness=1, highlightbackground=T.FG)
        holder.pack(fill="both", expand=True, padx=12, pady=8)
        sb = tk.Scrollbar(holder, troughcolor=T.BG, bg=T.DIM, relief="flat", bd=0, width=12)
        self.list = tk.Listbox(holder, font=FONT, bg=T.BG, fg=T.FG, selectbackground=T.FG, selectforeground=T.BG,
                               relief="flat", highlightthickness=0, activestyle="none", yscrollcommand=sb.set)
        sb.config(command=self.list.yview)
        sb.pack(side="right", fill="y")
        self.list.pack(side="left", fill="both", expand=True, padx=4, pady=4)
        self.list.bind("<Double-Button-1>", lambda e: self.choose())
        self.list.bind("<Return>", lambda e: self.choose())

        bottom = tk.Frame(self, bg=T.BG)
        bottom.pack(fill="x", padx=12, pady=(0, 12))
        app.button(bottom, app.tr("select"), self.choose).pack(side="left")
        app.button(bottom, app.tr("reload"), self.load).pack(side="left", padx=6)
        app.button(bottom, app.tr("close"), self.destroy).pack(side="right")
        self.load()
        self.poll()

    def load(self):
        import threading

        self.info.config(text=self.app.tr("loading"), fg=T.AMBER)
        self.result = None

        def work():
            try:
                self.result = ("ok", fetch_models())
            except Exception as e:
                self.result = ("err", f"{type(e).__name__}: {e}")

        threading.Thread(target=work, daemon=True).start()

    def poll(self):
        if self.result:
            kind, value = self.result
            self.result = None
            if kind == "ok":
                self.models = value
                self.info.config(text=self.app.tr("count").format(n=len(value)), fg=T.DIM)
            else:
                self.info.config(text=self.app.tr("fetch_err").format(e=value), fg=T.RED)
            self.refill()
        if self.winfo_exists():
            self.after(100, self.poll)

    def refill(self):
        needle = self.filter.get().strip().lower()
        self.list.delete(0, "end")
        for m in self.models:
            if needle in m.lower():
                self.list.insert("end", m)
                if m == self.app.model:
                    self.list.selection_set("end")
                    self.list.see("end")

    def choose(self):
        sel = self.list.curselection()
        model = self.list.get(sel[0]) if sel else self.filter.get().strip()
        if model:
            self.app.set_model(model)
            if self.done:
                self.done(model)
            self.destroy()


if __name__ == "__main__":
    App().mainloop()
