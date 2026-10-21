# Troubleshooting

Messages are quoted in English; the Indonesian interface shows the same messages translated. If the app window closes without a message, start it from a terminal (`.venv\Scripts\python.exe app.py`) to see the error.

## Setup and startup

**`ModuleNotFoundError` (faster_whisper, yt_dlp, openai, …)**
The virtual environment is missing or not active. Run `pip install -r requirements.txt` inside `.venv`, and start the app with `.venv\Scripts\python.exe app.py` or `run.bat`.

**`No module named 'tkinter'`**
Your Python was installed without Tk. On Windows reinstall Python with *tcl/tk and IDLE* ticked. On Linux install your distribution's `python3-tk` package.

**`run.bat` does nothing**
It launches `pythonw.exe` (no console), so errors are invisible. Run `python app.py` from a terminal instead.

## Download

**An error mentioning yt-dlp, HTTP 403, or "unable to extract"**
YouTube changes often. Update the downloader: `pip install -U yt-dlp`. Age-restricted, members-only or private videos cannot be downloaded without cookies, which the app does not support.

**"Enter a valid YouTube video URL."**
The URL must start with `http://` or `https://`. Playlist links use only the single video.

## Transcription

**It is very slow**
Without an NVIDIA GPU, Whisper runs on the CPU. `large-v3` is slow there; choose `medium` or `small` in **[ SETTINGS ] > TRANSCRIPTION**, or use the Colab engine. The status line shows `(CPU)` or `(CUDA)` while transcribing.

**CUDA / cuDNN / cuBLAS errors with an NVIDIA GPU**
The GPU libraries required by CTranslate2 (the engine behind faster-whisper) are not installed or not found. Follow the CTranslate2 / faster-whisper GPU installation notes, or switch to the Colab engine. The app picks CUDA automatically when CTranslate2 reports a GPU and has no switch to force the CPU yet.

**"No speech was detected in this audio."**
Whisper's voice filter found no speech: wrong video, music only, or the wrong audio language. Retry with **Auto** language.

**Names and numbers are wrong**
Expected for speech recognition. Use a larger Whisper model, set the correct audio language, and check the timestamps listed on each stock card against the video.

**The transcript is full of repeated phrases**
The app already collapses repeats of 4 or more. Heavy repetition usually means poor audio or the wrong language setting.

## Analysis (LLM)

**"NINEROUTER_API_KEY is not set (app/.env)…"**
Add the key in **[ SETTINGS ] > ANALYSIS (LLM)**. The transcript is still available in the TRANSCRIPT tab, and the next **[ ANALYZE ]** reuses it.

**"No LLM model is set…" or the warning "LLM not set up" when you press ANALYZE**
A fresh install has no default model because every endpoint offers different ones. Open **[ SETTINGS ] > ANALYSIS (LLM)**, press **[ PICK MODEL ]** (or type a model id), and **[ SAVE ]**. The same warning appears if the API key is empty.

**Connection refused / cannot load the model list**
The endpoint is not running or the URL is wrong. For a local 9router, start it first and check the URL (default `http://localhost:20128/v1`). In the model picker you can type a model name by hand even when the list cannot load.

**"The model's reply was not valid JSON, so no dashboard can be built."**
The raw reply is shown in the ANALYSIS tab. Try again or choose another model; weaker models sometimes ignore the JSON-only instruction. Re-running reuses the cached transcript.

**Red warning: the model's reply was cut off**
The dashboard shows what could be recovered and the last stock may be incomplete. Press **[ ANALYZE ]** again, or pick a model with a larger output limit. Very long videos make long replies more likely.

**No stocks were found**
The speaker may not have discussed specific stocks, or the transcript is poor. Try a larger Whisper model or a different LLM model.

## Colab engine

**"The Colab server is not set up…"**
Open **[ SETTINGS ] > TRANSCRIPTION** and paste the `URL TOKEN` line from the notebook into the URL field (the token fills in automatically), then **[ SAVE ]**.

**TEST CONNECTION fails, or "Colab server problem: …"**
- The notebook's last cell must still be running. Colab sessions end when idle or after a time limit.
- The URL and token change every session; paste the new line.
- *401 token salah / wrong token*: the token does not match this session.
- *409 server busy*: a previous job did not stop within 30 seconds; wait a moment and retry, or restart the notebook's last cell.
- *Connection refused / timeout*: the tunnel is gone; run the last notebook cell again.

**The Colab job stopped midway**
Whatever was transcribed is checkpointed. Reconnect, then press **[ ANALYZE ]** and choose **[ RESUME ]**. The compressed audio is reused, so it is not compressed again.

**No GPU in Colab**
Choose *Runtime > Change runtime type > T4 GPU* and run the notebook again. Free-tier GPU availability varies. The settings test reports `Device: cpu` when no GPU is attached.

More in [colab/README.md](../colab/README.md).

## Settings and files

**A setting reverts or is ignored**
`settings.json` takes precedence over `.env` for the LLM model, engine and Colab values. Change them in the Settings dialog (it updates both) or remove the key from `settings.json`. See [Configuration](configuration.md#precedence).

**History is empty**
History reads `cache/`. Entries appear after a transcription finishes or is cancelled with some text. It is unavailable while a job runs.

**Disk space is growing**
`work/` keeps downloaded audio and `transcripts/` keeps text copies. Delete files you no longer need; entries remain in History but a restart will download again.

**Theme looks wrong after changing the OS dark/light mode**
*Follow system* is read when the app starts. Restart the app, or pick a theme explicitly.
