"""Harga saham dari Yahoo Finance (endpoint chart). Tidak resmi; harga IDX tertunda sekitar 15 menit. Tanpa Tk.

Hanya dipanggil saat jendela harga dibuka; aplikasi tidak mengambil data pasar di tempat lain.
"""
import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range={range}&interval={interval}"
TRADINGVIEW_URL = "https://www.tradingview.com/chart/?symbol={symbol}"
SUFFIX = ".JK"  # Bursa Efek Indonesia
WIB = timezone(timedelta(hours=7))
RANGES = {"1D": ("1d", "5m"), "5D": ("5d", "15m"), "1M": ("1mo", "1d"), "3M": ("3mo", "1d"), "1Y": ("1y", "1d")}
SESSION = ((9, 0), (16, 15))  # jam bursa (WIB), longgar: termasuk pra-penutupan


class MarketError(Exception):
    """kind: not_found (simbol tidak ada) | network (koneksi) | bad_data (jawaban tak terduga)."""

    def __init__(self, kind, detail=""):
        super().__init__(detail or kind)
        self.kind, self.detail = kind, detail


def symbol_for(ticker):
    t = (ticker or "").strip().upper()
    return t if "." in t else t + SUFFIX


def tradingview_url(symbol):
    """Grafik di TradingView.com: 'TLKM.JK' (atau 'TLKM') -> IDX:TLKM; simbol bursa lain tanpa akhirannya."""
    base, dot, suffix = (symbol or "").strip().upper().partition(".")
    tv = f"IDX:{base}" if not dot or "." + suffix == SUFFIX else base
    return TRADINGVIEW_URL.format(symbol=urllib.parse.quote(tv, safe=""))


def fetch_chart(symbol, rng="1d", interval="5m", timeout=15):
    url = CHART_URL.format(symbol=urllib.parse.quote(symbol), range=rng, interval=interval)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 TickerQuill"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise MarketError("not_found", symbol) from e
        raise MarketError("network", f"HTTP {e.code}") from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise MarketError("network", str(getattr(e, "reason", e))) from e
    except ValueError as e:
        raise MarketError("bad_data", str(e)) from e
    chart = data.get("chart") if isinstance(data, dict) else None
    if not isinstance(chart, dict):
        raise MarketError("bad_data", "no chart")
    if chart.get("error"):
        raise MarketError("not_found", (chart["error"] or {}).get("description") or symbol)
    if not chart.get("result"):
        raise MarketError("not_found", symbol)
    return data


def parse_chart(data):
    try:
        res = data["chart"]["result"][0]
        meta = res["meta"]
        quote = (res.get("indicators") or {}).get("quote") or [{}]
        q = quote[0]
        stamps = res.get("timestamp") or []
        points = []
        for i, ts in enumerate(stamps):
            close = (q.get("close") or [None] * len(stamps))[i]
            if close is None:  # bar kosong (istirahat siang, belum ada transaksi)
                continue
            high = (q.get("high") or [None] * len(stamps))[i]
            low = (q.get("low") or [None] * len(stamps))[i]
            points.append((datetime.fromtimestamp(ts, WIB), float(close), float(high if high is not None else close),
                           float(low if low is not None else close)))
        price = meta.get("regularMarketPrice")
        price = float(price) if price is not None else (points[-1][1] if points else None)
        prev = meta.get("previousClose") or meta.get("chartPreviousClose")
        change = price - prev if price is not None and prev else None
        when = meta.get("regularMarketTime")
        return {"symbol": meta.get("symbol", ""), "name": meta.get("shortName") or meta.get("longName") or "",
                "currency": meta.get("currency") or "", "price": price, "prev_close": prev, "change": change,
                "change_pct": change / prev * 100 if change is not None else None,
                "high": meta.get("regularMarketDayHigh"), "low": meta.get("regularMarketDayLow"),
                "volume": meta.get("regularMarketVolume"),
                "time": datetime.fromtimestamp(when, WIB) if when else (points[-1][0] if points else None),
                "points": points}
    except (KeyError, IndexError, TypeError, ValueError) as e:
        raise MarketError("bad_data", f"{type(e).__name__}: {e}") from e


def market_open(now=None):
    now = (now or datetime.now(WIB)).astimezone(WIB)
    start, end = SESSION
    return now.weekday() < 5 and start <= (now.hour, now.minute) < end


def since(points, video_date, prices):
    """Pergerakan sejak tanggal video dari data harian. None bila tanggalnya sesudah data terakhir."""
    try:
        day = datetime.strptime(video_date, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None
    idx = next((i for i, p in enumerate(points) if p[0].date() >= day), None)
    if idx is None:
        return None
    start_dt, start = points[idx][0], points[idx][1]
    now = points[-1][1]
    after = points[idx + 1:]
    high = max((p[2] for p in after), default=None)
    low = min((p[3] for p in after), default=None)
    target, stop = prices.get("target"), prices.get("stop_loss")
    return {"start": start, "start_date": start_dt.date().isoformat(), "now": now,
            "change_pct": (now - start) / start * 100, "max_high": high, "min_low": low,
            # tersentuh bila harga sesudah hari video, atau harga terakhir, mencapai level itu
            "target_hit": ((high is not None and high >= target) or now >= target) if target else None,
            "stop_hit": ((low is not None and low <= stop) or now <= stop) if stop else None,
            "to_target_pct": (target - now) / now * 100 if target else None}
