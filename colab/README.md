# Whisper on Google Colab

Run the speech-to-text step on a Colab GPU instead of your own computer. The app still downloads the YouTube audio locally (Colab IPs are often blocked by YouTube), compresses it to Opus mono 16 kHz (about 14 MB per hour), uploads it to a Whisper server running in Colab, and receives the text back segment by segment. Progress, pause/cancel and "resume" checkpoints keep working.

## Use it

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/ivanpwh/TickerQuill/blob/main/colab/Whisper_Server.ipynb)

Short version (the full illustrated walk-through, including what you should see at each step and what to do when it fails, is in the main README: [Running Whisper on Google Colab](../README.md#running-whisper-on-google-colab)):

1. Open `Whisper_Server.ipynb` in Google Colab (**File > Upload notebook**), then **Runtime > Change runtime type > T4 GPU**.
2. **Runtime > Run all**. The last cell prints one `URL TOKEN` line and keeps running. Leave it running.
3. In the app: **[ SETTINGS ] > TRANSCRIPTION** → **Run Whisper on = Colab**, paste the whole line into **Colab server URL**, **[ TEST CONNECTION ]** (expect `Connected. Device: cuda …`), **[ SAVE ]**.
4. Press **[ ANALYZE ]** as usual.

The URL and token change every Colab session. Alternative without the dialog: set `COLAB_WHISPER_URL`, `COLAB_WHISPER_TOKEN` and `WHISPER_ENGINE=Colab` in `.env` (see [`.env.example`](../.env.example)).

## What is in this folder

| File | Purpose |
|---|---|
| `whisper_server.py` | The FastAPI server (source of truth) |
| `Whisper_Server.ipynb` | The notebook you run in Colab. Generated: `python colab/build_notebook.py` re-embeds `whisper_server.py` |
| `build_notebook.py` | Notebook generator |

## What the notebook does

1. Checks that a GPU is attached and installs `faster-whisper`, `fastapi`, `uvicorn`, `python-multipart`.
2. Writes `whisper_server.py` and starts it as a separate process with the CUDA libraries from the pip `nvidia-*` packages on `LD_LIBRARY_PATH`.
3. Downloads `cloudflared` and opens a free Cloudflare quick tunnel to the server. No account is needed.
4. Generates a random token, prints `URL TOKEN`, then waits.

## Security

- Every request must carry the random token; without it the server answers 401.
- The URL is public but unguessable, and the token is generated per session. Anyone holding both can use your Colab session, so do not share them.
- The audio of the video you analyse is sent to Colab through the Cloudflare tunnel. Use the Local engine for anything you would not upload.

## Limits and behaviour

- One transcription at a time. A new request stops a stale one so that a crashed client does not block you.
- Cloudflare's free tunnel limits a request to 100 MB; compressed audio of about 7 hours fits.
- A long **pause** can drop the tunnel connection. Whatever was transcribed is checkpointed; press **[ ANALYZE ]** and choose **[ RESUME ]**. The compressed audio is kept until the transcription completes, so resuming does not recompress.
- Free Colab sessions end when idle or after a time limit, and GPU availability varies. Check Google's terms of use for how you may use Colab.
- Compression takes time proportional to the video length (68-94 seconds per hour of audio on the machine it was measured on). It is done once per video; resuming reuses the result.

## Troubleshooting

See [Troubleshooting > Colab engine](../docs/troubleshooting.md#colab-engine).

## Status

The server and client were tested end to end on a local machine (CPU, `tiny` model): streaming, cancel, resume, wrong token and connection errors. The notebook itself, the Cloudflare tunnel and GPU speed have **not** been verified in a real Colab session yet. If something fails there, please report the error text from the notebook output.
