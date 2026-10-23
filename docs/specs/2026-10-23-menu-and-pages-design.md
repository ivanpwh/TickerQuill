# Menu bar and pages: design

Date: 2026-10-23 · Status: approved, implementation started without a separate spec review (at the user's request) · Runs before sub-project B (COLLECTION), which adds its page and menu item.

## Problems

1. The row next to the URL field mixes five buttons with different jobs: start (PROSES, BUKA FILE), navigation (RIWAYAT) and job control (JEDA, BATAL).
2. History and Settings each open a separate window, and COLLECTION would add another.
3. Upcoming features (COLLECTION, stock price) have no obvious place.

## Decisions

| Question | Decision |
|---|---|
| Navigation | The **native Windows menu bar** (`tk.Menu` set with `app.config(menu=…)`). Its strip uses system colours and does not follow the theme. |
| Pages in the main window | **ANALYSIS** and **HISTORY** now; **COLLECTION** is added by sub-project B. **Settings** stays a dialog. Stock prices (sub-project C) will be small windows. |
| Code layout | `menus.py` holds the menu bar (it only talks to the `App` instance). `HistoryDialog` becomes `HistoryPage(tk.Frame)` **in `app.py`**. It needs `list_history`, `AUDIO_LABEL_OF` and friends, and tests monkeypatch `app.CACHE`. A separate module would have to import `app`, which loads `app.py` a second time when the program runs as `python app.py` (`__main__` vs `app`). The conversion does not grow `app.py`. |

## 1. Window structure

```
 File   View   Job   Tools   Help                          ← native menu bar
┌──────────────────────────────────────────────────────────────────────────┐
│ TickerQuill v1.1.0_  ›  ANALISIS                  ● 2/3 TRANSKRIP 45%    │ title, page, job indicator
│ YOUTUBE >> WHISPER >> SARAN & PREDIKSI SAHAM                             │
│ ── ANALYSIS page ─────────────────────────────────────────────────────── │
│ URL> [_______________________________]  [ PROSES ]  [ BUKA FILE ]        │ start actions only
│ [OK] Transkrip sudah ada …                                               │
│ Whisper large-v3 di Colab | Audio | LLM … | klik untuk ubah              │
│ 2/3 TRANSKRIP                                     [ JEDA ] [ BATAL ]     │ job control next to the status
│ [████████░░░░] 45%                                                       │
│ [DASHBOARD] [HASIL ANALISIS] [TRANSKRIP]       [SALIN …] [SIMPAN …]      │
│ ┌──────────────────────────────────────────────────────────────────────┐ │
│ │ result                                                               │ │
│ └──────────────────────────────────────────────────────────────────────┘ │
│ ! disclaimer                                                             │
└──────────────────────────────────────────────────────────────────────────┘
```

- The `[ PENGATURAN ]` button (top right) and the `[ RIWAYAT ]` button are removed. The clickable settings summary line stays.
- JEDA and BATAL move to the status row.

## 2. Menus

Labels follow the app language. "{tab}" is the active result tab.

| Menu | Items |
|---|---|
| **File** | Open transcript… `Ctrl+O` · Copy {tab} `Ctrl+Shift+C` · Save {tab}… `Ctrl+S` · ─ · Exit |
| **View** | Analysis `Ctrl+1` · History `Ctrl+2` · ─ · Dashboard / Report / Transcript · ─ · Theme ▸ · Language ▸ |
| **Job** | Run URL `Enter` · Pause / Resume · Cancel `Esc` |
| **Tools** | Settings… `Ctrl+,` · Pick LLM model… · Test Colab connection |
| **Help** | User guide · About TickerQuill |

- Built by `menus.MenuBar(app)`. One table holds each item's label key, command, accelerator text and key bindings, so the shown accelerator and the binding cannot drift apart.
- `MenuBar.refresh_labels()` is called from `apply_lang()` and relabels entries with `entryconfig`; the menu is not rebuilt.
- `MenuBar.refresh_state()` is called after `start`, `finish`, `show` (result tab), `show_page`, queue events and `apply_lang`:
  - Run URL and Open transcript are disabled while a job runs.
  - Pause/Resume mirrors the `[ JEDA ]` button (state and label). Cancel is enabled only while a job runs.
  - Copy/Save are enabled only on the ANALYSIS page when the active tab has content.
- View › Dashboard/Report/Transcript switches to the ANALYSIS page and that tab.
- View › Theme: radio items for `theme.CHOICES`, applied through `App.set_theme` (saved to `settings.json`).
- View › Language: radio items for `UI_LANGS`, written to `APP_LANG` in `.env`, then `apply_lang()`.
- If the Settings dialog is open when the theme or language changes from the menu, it is closed and reopened on the same tab so it shows the new values.
- Tools › Pick LLM model opens `ModelPicker`. Tools › Test Colab connection opens Settings on the TRANSCRIPTION tab and runs its test.
- Help › User guide opens `docs/user-guide.md` with `os.startfile`, falling back to the GitHub page. Help › About shows name, version, MIT licence and the disclaimer.

### Key bindings

- `Ctrl+O`, `Ctrl+S`, `Ctrl+Shift+C`, `Ctrl+1`, `Ctrl+2`, `Ctrl+,` and `Esc` are bound on the main window. `Enter` in the URL field still runs the job.
- Tk's `Text` class binds `Ctrl+O` to "insert a new line", and class bindings run before window bindings. Shortcuts that a widget class already binds are rebound on that class with the menu action and `return "break"`, so they run once and the text is not changed.
- `Esc` cancels only while a job runs.

## 3. Pages

- `App.show_page(name)` hides the current page and shows the chosen one. Pages keep their state (results, scroll position, History selection).
- The title row shows `› <PAGE NAME>`.
- **HISTORY page** (`HistoryPage`): the same list, detail line and buttons as the old dialog, without CLOSE.
  - Reloaded every time the page is shown and when a job finishes.
  - USE / REANALYZE / RESTART / double-click switch to ANALYSIS and start the job.
  - If a job is running, the page does not switch; the info line shows "A job is already running." in red (no message box).
  - DELETE still asks for confirmation.
- **Job indicator** (right side of the title row, clickable, returns to ANALYSIS):
  - Hidden on the ANALYSIS page.
  - While a job runs on another page: `● <status text> <percent>%`.
  - When a job ends while another page is shown: `✓ <DONE>` or `! <ERROR>`, until ANALYSIS is shown. The app never switches pages on its own.

## 4. Text changes

Messages that pointed at removed buttons now point at the menu: "PENGATURAN > X" → "Alat > Pengaturan > X" (EN "SETTINGS > X" → "Tools > Settings > X"), and "RIWAYAT"/"HISTORY" → "Lihat > Riwayat" / "View > History".

## 5. Theme

`theme.recolor()` skips `tk.Menu` widgets (the native menu keeps system colours).

## 6. Tests

- Pages: `show_page` switches pages and the title; History page actions switch to ANALYSIS and start the job; a running job keeps the page and shows the busy message.
- Job indicator: running text on another page, done/error mark after `finish`, hidden on ANALYSIS.
- Menu: labels follow the language; Run/Open/Pause/Cancel/Copy/Save states follow the job and tab; View items switch pages and tabs; theme and language radio items apply and persist.
- Key bindings: `Ctrl+O` in a Text pane opens the file dialog once and does not insert a line.
- Existing History tests move from `HistoryDialog` to the History page.

## 7. Documentation

README (main window table), user guide (menus, pages, shortcuts), architecture (`menus.py`, pages, indicator), CHANGELOG.
