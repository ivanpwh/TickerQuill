# Source link and clearer labels: design

Date: 2026-10-23 · Status: approved in brainstorming, awaiting spec review · Sub-project A of the 1.2.0 plan

The 1.2.0 plan has three sub-projects, built in order: **A. Source link and labels** (this spec), **B. Analysis archive and COLLECTION dashboard**, **C. Stock price view**. B and C get their own specs.

## Problems

1. **The video link is not visible.** When a finished analysis is opened from History, the dashboard, the report and the History dialog do not show which video it came from. The URL is stored in the cache entry (`url`) and History already puts it back in the URL box, but nowhere is it shown or clickable.
2. **The start button and the report tab have the same label.** In Indonesian both read `[ ANALISIS ]` (English: `[ ANALYZE ]` / `ANALYSIS`), so it is unclear which one runs the job and which one shows the result.
3. **COPY/SAVE don't say what they act on.** `[ SALIN ]` / `[ SIMPAN ]` look the same on every tab.

Out of scope: storing the exact URL variant the user typed (for example `youtu.be/…` vs `watch?v=…`), moving progress messages out of the report tab, and refreshing screenshots.

## 1. Data flow for the source

1. `Pipeline` sends the source with the `transcript` event. The payload changes from `(title, text)` to `(title, text, source)`:
   - YouTube: `{"url": self.url}`. This is the URL box content; when opening from History it already holds the stored URL.
   - Transcript file (OPEN FILE, or a file entry opened from History): `{"file": <file name>}`. The name is the `source` path's file name from the cache entry, falling back to the title when `source` is missing.
2. `App` keeps it as `self.source` (reset in `start()`). In `process_report`, after `report.compute()`, it sets `self.data["source"] = {"title": <title>, **self.source}`.
3. `report.blocks(d, ui)` puts `("source", {"title", "url" | "file", "label"})` first, above the truncation warning. `label` is the localised `Source` / `File` word.
4. `report.report_markdown(d, ui)` starts with:
   ```
   # <video title>
   Sumber: https://youtu.be/...        (or "Berkas: notes.txt")
   ```
5. `report.blocks_to_text()` writes the `source` block in the same two-line form, so COPY/SAVE DASHBOARD carries the link.
6. If `d` has no `source` (parse failure, tests, older callers), no header is added.

`report.compute()` is unchanged and stays pure.

## 2. Display

### Dashboard: `DashboardView.b_source`
```
<VIDEO TITLE>                         T.AMBER, bold
https://youtu.be/abc123xyz            T.CYAN, underlined, hand cursor
```
- Clicking the link calls `webbrowser.open(url)`, only for `http://` or `https://` URLs.
- For a file source the second line reads `Berkas: notes.txt` in `T.DIM` and is not clickable.
- Colours are read from `T` at render time; theme switches already redraw the dashboard.

### Report tab
- `render_markdown` shows the title as `h1` and the `Sumber:` line below it.
- `http(s)://` URLs in the rendered text get a `link` tag (`T.CYAN`, underline, hand cursor) bound to `webbrowser.open`.

### History dialog: detail line
```
┌ history list ──────────────────────────────────────────────┐
│  SELESAI  Video title …   Indonesia large-v3 2026-10-21    │ ← selected
└────────────────────────────────────────────────────────────┘
Full video title, wrapped instead of cut
https://www.youtube.com/watch?v=abc123xyz   [ BUKA LINK ] [ SALIN LINK ]
[ PAKAI / LANJUTKAN ] [ ANALISIS ULANG ] [ ULANG DARI AWAL ] [ HAPUS ]     [ TUTUP ]
```
- Updated on `<<ListboxSelect>>` and after `reload()`.
- No selection: empty detail line, both buttons disabled.
- YouTube entry: shows `it["url"]`. OPEN LINK opens it, COPY LINK copies it.
- File entry: shows `Berkas: <source path>`. OPEN LINK is disabled, COPY LINK copies the path.

### New strings (ID / EN)

