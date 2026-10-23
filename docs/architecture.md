# Architecture

A map of the code for contributors. User-facing behaviour is in the [user guide](user-guide.md); formulas are in the [methodology](methodology.md).

## Modules

| File | Responsibility |
|---|---|
| `app.py` | Tk application (`App`), dialogs (`SettingsDialog`, `HistoryDialog`, `ChoiceDialog`, `ModelPicker`), settings helpers, UI strings (`STR`), the LLM system prompt, cache/history helpers and the `Pipeline` |
| `report.py` | Parsing and repairing the LLM reply, all calculations (`compute`), tips (`advice`), UI-neutral dashboard blocks (`blocks`), plain-text/Markdown export |
| `dashboard.py` | `DashboardView`: scrollable canvas that renders the blocks (cards, gauge, bars) |
| `theme.py` | Palettes, the live palette object `T`, `apply()` and `recolor()` |
| `textclean.py` | Removes runs of repeated words/lines that Whisper hallucinates |
| `remote.py` | Client for the Colab Whisper server: audio compression, health check, streaming upload and results |
| `colab/whisper_server.py` | FastAPI server run inside Colab; `Whisper_Server.ipynb` is generated from it by `build_notebook.py` |

## Pipeline

`Pipeline` (in `app.py`) runs on a worker thread and talks to the UI only through a `queue.Queue` of `(kind, payload)` events. The UI drains the queue every 100 ms in `App.poll()`.

| Event | Payload | Handled by |
|---|---|---|
| `status` | `(key, percent, extra)` | status line, progress bar, pause button state |
| `transcript` | `(title, text, source)` | writes the TRANSCRIPT tab; `source` is `{"url": …}` or `{"file": <file name>}` and becomes `data["source"]` |
| `report_raw` | `(raw LLM text, finish reason)` | `process_report` → `report.parse_report` → `report.compute` → dashboard |
| `error` | message | status line, REPORT tab, dashboard message |
| `done` | none | re-enables buttons |

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

```
cache/<video id>.<lang>.json            finished transcript
cache/<video id>.<lang>.partial.json    checkpoint
transcripts/<title>-<video id>.txt      plain text copy
work/<video id>.<ext>                   downloaded audio
work/upload/<video id>.ogg              compressed audio for Colab (deleted on success)
```

`<lang>` is the Whisper language code (`id`, `en`, …) or `auto`. Files are written atomically (temp file then rename).

Transcripts opened with OPEN FILE are registered as `cache/file-<sha1 of the cleaned text, 10 hex>.file.json` (`lang` is the literal `file`, `url` is empty, `whisper_model` is `-`, plus a `source` path and the full `transcript`) so History can list them. Identical content maps to the same entry. Choosing one in History starts `Pipeline(preloaded=(title, transcript))`, which skips download and Whisper and goes straight to the analysis.

Finished cache JSON: `title, url, vid, lang, whisper_model, duration, created, transcript`.
Checkpoint JSON: the same without `transcript`, plus `lines` (timestamped lines so far) and `done_until` (seconds). A checkpoint is written every 10 segments and whenever a job is cancelled or fails with some text. `list_history()` reads this folder; there is no separate database.

## Settings

`setting(name, default)` reads `.env`, then the OS environment, then the default, on every call (so edits apply without restart). `load_settings()` / `save_settings(**changes)` read and merge-write `settings.json`. `write_env()` edits `.env` in place, keeping comments and unknown lines. `SettingsDialog.FIELDS` declares each field, its tab, widget type and storage (`env` or `json`); `SettingsDialog.apply()` pushes saved values into the running app. Precedence rules: [configuration](configuration.md#precedence).

## Themes

`theme.THEMES` maps a theme name to seven colour roles: `BG`, `FG`, `DIM`, `AMBER`, `RED`, `CYAN`, `GOOD`. Code reads colours as `T.BG`, `T.FG`, … when it creates a widget. Switching themes:

1. `theme.apply(name)` updates `T` and returns the old palette.
2. `theme.recolor(root, old, new)` walks every widget (including open dialogs) and replaces any colour option equal to an old role colour with the new role colour; text tags are included.
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

Automated tests cover only the pure logic (`report.py`, `textclean.py`, settings/history helpers, themes); the download, Whisper, LLM and Colab steps are verified manually. Analysis results are not persisted (History keeps transcripts only); single-job pipeline; Windows-only launcher and untested on macOS/Linux; fonts are fixed to a monospace family in every theme.
