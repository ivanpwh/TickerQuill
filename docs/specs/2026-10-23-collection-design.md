# COLLECTION page (combined dashboard): design

Date: 2026-10-23 · Status: approved and implemented (section 1 reviewed; sections 2–5 decided during implementation at the user's request) · Sub-project B of the 1.2.0 plan

## Goal

One page that gathers every analysis ever made, grouped by video date, and compares what different videos said about the same stock. Example from real data: TLKM was discussed in 5 videos between 21/10 and 23/10 (WATCH ×4, BUY ×1, with entry, target and resistance levels that moved over time).

## Decisions

| Question | Decision |
|---|---|
| Approach | **Hybrid**: every number is computed locally; an AI narrative is created only when the user presses a button, then cached |
| Date | **Video upload date** (`yt-dlp upload_date`); transcript files and entries without it use the analysis date, marked as such |
| Re-analysis | The dashboard uses the **latest analysis per video**; older versions stay in the archive |
| Place | A third page, **View › Collection** (`Ctrl+3`) |
| v1 content | Consensus, timeline, disagreement flag, price zone, view changes, most-discussed stocks + market tone per date, combined reliability |
| Storage | `analyses/` folder, one JSON file per analysis |

## 1. Data and storage

**Video metadata.** `get_transcript` already calls `yt-dlp extract_info`. It now also keeps `upload_date` (as `YYYY-MM-DD`) and `channel` (falling back to `uploader`). Both are written to the cache entry as `video_date` and `channel`.

**Archive record.** Every analysis that `save_analysis` stores (not cut off by an error, JSON parsed) is also written to `analyses/<YYYYMMDD-HHMMSS>-<vid>.json`:

```json
{ "id": "20261023-100112-jO7jPNzp9Hs", "vid": "jO7jPNzp9Hs", "entry": "jO7jPNzp9Hs.id.json",
  "source": "youtube", "title": "…", "url": "…", "channel": "…", "video_date": "2026-10-21",
  "analyzed_at": "2026-10-23 10:01", "llm_model": "…", "raw": "<LLM reply>",
  "tone": 0.69, "sentiment": "MIXED", "summary": "…", "outlook": "…", "risks": ["…"],
  "stocks": [{ "ticker": "TLKM", "name": "…", "stance": "WATCH", "share": 4.1,
               "levels": {"entry": "2100", "resistance": "2110", …},
               "prices": {"entry": 2100.0, "target": null, …},
               "reason": "…", "expectation": "…", "confidence": "MEDIUM", "doubtful": false }] }
```

- `entry` is the cache file name, used to open the video again from the Analysis page.
- File transcripts: `source` is `file`, `video_date` is empty and `channel` is empty.
- `prices` uses `report.parse_price` (first number of the spoken text); the text in `levels` is what is shown.

**One-time import.** The first time the Collection page loads and `analyses/.imported` does not exist, every finished cache entry with a saved `analysis` is imported (analysis time = the cache file's modification time), then the marker file is written. Deleting a video from the Collection afterwards does not bring it back.

**Fill in video dates.** A **[ LENGKAPI TANGGAL VIDEO ]** / **[ FILL IN VIDEO DATES ]** button (shown while some YouTube records have no `video_date`) calls `yt-dlp extract_info` (metadata only, no download) for each such video in a worker thread. It updates every archive record of that video and its cache entries. A failure for one video is counted and reported, not fatal.

**Latest per video.** Records are grouped by `vid`; the one with the largest `analyzed_at` is used.

**Delete.** Deleting in the Collection removes every archive record of that video. Transcripts in History are untouched, and deleting a History entry leaves the archive alone.

**AI cache.** `analyses/ai/<kind>-<key>-<hash>.json` where kind is `ticker` or `date`, key is the ticker or date, and hash is the first 10 hex characters of the SHA-1 of the sorted record ids used plus the UI language. A new video for that ticker or date changes the hash, so the cached text is shown as outdated with an **update** button.

## 2. Calculations (`archive.py`, no Tk)

The effective date of a record is `video_date`, or the first 10 characters of `analyzed_at` (flagged as a fallback).

For one ticker, a **view** is one video's opinion: date, title, channel, stance, level texts, prices, share, confidence, doubtful, reason, expectation. Views are sorted by date, then analysis time.

| Function | Result |
|---|---|
| `consensus(views)` | Count per stance (BUY, WATCH, HOLD, SELL, AVOID), `top` = every stance with the most votes (more than one = a tie, shown as such), agreement = 100 × top count / number of views |
| `conflict(views)` | True when at least one BUY and at least one SELL or AVOID |
| `price_zone(views)` | For entry, target, stop loss: min, max, median and number of videos that stated it. **Repeated levels**: numbers (any level kind) stated in at least 2 videos. **Combined reward:risk** from the medians, only when stop < entry < target |
| `changes(views)` | Between consecutive views: stance changes, and target or stop-loss changes when both views state one |
| `reliability(views)` | Number of views marked doubtful; average confidence (HIGH 3, MEDIUM 2, LOW 1, rounded to the nearest label) over views that state one |
| `trending(records)` | Per ticker: number of videos, average mention share, dominant stance, conflict flag; sorted by videos then share |
| `tone_by_date(records)` | Average tone and video count per date |

## 3. The page

```
 7 video · 40 emiten · 16 dibahas >1 video      [ LENGKAPI TANGGAL VIDEO ] [ MUAT ULANG ]
┌ TANGGAL ─────────────┐┌──────────────────────────────────────────────────────────────┐
│ SEMUA TANGGAL        ││ (content, scrollable)                                        │
│ 2026-10-23  (2)      ││                                                              │
│ 2026-10-22  (3)      ││                                                              │
│ 2026-10-21  (2)      ││                                                              │
├ EMITEN ──────────────┤│                                                              │
│ CARI> ____           ││                                                              │
│ TLKM   5  !          ││                                                              │
│ BUMI   5             ││                                                              │
└──────────────────────┘└──────────────────────────────────────────────────────────────┘
```

- **Left**: the date list (all dates, then newest first, with video counts) and the stock list for the selected date (videos count, `!` for disagreement), filtered by the search box.
- **Content** depends on the selection:
  - **All dates, no stock**: most-discussed stocks (table: ticker, videos, consensus, agreement %, `!`), market tone per date (small bars), and the list of all videos.
  - **One date, no stock**: that day's videos (date, channel, title, tone; title opens it on the Analysis page; DELETE removes it from the Collection), the comparison table for stocks discussed in more than one video that day (one stance badge per video, consensus, target range), the other stocks as one line, and the daily AI summary.
  - **A stock** (always across all dates): header with video count and date range, consensus and agreement, disagreement warning, timeline (date, channel/title, stance badge, levels, confidence, doubtful), price zone with repeated levels and combined reward:risk, changes, reliability, each video's reason, and the stock AI summary.
- Clicking a ticker in any table selects it.
- Rendering reuses `DashboardView` (scrolling, wrapping, title/para/dim/warn/bullets blocks) through a subclass in `collection.py` that adds `table`, `bars`, `actions` and `text` blocks with click handlers.
- The page reloads when shown and after a job finishes.

## 4. AI summary

- Button **[ RANGKUM AI ]** / **[ AI SUMMARY ]** for a stock or a date; disabled when the LLM is not set up.
- Input: only the archived extraction (no transcripts). For a stock: each view's date, channel, title, stance, levels, reason, expectation, confidence and doubtful flag. For a date: each video's title, channel, sentiment, summary, outlook and stock stances.
- System prompt: summarise only what the data says; never add prices, targets or tickers; point out agreement, disagreement, changes over time, risks and what to re-check; 4–8 short bullet points in the app language; not investment advice.
- Runs in a worker thread through `app.llm_complete(system, user)` (one non-streaming chat completion with the configured endpoint, key and model). The page polls for the result. Errors are shown in red under the button.
- The result is cached (section 1) and shown with its date and model.

## 5. Code layout

| Unit | Responsibility |
|---|---|
| `archive.py` | Records: build from an analysis, save, load, latest per video, delete, import, fill video dates (given a metadata function), AI cache paths; all calculations in section 2. Imports `report`; no Tk |
| `collection.py` | `CollectionPage(tk.Frame)` and its view; strings in its own `(ID, EN)` table like `report.py`. Talks to the app only through `App` methods |
| `app.py` | `ARCHIVE` folder; `Pipeline` keeps `video_date`/`channel` and writes the archive record; `App.collection_records()`, `App.fill_video_dates()`, `App.open_record()`, `App.llm_complete()`; the page and its menu item |

## 6. Tests

- `tests/test_archive.py`: record building, latest per video, import with marker, delete, fill dates, every calculation in section 2 (including the TLKM-style example: WATCH ×4 + BUY ×1, entry 2.060–2.100, SELL→BUY change), AI cache key changes when a record is added.
- Pipeline: `video_date`/`channel` stored from `extract_info`; a fresh analysis writes an archive record; viewing a saved one does not.
- GUI: the page lists dates and stocks, selecting a stock renders its detail, a disagreement shows `!`, the AI button calls `llm_complete` once and caches the result.