| Key | ID | EN |
|---|---|---|
| `hist_open_link` | `[ BUKA LINK ]` | `[ OPEN LINK ]` |
| `hist_copy_link` | `[ SALIN LINK ]` | `[ COPY LINK ]` |
| `src_label` | `Sumber` | `Source` |
| `src_file` | `Berkas` | `File` |

`src_label` and `src_file` live in `report._T` (they are used by `report.py`). The History keys live in `STR`.

## 3. Labels

| `STR` key | ID old → new | EN old → new |
|---|---|---|
| `analyze` (start button) | `[ ANALISIS ]` → `[ PROSES ]` | `[ ANALYZE ]` → `[ RUN ]` |
| `analysis_tab` | `ANALISIS` → `HASIL ANALISIS` | `ANALYSIS` → `REPORT` |
| `copy` / `save` | removed, replaced by `copy_fmt` / `save_fmt` | removed, replaced by `copy_fmt` / `save_fmt` |
| `analysis_for` | removed (unused) | removed (unused) |

`copy_fmt` = `[ SALIN {x} ]` / `[ COPY {x} ]` and `save_fmt` = `[ SIMPAN {x} ]` / `[ SAVE {x} ]`. `{x}` comes from new keys per tab:

| Active tab | Key | ID | EN |
|---|---|---|---|
| DASHBOARD | `x_dash` | DASHBOARD | DASHBOARD |
| report | `x_report` | HASIL | REPORT |
| transcript | `x_transcript` | TRANSKRIP | TRANSCRIPT |

`App.update_export_labels()` sets both buttons. It is called from `show()` and `apply_lang()`.

Texts that refer to the start button switch to `[ PROSES ]` / `[ RUN ]`: `hint`, `hint_tr_part`, `hint_tr_none`, `hint_an`, `llm_open` in `STR`, and `trunc_warn` in `report._T`. `parse_fail` now says "tab HASIL ANALISIS" / "REPORT tab".

Unchanged on purpose: the settings tab `ANALISIS (LLM)` / `ANALYSIS (LLM)`, the History button `[ ANALISIS ULANG ]` / `[ REANALYZE ]`, the internal pane name `"ANALISIS"`, and the save file name `tickerquill-analysis.md`.

## 4. Error handling

| Case | Behaviour |
|---|---|
| No `source` in data | No header block; nothing else changes |
| Empty URL or not `http(s)` | Text shown, not clickable, `webbrowser.open` never called |
| `webbrowser.open` fails | Ignored; COPY LINK still works |
| Nothing selected in History | Empty detail line, link buttons disabled |
| Very long title | Wrapped (`wraplength`), not cut |

## 5. Tests (pytest, no network)

- `tests/test_report.py`
  - `blocks()` puts `source` first when present and omits it when absent.
  - `report_markdown()` starts with the title and a `Sumber:` / `Source:` line.
  - `blocks_to_text()` contains the URL.
  - A file source renders `Berkas:` / `File:` without a URL.
- `tests/test_gui.py`
  - Start button reads `[ PROSES ]` / `[ RUN ]`.
  - COPY/SAVE labels follow the active tab and the UI language.
  - History detail line shows the URL for a YouTube entry (both link buttons enabled) and the path for a file entry (OPEN LINK disabled).
- `tests/test_pipeline_errors.py`
  - `"[ ANALYZE ]"` assertions become `"[ RUN ]"`.
  - The `transcript` event carries `source`.

## 6. Documentation

- `README.md`, `docs/user-guide.md`, `docs/troubleshooting.md`: `[ ANALYZE ]` becomes `[ RUN ]` and the ANALYSIS tab becomes REPORT. Describe the per-tab COPY/SAVE labels and the History link line.
- `docs/methodology.md`: "ANALYSIS tab" becomes "REPORT tab".
- `docs/architecture.md`: the `transcript` event payload, the `source` block and `data["source"]`.
- `CHANGELOG.md`: an "Unreleased" entry.
- Screenshots in `docs/images/` are left for a separate PR.
