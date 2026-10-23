# Stock price window: design

Date: 2026-10-23 · Status: implemented (built at the user's request; details decided during implementation) · Sub-project C of the 1.2.0 plan

## Goal

Click a stock (on the Dashboard or in the Collection) to see its current price and chart, with the price levels the videos mentioned drawn on the chart, and how the price moved since each video.

## Decisions

| Question | Decision |
|---|---|
| Data source | **Yahoo Finance chart endpoint** (`query1.finance.yahoo.com/v8/finance/chart/<SYMBOL>`), through `urllib` (no new dependency, no API key). Unofficial, and IDX prices are delayed about 15 minutes; the window says so. Checked on 2026-10-23: `TLKM.JK` returns price, previous close, high/low, volume, name, 5-minute intraday and daily history; an unknown symbol returns 404 "No data found" |
| Symbol | Ticker + `.JK` (IDX). A ticker that already contains a dot is used as is. The window has a symbol field to correct a misheard ticker |
| "Live" | Polling: refresh every 60 s while the window is open and the IDX is in session (Mon–Fri 09:00–16:15 WIB); a refresh button otherwise |
| Where | Clicking the ticker on a Dashboard stock card; a **[ HARGA SAHAM ]** / **[ STOCK PRICE ]** button on the Collection's stock view |
| Windows | A small `Toplevel` per symbol; opening the same symbol again raises the existing window and updates its context. Several can be open |
| Network | Only when a price window is open. Nothing is fetched otherwise |

## 1. `market.py` (no Tk)

- `symbol_for(ticker)` → `TLKM.JK`.
- `fetch_chart(symbol, range, interval)` → raw JSON; raises `MarketError(kind, detail)` with `kind` = `not_found` (HTTP 404 or `chart.error`), `network` (URL/timeout errors) or `bad_data` (unexpected JSON).
- `parse_chart(data)` → `{symbol, name, currency, price, prev_close, change, change_pct, high, low, volume, time, points}`; `points` = `(datetime WIB, close, high, low)` with empty bars (lunch break) dropped. `prev_close` uses `previousClose`, else `chartPreviousClose` (only meaningful for the 1-day range).
- `RANGES`: `1D` (1d, 5m) · `5D` (5d, 15m) · `1M` (1mo, 1d) · `3M` (3mo, 1d) · `1Y` (1y, 1d).
- `market_open(now)` → IDX session check (weekday, 09:00–16:15 WIB).
- `since(points, video_date, prices)` → from daily points: close on the first trading day on/after the video date, latest close, change %, highest high and lowest low after that day, `target_hit` / `stop_hit` (None when the level was not stated), distance to target in %. None when the video date is after the data.

## 2. The window (`stockview.py`)

```
SIMBOL> [TLKM.JK ] [ CARI ]   [1H] [5H] [1B] [3B] [1T]          [ MUAT ULANG ]
TLKM.JK  Telkom Indonesia (Persero) Tbk.
2.240   +40 (+1,82%)        tinggi 2.250 · rendah 2.160 · volume 238,9 jt
update 23/10 15:14 WIB · tertunda ±15 menit (Yahoo Finance) · bursa buka, otomatis tiap 60 detik
┌ chart ─────────────────────────────────────────────────────────────┐
│ price line (green if up over the range, red if down), 4 grid lines │
│ dashed lines: buy price (amber), target (green), loss limit (red)  │
└────────────────────────────────────────────────────────────────────┘
SEJAK VIDEO
TANGGAL  VIDEO           SIKAP  SAAT VIDEO → SEKARANG   TARGET            BATAS RUGI
22/10    14 Saham …      BELI   2.180 → 2.240 (+2,8%)   2.200 tersentuh   1.985 aman
! Harga dari Yahoo Finance, tidak resmi dan tertunda. Bukan nasihat investasi.
```

- Context passed in: the levels to draw (`entry`, `target`, `stop_loss`; from the stock card, or the medians in the Collection) and the videos (`date`, `title`, `stance`, `prices`).
- Level lines are drawn when they fall within 30% of the chart's price range; others are listed under the chart as off-chart.
- The chart uses the bar index on the x axis (no gaps for nights and lunch), with the first and last time as labels.
- "Since video" needs daily data back to the oldest video: fetched once per symbol with range `1y`. Rows whose date is an analysis date (no upload date) are marked `*`. Without any video date the section says the date is unknown.
- Fetching runs in a worker thread; the window polls for the result. Errors: not found ("<symbol> not found; the ticker may be misheard, correct it in SYMBOL"), network (with the message and a retry button). The last good data stays on screen when a refresh fails.

## 3. Hooks

- `Pipeline.source()` adds `video_date` (from the cache entry or yt-dlp) to the source dict, so the Dashboard knows the video date.
- `DashboardView.on_ticker`: optional callback; when set, the ticker on each stock card is underlined and clickable. `App` sets it to open the window with that stock's levels and the current video.
- Collection stock view: a **[ HARGA SAHAM ]** button under the header, with the median levels and every video's date, stance and prices.
- `App.open_stock(ticker, context)` keeps one window per symbol.

## 4. Text and docs

- README: the "does not fetch market data" statements now say prices are fetched only when a price window is opened, from Yahoo Finance, delayed.
- User guide section for the price window; architecture entry for `market.py` / `stockview.py`; CHANGELOG.

## 5. Tests

- `tests/test_market.py`: `symbol_for`, `parse_chart` on a captured-shape fixture (nulls dropped, change computed), `fetch_chart` error mapping (404, `chart.error`, network) with a fake `urlopen`, `market_open`, `since` (start price, hit/miss, missing levels, date after data).
- GUI: the window renders price and change from a fake fetch; "since video" shows a hit target; not-found shows the message; opening the same symbol twice reuses the window; clicking a Dashboard ticker opens it.
