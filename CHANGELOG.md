# Changelog

## Unreleased

### Added
- The dashboard and the report start with the video title and a clickable link (or the file name for transcript files), and the link is included in copied and saved text.
- **History** shows the selected item's full title and video link, with **[ OPEN LINK ]** and **[ COPY LINK ]**.
- Errors in step 2 (transcription) and step 3 (analysis) name the failed step, how many automatic tries were made, and what to press next. Temporary connection problems to the Colab server or the LLM are retried up to 3 times; a transcription continues from its last checkpoint.
- Finished analyses are saved with their transcript, including files opened with **[ OPEN FILE ]**. Clicking a finished transcript in **History** shows its dashboard, analysis and transcript without calling the LLM; **[ REANALYZE ]** creates the analysis again.

### Changed
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
