# Changelog

## Unreleased

### Added
- The dashboard and the report start with the video title and a clickable link (or the file name for transcript files), and the link is included in copied and saved text.
- **History** shows the selected item's full title and video link, with **[ OPEN LINK ]** and **[ COPY LINK ]**.
- Errors in step 2 (transcription) and step 3 (analysis) name the failed step, how many automatic tries were made, and what to press next. Temporary connection problems to the Colab server or the LLM are retried up to 3 times; a transcription continues from its last checkpoint.
- Finished analyses are saved with their transcript, including files opened with **[ OPEN FILE ]**. Clicking a finished transcript in **History** shows its dashboard, analysis and transcript without calling the LLM; **[ REANALYZE ]** creates the analysis again.
- **Market Overview** page (Indonesian **Ringkasan Pasar**; on the menu bar and `Ctrl+3`, and the start page once analyses exist): every analysis grouped by the video's upload date, the most-discussed stocks, market tone per date, a per-date comparison of stocks discussed in several videos, and a per-stock view with consensus, disagreement, timeline, combined price zone, changes of view and reliability. An optional AI summary per stock or date is made from the extracted data and saved. Earlier analyses are imported once; **[ FILL IN VIDEO DATES ]** adds missing upload dates.
- New analyses also store the video's upload date and channel.
- **Stock price window**: click a ticker on a Dashboard card, or **[ STOCK PRICE ]** in Market Overview, for the delayed Yahoo Finance price, a 1D–1Y chart with the videos' buy/target/loss-limit levels, and the move since each video with target and loss-limit hits. Refreshes every 60 s during IDX hours; prices are fetched only while the window is open. Chart ranges use TradingView's labels (1D, 5D, 1M, 3M, 1Y) in both languages.
- **[ TRADINGVIEW ]** in the price window and on each stock in Market Overview opens the stock on TradingView.com.
- **[ CANDLE CHART ]** in the price window: a TradingView-style candlestick window (TradingView Lightweight Charts™ v5.2.1, Apache 2.0, bundled) with volume, the videos' levels as price lines and their stances as markers; 1D–1Y; refreshes during IDX hours. Needs the new optional dependency `pywebview` and Edge WebView2.
- Menu bar: **File**, **View**, **Job**, **Tools**, **Help**, with shortcuts (`Ctrl+O`, `Ctrl+S`, `Ctrl+Shift+C`, `Ctrl+1`, `Ctrl+2`, `Ctrl+,`, `Esc`). Theme and language can be switched from **View**.
- While a job runs on another page, the title row shows its progress, then whether it finished, was cancelled or failed.

### Changed
- **History** is now a page in the main window (**View > History**) instead of a separate window. The **[ SETTINGS ]** and **[ HISTORY ]** buttons are replaced by the menu; **[ PAUSE ]** and **[ CANCEL ]** moved next to the status line.
- The start button is now **[ RUN ]** (Indonesian **[ PROSES ]**) and the report tab **REPORT** (**HASIL ANALISIS**), so the button and the tab no longer share a label.
- The copy and save buttons name the tab they act on, for example **[ COPY TRANSCRIPT ]**.

### Fixed
- Resuming a partial transcript needs no network when its audio and checkpoint are already on disk.
- **History** stays open while another job runs; choosing an item then shows a message instead of closing the window silently.
- Colab notebook: `open() got an unexpected keyword argument 'metadata_errors'` came from PyAV 19, which removed that argument while faster-whisper still uses it. The install cell now pins `av>=18.1,<19` and prints the installed PyAV version. Re-download `Whisper_Server.ipynb` and run it in a fresh session.

## 1.1.0 - 2026-10-21

### Added
- Transcripts opened with **[ OPEN FILE ]** now appear in **History** (as `FILE` entries) and can be analysed again from the saved copy.
- The LLM model has no default any more: a fresh install must set one (**[ PICK MODEL ]** lists what the endpoint offers), and the app warns before a job starts if the API key or model is missing.
- **Name:** the app is now called **TickerQuill** (was STOCK-SCOPE).
- pytest suite, `requirements-dev.txt`, GitHub Actions CI, `.gitattributes`.
- **Colab engine:** run Whisper on a Google Colab GPU (`remote.py`, `colab/`), with streaming progress, cancel and resume.
- **Settings dialog** with General, Transcription and Analysis (LLM) tabs; edits `.env` and `settings.json` and applies changes immediately.
- **Themes:** Retro Green, Retro Amber, Modern Dark, Light, Follow system, switched live and remembered.
- Active tab is marked with an accent colour and underline.
- `requirements.txt`, `.env.example`, `.gitignore`.
- Documentation: README, user guide, configuration, methodology, architecture, troubleshooting, Colab guide.

### Changed
- Saved files are named `tickerquill-dashboard.md`, `tickerquill-analysis.md` and `tickerquill-transcript.txt` by default.
- The main window is simplified: engine, Whisper model, audio language, app language and LLM model controls moved into Settings, leaving a one-line summary that opens Settings when clicked.
- Whisper model is now remembered between runs.
- Colors are read from the live palette (`theme.T`) instead of constants.

## 1.0

- YouTube → Whisper → LLM pipeline with a retro terminal interface.
- Transcript cache, checkpointed transcription with pause, cancel and resume, and a History dialog.
- Dashboard with market tone gauge, stock cards, reward:risk, plan completeness, tips, method and glossary.
- Indonesian and English interface and reports; open an existing transcript file; copy and save.
