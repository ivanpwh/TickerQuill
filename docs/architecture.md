# Architecture

A map of the code for contributors. The app is the `tickerquill` package (`python -m tickerquill`); paths below are relative to the repository. User-facing behaviour is in the [user guide](user-guide.md); formulas are in the [methodology](methodology.md).

## Modules

| File | Responsibility |
|---|---|
| `tickerquill/__main__.py` | Command line (`tickerquill`, `tickerquill-gui`, `python -m tickerquill`): `--version`, `--where`, `--data`, `--migrate`, `--shortcut`, `--remove-shortcut`; imports the app only to start it, after `--data` is applied |
| `tickerquill/paths.py` | `PACKAGE`, `ASSETS`, `ICONS`, `SOURCE` (repository when running from a checkout) and `data_dir()`; `migrate()` copies data from an older folder |
| `tickerquill/system.py` | OS integration: `open_url`, `open_path` (startfile / open / xdg-open), `MOD`/`MOD_LABEL` (Control/Ctrl or Command/Cmd), `gui_python()` (pythonw on Windows), `no_console_flags()`, `set_app_id()` (Windows taskbar identity) |
| `tickerquill/shortcuts.py` | App shortcuts: `.lnk` in Start Menu and Desktop through PowerShell (Windows), `~/Applications/TickerQuill.app` (macOS), `tickerquill.desktop` + icon (Linux); all run `python -m tickerquill` |
| `tickerquill/widgets.py` | `RetroButton`, a Label-based button with the `tk.Button` API (`invoke`, `state`), because `tk.Button` ignores colours on macOS |
| `tickerquill/app.py` | Tk application (`App`) and its pages (the Analysis frame, `HistoryPage`), dialogs (`SettingsDialog`, `ChoiceDialog`, `ModelPicker`), settings helpers, UI strings (`STR`), the LLM system prompt, cache/history helpers and the `Pipeline` |
| `tickerquill/report.py` | Parsing and repairing the LLM reply, all calculations (`compute`), tips (`advice`), UI-neutral dashboard blocks (`blocks`), plain-text/Markdown export |
| `tickerquill/archive.py` | Analysis archive (`analyses/`): build/save/load records, latest per video, one-time import from the cache, video-date fill-in, AI cache paths, and every cross-video calculation (consensus, conflict, price zone, changes, reliability, trending, tone per date). No Tk |
| `tickerquill/collection.py` | `CollectionPage` and `CollectionView` (a `DashboardView` with table, bars, actions and link blocks); its own `(ID, EN)` strings. Talks to the app only through `App` methods |
| `tickerquill/market.py` | Yahoo Finance chart endpoint through `urllib`: `fetch_chart` (errors mapped to `MarketError` kinds `not_found`, `network`, `bad_data`), `parse_chart`, `market_open` (IDX session), `tradingview_url` (`IDX:<TICKER>` chart link), `since` (move and target/stop hits since a video date). No Tk |
| `tickerquill/chartview.py` | Candle chart process: `pywebview` window (Edge WebView2) showing `assets/chart.html` with the bundled Lightweight Charts; `Api.init`/`Api.bars` are called from JavaScript; `video_markers` places stance markers. Importable without pywebview |
| `tickerquill/stockview.py` | `StockWindow`: price header, canvas chart with level lines, since-video table; fetches in a worker thread, refreshes every 60 s while the IDX is open |
| `tickerquill/menus.py` | `MenuBar`: the native menu bar built from one table (label, command, accelerator, key bindings, enabled condition) |
| `tickerquill/dashboard.py` | `DashboardView`: scrollable canvas that renders the blocks (cards, gauge, bars) |
| `tickerquill/theme.py` | Palettes, the live palette object `T`, `apply()` and `recolor()` |
| `tickerquill/textclean.py` | Removes runs of repeated words/lines that Whisper hallucinates |
| `tickerquill/remote.py` | Client for the Colab Whisper server: audio compression, health check, streaming upload and results |
| `colab/whisper_server.py` | FastAPI server run inside Colab; `Whisper_Server.ipynb` is generated from it by `build_notebook.py` |

## Pipeline

`Pipeline` (in `app.py`) runs on a worker thread and talks to the UI only through a `queue.Queue` of `(kind, payload)` events. The UI drains the queue every 100 ms in `App.poll()`.

