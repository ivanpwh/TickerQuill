# User guide

How to use TickerQuill day to day, and how to read what it produces. For installation see the [README](../README.md).

## Contents
0. [Menus and pages](#menus-and-pages)
1. [First-time setup](#1-first-time-setup)
2. [Analysing a video](#2-analysing-a-video)
3. [When a video was seen before](#3-when-a-video-was-seen-before)
4. [Pause, cancel and resume](#4-pause-cancel-and-resume)
5. [Using your own transcript](#5-using-your-own-transcript)
6. [History](#6-history)
7. [Reading the results](#7-reading-the-results)
8. [Copy and save](#8-copy-and-save)
9. [Settings, language and themes](#9-settings-language-and-themes)
10. [Tips for better results](#10-tips-for-better-results)

---

## Menus and pages

The main window has two pages: **Analysis** (paste a URL, run, read the results) and **History** (saved transcripts). Switch with **View > Analysis** / **View > History** or `Ctrl+1` / `Ctrl+2`. Each page keeps its state while you look at the other one. Settings, the model picker and confirmations open as dialogs.

| Menu | Items |
|---|---|
| **File** | Open file… `Ctrl+O` · Copy {tab} `Ctrl+Shift+C` · Save {tab}… `Ctrl+S` · Exit |
| **View** | Analysis `Ctrl+1` · History `Ctrl+2` · Dashboard / Report / Transcript · Theme · Language |
| **Job** | Run `Enter` · Pause / Resume · Cancel `Esc` |
| **Tools** | Settings… `Ctrl+,` · Pick model… · Test Colab connection |
| **Help** | User guide · About TickerQuill |

Items that cannot be used right now are greyed out: Run and Open file while a job runs, Pause and Cancel when nothing runs, Copy and Save when the current tab is empty or another page is open. Menu labels follow the app language. The menu bar itself uses the Windows colours; it does not follow the theme.

While a job runs and the History page is open, the title row shows the progress, for example `● 2/3 TRANSCRIBING (CUDA) 45%`. When the job ends there it shows `✓` (done), `■` (cancelled) or `!` (error) with the final status. The app never switches pages on its own; click the indicator or press `Ctrl+1` to see the result.

## 1. First-time setup

1. Start the app and open **Tools > Settings** (`Ctrl+,`).
2. **ANALYSIS (LLM)** tab: enter the endpoint URL, API key and model. **[ PICK MODEL ]** asks your endpoint for its model list; you can also type a model name directly.
3. **TRANSCRIPTION** tab: choose where Whisper runs (**Local** or **Colab**), the Whisper model and the default audio language. See the [Colab guide](../colab/README.md) if you pick Colab.
4. **GENERAL** tab: language and theme.
5. **[ SAVE ]**. Changes apply immediately.

The grey line under the URL bar always shows the active choices, e.g. `Whisper large-v3 on Local | Audio: Indonesia | LLM: … | click to change`. Click it to reopen Settings.

Without an API key the app still downloads and transcribes; it stops before the analysis step and tells you so. The transcript stays available in the **TRANSCRIPT** tab.

## 2. Analysing a video

1. Paste the video URL into **URL>**. Supported forms: `youtube.com/watch?v=…`, `youtu.be/…`, `…/shorts/…`, `…/live/…`, `…/embed/…`. Playlists are not expanded; only the single video is used.
2. Press **[ RUN ]** (or **Enter**).
3. The status line and progress bar show the stage:

| Status | Meaning |
|---|---|
| 1/3 FETCHING VIDEO INFO | Reading the title and id |
| 1/3 DOWNLOADING AUDIO | Downloading the best audio stream into `work/` |
| 2/3 LOADING WHISPER MODEL | Loading the model (the first run also downloads it) |
| 2/3 TRANSCRIBING (CPU / CUDA) | Speech-to-text; the percentage is position in the audio |
| 2/3 COMPRESSING AUDIO / UPLOADING TO COLAB / COLAB LOADING WHISPER MODEL | Colab engine only |
| 2/3 TRANSCRIPT FROM CACHE | An earlier transcript is being reused |
| 3/3 ANALYZING STOCKS | The LLM is extracting the structured report |
| DONE · CANCELLED · ERROR · PAUSED | Final or paused states |

4. When the analysis finishes the **DASHBOARD** tab opens. The transcript is available as soon as transcription ends, even if the analysis fails.

Only one job runs at a time; the buttons that would start another are disabled until it ends.

## 3. When a video was seen before

If the URL (with the selected audio language) already has a cache entry, a small line under the URL bar says so, and **[ RUN ]** asks what to do:

| Situation | Choices |
|---|---|
| Finished transcript exists | **[ REUSE ]** (go straight to analysis) · **[ TRANSCRIBE AGAIN ]** · **[ CANCEL ]** |
| Unfinished transcript exists | **[ RESUME ]** from the saved point · **[ START OVER ]** · **[ CANCEL ]** |

Reusing is much faster and is the default choice for repeat analyses, for example with a different LLM model. The cache is keyed by video and audio language, not by Whisper model.

## 4. Pause, cancel and resume

- **[ PAUSE ]** (next to the status line, or **Job > Pause**) is available while downloading, loading the model and transcribing. **[ RESUME ]** continues. Pausing a download stops it and continues from the partial file.
- **[ CANCEL ]** (or `Esc`) stops the job. If any transcript text exists it is saved as a checkpoint (written every 10 segments and on cancel or error). Press **[ RUN ]** again and choose **[ RESUME ]**.
- With the Colab engine a very long pause can drop the connection; the checkpoint still lets you resume.

## 5. Using your own transcript

Press **[ OPEN FILE ]** and pick a `.txt`, `.md`, `.srt` or `.vtt` file. The app skips download and Whisper, cleans repeated phrases and runs only the analysis. Files are read as plain UTF-8 text; subtitle formats are not parsed, so cue numbers and time ranges stay in the text. Lines in the form `[hh:mm:ss] text` (the format TickerQuill writes) give the best timestamps in the report.

The transcript is also saved to **History** as a **FILE** entry (the same content never creates a second entry), so you can analyse it again later, for example with another LLM model, without keeping the original file.

## 6. History

The **History** page (**View > History**, `Ctrl+2`) lists everything in `cache/`, newest first: status (`DONE` or percent complete), title, audio language, Whisper model and date. Transcripts you opened with **[ OPEN FILE ]** are listed too, with `FILE` in the language column and `-` as the model.

| Button | Action |
|---|---|
Selecting an item shows its full title and video link under the list. **[ OPEN LINK ]** opens the video in your browser and **[ COPY LINK ]** copies the link. For a `FILE` entry the line shows the original file path; COPY LINK copies the path and OPEN LINK is disabled.

| Button | Action |
|---|---|
| **[ USE / RESUME ]** (or double-click) | Resumes an unfinished transcript. For a finished one it shows the saved dashboard, report and transcript without calling the LLM; if no analysis was saved yet it says so |
| **[ REANALYZE ]** | Runs the LLM analysis again on the saved transcript (an unfinished transcript is resumed first) |
| **[ RESTART ]** | Transcribes the selected video again from scratch (for a `FILE` entry: same as USE, since there is nothing to transcribe) |
| **[ DELETE ]** | Removes the entry from the cache. The `.txt` in `transcripts/` and the audio in `work/` are kept |

History can be browsed while a job is running; choosing an item then shows "A job is already running." in red and stays on the page. The list reloads whenever the page is opened and when a job ends.

## 7. Reading the results

![Dashboard](images/dashboard-retro-green.png)

The dashboard and report start with the video title and its link (click it to open the video). For a transcript file the line shows the file name instead.

### Dashboard tab

| Section | What it tells you |
|---|---|
| **Quick summary** | 2–4 sentence gist of the video, then a stats line: stocks discussed, total mentions in the transcript, and **transcript reliability** |
| **Video mood (market tone)** | A gauge from NEGATIVE to POSITIVE with the **tone score** (−1…+1), the speaker's own view of the market (optimistic, pessimistic, neutral, mixed) and their market outlook |
| **Stocks discussed** | One card per stock, most-mentioned first |
| **Risks mentioned** | Risks the speaker raised, plus notes on poor transcript quality |
| **Tips for you** | Context-aware cautions (see below) |
| **Method & calculations** | How each number was produced, with this video's own values plugged in |
| **Glossary** | Ticker, entry, target, stop loss, support/resistance, reward:risk, IHSG, FOMO |

A red box at the top means the model's reply was cut off; the dashboard shows what could be recovered and the last stock may be incomplete. Press **[ RUN ]** again (the transcript is reused) or pick another model.

![Stock cards](images/stock-cards-retro-green.png)

### A stock card

- **Ticker, name and stance badge**: BUY, HOLD, SELL, WATCH or AVOID, with a one-sentence explanation. WATCH means "on the watchlist, no clear buy suggestion yet".
- **Mentioned N× (P%)**: how often the stock appears in the transcript and its share of all stock mentions. A rough measure of how much of the video was about it.
- **Plan completeness (0–100)**: 20 points each for a stated buy price, sell target, loss limit, a reason, and names/numbers that are not doubtful. A high score means the speaker gave a complete plan, not that the plan is good.
- **Levels**: buy price, sell target, loss limit (stop loss), support, resistance, exactly as spoken.
- **Reward:Risk**: computed only when buy price, target and loss limit are all stated and ordered sensibly (stop < buy < target). Shows potential gain %, potential loss % and the ratio. A ratio of 2 means the upside is twice the downside.
- **Reason / Expectation / Speaker confidence / Discussed at**: what the speaker said, how sure they sounded (Low, Medium, High) and the video timestamps to jump to.
- **(!) doubtful** warning: the name or numbers may be misheard. Replay that part of the video.

### Tips for you

Generated from the data, for example: doubtful stocks, a BUY without a stop loss, reward:risk below 1.5 or looking reasonable, a very optimistic video (FOMO warning), a negative video (do not panic-sell over one video). Position-sizing, staleness and "consult a licensed adviser" reminders are always shown. Exact rules: [Methodology](methodology.md#tips).

### Report and Transcript tabs

- **REPORT**: the same content as a Markdown-style report (summary, stocks, market outlook, risks).
- **TRANSCRIPT**: the video title and the full timestamped text, ready to copy or save.

## 8. Copy and save

The copy and save buttons act on the tab you are viewing and name it: **[ COPY DASHBOARD ]**, **[ COPY REPORT ]**, **[ COPY TRANSCRIPT ]** (Indonesian: **[ SALIN … ]** / **[ SIMPAN … ]**). The video title and link are included. The dashboard and report save as `.md`, the transcript as `.txt`. Default names are `tickerquill-dashboard.md`, `tickerquill-analysis.md` and `tickerquill-transcript.txt`.

Finished transcripts are also written automatically to `transcripts/<title>-<video id>.txt`.

## 9. Settings, language and themes

- **App language** switches the interface and the report labels between Indonesian and English. The dashboard is re-labelled immediately without calling the LLM again. Free-text parts written by the LLM (summary, reasons) stay in the language they were generated in; the language used for new analyses follows the app language.
- **Theme**: Retro Green (default), Retro Amber, Modern Dark, Light, or Follow system (checked when the app starts). The change is instant and remembered.
- Both can also be switched from **View > Theme** and **View > Language** without opening Settings.

![Light theme](images/dashboard-light.png)

All options: [Configuration](configuration.md).

## 10. Tips for better results

- **Pick the right audio language.** Auto-detect works, but forcing the language usually helps with tickers and numbers.
- **Bigger Whisper models are more accurate** but slower. If a job is too slow locally, try `medium`/`small` or use the Colab engine.
- **Treat "doubtful" flags seriously.** Whisper often mishears company names ("MEDCO" for MEDC) and numbers.
- **Cross-check every price level** against the video and against current market data before acting.
- **Try another LLM model** if the report is empty, cut off, or the stocks look wrong. Re-running reuses the cached transcript, so it is quick.
- **Delete `work/` occasionally**; downloaded audio is kept for resuming and can grow large.
