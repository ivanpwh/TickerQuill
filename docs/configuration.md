# Configuration

Every option can be changed in **[ SETTINGS ]** inside the app. This page documents where each value is stored, its default and what it does. You only need to read it if you edit files by hand or run into precedence questions.

## Where settings live

| File | Holds | Notes |
|---|---|---|
| `.env` | Endpoint, API key, language defaults, engine and Colab values | `KEY=value` lines. Start from [`.env.example`](../.env.example) |
| `settings.json` | Theme, Whisper model, and choices made in the app (engine, Colab connection, LLM model) | Written by the app; safe to delete (defaults return) |
| OS environment | Any `.env` variable | Used when `.env` does not define it |

Both files contain secrets (API key, Colab token). Keep them out of version control; the provided `.gitignore` already excludes them.

## All options

| Setting (Settings dialog) | Key | Stored in | Default | Description |
|---|---|---|---|---|
| App language | `APP_LANG` | `.env` | `ID` | `ID` or `EN`. Interface and report labels, and the language requested from the LLM |
| Appearance theme | `theme` | `settings.json` | `retro_green` | `retro_green`, `retro_amber`, `dark`, `light`, `system` |
| Run Whisper on | `WHISPER_ENGINE` / `engine` | `.env` and `settings.json` | `Local` | `Local` (this computer) or `Colab` |
| Whisper model | `whisper_model` | `settings.json` | `large-v3` | `large-v3`, `medium`, `small`, `base` |
| Default audio language | `AUDIO_LANG` | `.env` | `Indonesia` | `Auto`, `Indonesia`, `English`, `Melayu`, `Mandarin`, `Japanese`, `Korean`, `Arabic` |
| Colab server URL | `COLAB_WHISPER_URL` / `colab_url` | `.env` and `settings.json` | empty | Printed by the notebook; changes every Colab session |
| Colab token | `COLAB_WHISPER_TOKEN` / `colab_token` | `.env` and `settings.json` | empty | Printed by the notebook; changes every Colab session |
| LLM endpoint URL | `NINEROUTER_BASE_URL` | `.env` | `http://localhost:20128/v1` | OpenAI-compatible base URL (the app calls `{base}/chat/completions` and `{base}/models`) |
| LLM API key | `NINEROUTER_API_KEY` | `.env` | empty | Required for the analysis step |
| LLM model | `NINEROUTER_MODEL` / `model` | `.env` and `settings.json` | empty (**must be set**) | Model id sent to the endpoint. Every endpoint offers different models, so a fresh install has none; use **[ PICK MODEL ]** to list yours |

Settings that exist in both files are kept in sync when you save from the dialog.

## Precedence

When the same value is defined in several places, the first match wins:

| Value | Order |
|---|---|
| LLM model | `settings.json` (`model`) → `.env` / OS `NINEROUTER_MODEL` → empty |
| Engine | `settings.json` (`engine`) → `.env` / OS `WHISPER_ENGINE` → `Local` |
| Colab URL and token | `settings.json` → `.env` / OS |
| Everything else in `.env` | `.env` → OS environment → built-in default |
| `theme`, `whisper_model` | `settings.json` → built-in default |

Consequence: if you hand-edit `.env` for the model, engine or Colab values but `settings.json` already has one, the `settings.json` value wins. Edit in the Settings dialog (it updates both) or delete the key from `settings.json`.

## How the Settings dialog saves

- Only fields you actually changed are written, so untouched secrets are never rewritten.
- `.env` edits keep comments, unknown lines and ordering. Values containing spaces or `#` are written in double quotes.
- Clearing a text field restores its default (an empty value is treated as unset).
- Changes take effect immediately: model, engine and languages update the main window, the theme re-colours every open window, and the endpoint and key are read again on the next analysis.
- Changing the app language rebuilds the dialog in the new language.

## `.env` format

```ini
# comment on its own line
NINEROUTER_API_KEY=sk-...
NINEROUTER_BASE_URL=http://localhost:20128/v1
APP_LANG=EN
```

One `KEY=value` per line; surrounding quotes are stripped; comments must be on their own line (inline `# comment` after a value is **not** supported).

## `settings.json`

```json
{
  "model": "provider/model-name",
  "engine": "Colab",
  "whisper_model": "medium",
  "theme": "dark",
  "colab_url": "https://example.trycloudflare.com",
  "colab_token": "..."
}
```

## Data folders

| Folder | Contents | Safe to delete? |
|---|---|---|
| `work/` | Downloaded audio, and `work/upload/` (temporary Colab upload) | Yes, except while a job is paused or resumable; it will be downloaded again |
| `cache/` | `<video id>.<lang>.json` finished transcripts, `<video id>.<lang>.partial.json` checkpoints, and `file-<hash>.file.json` copies of opened transcript files (what History lists) | Yes, but you lose History and resume points |
| `transcripts/` | Plain-text copies of finished transcripts | Yes |