| Event | Payload | Handled by |
|---|---|---|
| `status` | `(key, percent, extra)` | status line, progress bar, pause button state |
| `transcript` | `(title, text, source)` | writes the TRANSCRIPT tab; `source` is `{"url": …}` or `{"file": <file name>}` and becomes `data["source"]` |
| `report_raw` | `(raw LLM text, finish reason)` | `process_report` → `report.parse_report` → `report.compute` → dashboard |
| `error` | message | status line, REPORT tab, dashboard message |
| `done` | none | re-enables buttons, reloads History, updates the menu and the job indicator |

```
Pipeline.run
 ├─ read_transcript_file()            when a file was opened
 └─ get_transcript()
     ├─ reuse() from cache            finished transcript, no network
     ├─ yt-dlp extract_info           id and title
     ├─ download_audio()              work/<id>.<ext>, resumable (.part)
     ├─ resume point from cache/*.partial.json
     ├─ local_segments()  or  colab_segments()     → iterator of segments
     └─ collect()                     consume segments, checkpoint, write cache + transcripts/
 └─ analyze()                         streaming chat completion → "report_raw"
```

Cancellation uses an `Event` checked between segments, download chunks and stream chunks (`Cancelled` exception). Pause uses a second `Event`; `wait_if_paused` blocks the worker. A paused download aborts and restarts from the partial file.

### Segments from either engine

`local_segments()` returns faster-whisper's generator plus duration and device. `colab_segments()` compresses the audio, uploads it and returns a generator with the same shape (`.start`, `.end`, `.text`), so `collect()` does not care where the text came from. Device is CUDA when `ctranslate2` sees a GPU, otherwise CPU with int8.

### LLM call

An OpenAI-compatible streaming chat completion: system prompt (extraction rules and schema, plus a one-line language rule) and a user message with the video title and transcript. `max_tokens` is 16000, falling back to 8000 if the endpoint rejects it. The stream is accumulated; if the connection drops mid-reply the partial text is still processed. `finish` is passed along but truncation is detected by JSON repair (`parse_report`).

## Data on disk

All paths are inside the data folder (`paths.data_dir()`, see [configuration](configuration.md#data-folder)): `TICKERQUILL_HOME`, else the repository when it already holds data, else the OS user data folder. `app.py` reads it once at import time, which is why `__main__` applies `--data` before importing the app.

```
cache/<video id>.<lang>.json            finished transcript
cache/<video id>.<lang>.partial.json    checkpoint
transcripts/<title>-<video id>.txt      plain text copy
work/<video id>.<ext>                   downloaded audio
work/upload/<video id>.ogg              compressed audio for Colab (deleted on success)
analyses/<YYYYMMDD-HHMMSS>-<vid>.json   one archived analysis (Market Overview)
analyses/.imported                      marker: old cache analyses were imported once
analyses/ai/<kind>-<key>-<hash>.json    saved AI summary (kind = ticker or date)
```

`<lang>` is the Whisper language code (`id`, `en`, …) or `auto`. Files are written atomically (temp file then rename).

Transcripts opened with OPEN FILE are registered as `cache/file-<sha1 of the cleaned text, 10 hex>.file.json` (`lang` is the literal `file`, `url` is empty, `whisper_model` is `-`, plus a `source` path and the full `transcript`) so History can list them. Identical content maps to the same entry. Choosing one in History starts `Pipeline(preloaded=(title, transcript))`, which skips download and Whisper and goes straight to the analysis.

Finished cache JSON: `title, url, vid, lang, whisper_model, duration, created, transcript`, plus `video_date` and `channel` when yt-dlp provided them, and `analysis` / `analysis_model` once analysed.
Checkpoint JSON: the same without `transcript`, plus `lines` (timestamped lines so far) and `done_until` (seconds). A checkpoint is written every 10 segments and whenever a job is cancelled or fails with some text. `list_history()` reads this folder; there is no separate database.

## Market Overview (code name: collection)

`Pipeline.save_analysis` writes the analysis into the cache entry and, through `archive.build_record`, an archive record with the video metadata, the raw reply and a compact per-stock summary (stance, share, level texts, parsed prices, reason, confidence, doubtful). The Market Overview page (`CollectionPage`, page key `collection`) loads records through `App.collection_records()`, which imports cache analyses once (marker file) so deleting a video from Market Overview is permanent. Records are reduced to the latest per video before any calculation. The effective date is `video_date`, else the analysis date (marked). `App.fill_video_dates` runs yt-dlp metadata calls in a worker thread and updates both the archive and the cache.

AI summaries call `App.llm_complete(system, user)` in a worker thread with only the extracted data as input. The cache key hashes the ids of the records used plus the UI language, so a new analysis makes the stored summary stale (still shown, with an update button) instead of silently reusing it.

## Stock price window

`App.open_stock(ticker, context)` keeps one `StockWindow` per symbol (`market.symbol_for`, IDX `.JK`). `context` = `{"levels": {entry, target, stop_loss}, "videos": [{date, title, stance, prices, fallback}]}`: the Dashboard passes the clicked card's levels and the current video (its `video_date` comes from the `transcript` event's source), Market Overview passes the median levels and every video. A load fetches the 1-day quote, the selected range when it is not 1D, and (once, or on RELOAD) one year of daily bars for "since the video". Results come back through `self.result` and `poll()`; a failed refresh keeps the last good data and shows the error. Theme and language changes re-render open windows.

### Candle chart (separate process)

`App.open_chart(ticker, context)` writes the context (symbol, UI language, theme palette, stance colours and labels, levels, videos) to `%TEMP%/tickerquill-chart-<symbol>.json` and starts `pythonw chartview.py <file>`. A separate process is needed because Tk and pywebview each run their own GUI loop on the main thread. One process per symbol: opening it again terminates the old one; `App.destroy` terminates all of them. In the chart page, JavaScript calls `pywebview.api.bars(range)`; Python fetches through `market.py` and returns `ohlc_bars` (daily bars as `YYYY-MM-DD`, intraday as epoch seconds shifted to WIB because Lightweight Charts shows UTC), markers, a header and whether the IDX is open (the page then reloads after 60 s). Lightweight Charts v5.2.1 is inlined into the page from `assets/lightweight-charts/` (Apache 2.0; LICENSE and NOTICE kept there, attribution logo left on). If `pywebview` is not installed, `open_chart` shows how to install it; WebView2 failures are shown by the chart process in a Windows message box.

## Platforms, launch and icon

Platform differences are kept in `system.py`, `theme.font()` (Consolas / Menlo / fontconfig `monospace`, two points larger on macOS where Tk renders at 72 dpi), `dashboard.wheel_steps()` (Windows deltas of 120, small macOS deltas, X11 buttons 4/5), `menus.py` (Ctrl or Cmd, and the macOS app menu's Preferences/Quit through `tk::mac::ShowPreferences` / `tk::mac::Quit`) and `chartview.py` (Edge WebView2 on Windows, the default web view elsewhere). `App` is created with `className="TickerQuill"`, which Tk turns into the window class `Tickerquill`; the Linux `.desktop` entry uses it as `StartupWMClass`.

The icon is drawn by `tools/make_icon.py` into `tickerquill/assets/icon/` (PNG 16–1024, `.ico`, `.icns`). `App.set_icon()` passes six PNG sizes to `wm iconphoto -default`, so dialogs and price windows inherit it; on Windows `set_app_id()` runs before the first window so the taskbar shows it instead of Python's. Shortcuts use the `.ico` (Windows), `.icns` (macOS) or the 256 px PNG (Linux). pywebview can only set its window icon on GTK/Qt, so the candle chart window shows the interpreter's icon on Windows and macOS.

## Pages and menu

`App.pages` holds the page frames (`analysis`, `history`, `collection`). `show_page(name)` packs one and hides the others, so each keeps its widgets and state; it also sets the page name in the title row, reloads History, and updates the job indicator. `busy()` (the RUN button is disabled) is the single "a job is running" flag.

`menus.MenuBar` only calls methods on the `App` instance, so it does not import `app.py`. Each item is a row in one table: a label function, a command, the accelerator text, the key sequences bound on the main window, and an optional enabled condition. `refresh_labels()` runs on language changes; `refresh_state()` re-evaluates labels and enabled conditions after `start`, `finish`, tab/page switches and queue events. Copy/Save and Pause/Resume reuse the labels of their buttons. Key sequences that a Tk widget class already uses to edit text (`Ctrl+O` in `Text` inserts a line) are rebound on that class with the menu action and `"break"`.

The job indicator (`update_indicator`) is empty on the Analysis page. Elsewhere it shows `● <status> <pct>%` while `busy()`, then `job_mark` (`✓`, `■` or `!`) set by `finish()` until the Analysis page is shown.

## Settings

`setting(name, default)` reads `.env`, then the OS environment, then the default, on every call (so edits apply without restart). `load_settings()` / `save_settings(**changes)` read and merge-write `settings.json`. `write_env()` edits `.env` in place, keeping comments and unknown lines. `SettingsDialog.FIELDS` declares each field, its tab, widget type and storage (`env` or `json`); `SettingsDialog.apply()` pushes saved values into the running app. Precedence rules: [configuration](configuration.md#precedence).

## Themes

`theme.THEMES` maps a theme name to seven colour roles: `BG`, `FG`, `DIM`, `AMBER`, `RED`, `CYAN`, `GOOD`. Code reads colours as `T.BG`, `T.FG`, … when it creates a widget. Switching themes:

1. `theme.apply(name)` updates `T` and returns the old palette.
2. `theme.recolor(root, old, new)` walks every widget (including open dialogs, but not `tk.Menu`, which keeps the system colours) and replaces any colour option equal to an old role colour with the new role colour; text tags are included.
3. `App.set_theme` then redraws the dashboard, because its canvas items are not widgets.

Rules for contributors: never hard-code a hex colour in UI code (derive with `theme.mix`); give each role in a theme a distinct hex (`GOOD` may equal `FG`); read `T.X` at call time, not in default arguments or module-level constants. `system` resolves to dark/light from the OS when the app starts.

## Dashboard data flow

`report.compute(raw, transcript, model)` returns a dict (`report`, `stocks`, `tone`, `reliability`, …). `App.process_report` adds `data["source"]` (`{"title", "url"}` or `{"title", "file"}`) from the `transcript` event. `report.blocks(data, ui)` turns it into a flat list of `(kind, value)` blocks (`source`, `title`, `para`, `gauge`, `stock`, `bullets`, …) with all text already localised; `source` comes first when present and `report_markdown` starts with the same title and link. `DashboardView.render` draws them; `report.blocks_to_text` turns the same blocks into the text used for COPY/SAVE. Changing language re-runs `blocks` on the stored data; nothing is re-computed by the LLM.

## Colab Whisper server

`remote.py` ↔ `colab/whisper_server.py` over HTTP(S), tunnelled by Cloudflare. Every request carries `Authorization: Bearer <token>`.

| Endpoint | Purpose |
|---|---|
| `GET /health` | `{status: ok|busy, device, models}`; used by TEST CONNECTION |
| `POST /transcribe` | multipart `file`, `model`, `language` (empty = auto), `start` (seconds, for resume). Response: newline-delimited JSON |

Response lines: `{"type":"loading"}` (model being loaded), `{"type":"info","duration":…,"device":…}`, `{"type":"seg","start":…,"end":…,"text":…}`, `{"type":"ping"}` every 3 s, then `{"type":"done"}` or `{"type":"error","message":…}`.

Design notes: audio is compressed client-side to Opus mono 16 kHz (about 14 MB per hour) using PyAV, which also keeps uploads under the tunnel's 100 MB request limit; one job at a time, and a new request stops a stale one (the old client may be dead); closing the connection stops the server-side transcription; the compressed file is kept until the transcription finishes so a resume does not recompress.

## Extension points

- **New UI language:** needs more than data. `STR` in `app.py` holds one dict per language, but `report._T` stores `(Indonesian, English)` pairs and `report.t()` picks by `ui == "EN"`, so a third language means changing that convention first, then adding the code to `UI_LANGS`.
- **New theme:** add an entry to `theme.THEMES` and a `theme_<name>` string in both `STR` languages.
- **New setting:** add a row to `SettingsDialog.FIELDS` (and its label strings), then handle it in `apply()` if it needs to act on the running app.
- **Different LLM provider:** the call in `Pipeline.analyze` uses the `openai` client with a configurable `base_url`; anything speaking that protocol works.

## Known gaps

Automated tests cover the pure logic (`report.py`, `archive.py`, `textclean.py`, settings/history helpers, themes) and the main GUI flows; the download, Whisper, LLM and Colab steps are verified manually. Single-job pipeline; macOS and Linux are covered by CI (including the GUI tests) but have had less hands-on use than Windows; one monospace font per platform in every theme; the Windows `.exe` launchers and shortcuts need the virtual environment they were made with.
