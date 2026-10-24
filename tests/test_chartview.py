"""Candle chart process (chartview.py): data for Lightweight Charts, video markers, levels. pywebview is not needed."""
from datetime import datetime

import pytest

from tickerquill import chartview
from tickerquill import market

COLORS = {"BUY": "#00ff00", "WATCH": "#ffb000", "SELL": "#ff0000"}
LABELS = {"BUY": "BELI", "WATCH": "PANTAU", "SELL": "JUAL"}


def daily_bars(*dates):
    return [{"time": d, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1} for d in dates]


def test_video_markers_sit_on_the_first_bar_on_or_after_the_video_date():
    bars = daily_bars("2026-10-20", "2026-10-21", "2026-10-23")
    videos = [{"date": "2026-10-20", "stance": "BUY"}, {"date": "2026-10-22", "stance": "SELL"},  # Thursday holiday
              {"date": "2026-10-22", "stance": "WATCH"}, {"date": "2026-09-01", "stance": "BUY"},  # before the range
              {"date": "2026-11-01", "stance": "BUY"}]  # after the data
    m = chartview.video_markers(bars, videos, COLORS, LABELS)
    assert m == [
        {"time": "2026-10-20", "position": "belowBar", "shape": "arrowUp", "color": "#00ff00", "text": "BELI 20/10"},
        {"time": "2026-10-23", "position": "aboveBar", "shape": "arrowDown", "color": "#ff0000",
         "text": "JUAL 22/10 · PANTAU 22/10"},
    ]


def test_intraday_bars_use_wib_dates_for_markers():
    t = int(datetime(2026, 10, 23, 9, 0, tzinfo=market.WIB).timestamp()) + 7 * 3600
    bars = [{"time": t, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1}]
    assert chartview.bar_date(bars[0]) == "2026-10-23"
    [m] = chartview.video_markers(bars, [{"date": "2026-10-23", "stance": "WATCH"}], COLORS, LABELS)
    assert m["time"] == t and m["shape"] == "circle"


@pytest.fixture
def ctx():
    return {"symbol": "TLKM.JK", "ui": "ID", "palette": {"BG": "#000000"}, "stance_colors": COLORS,
            "stance_labels": LABELS, "levels": {"entry": 2080.0, "target": 2150.0, "stop_loss": None},
            "videos": [{"date": "2026-10-21", "stance": "BUY"}]}


def test_init_lists_stated_levels_only(ctx):
    info = chartview.Api(ctx).init()
    assert info["levels"] == [{"price": 2080.0, "role": "AMBER", "label": "beli"},
                              {"price": 2150.0, "role": "GOOD", "label": "target"}]
    assert info["range"] == "3M" and info["ranges"] == ["1D", "5D", "1M", "3M", "1Y"]
    assert info["precision"] == 0  # IDX prices are whole rupiah
    assert chartview.Api({**ctx, "symbol": "AAPL.US"}).init()["precision"] == 2


def test_bars_returns_candles_markers_and_header(ctx, monkeypatch):
    days = [int(datetime(2026, 10, d, 9, tzinfo=market.WIB).timestamp()) for d in (20, 21, 23)]

    def fetch(symbol, rng="1d", interval="5m", timeout=15):
        q = {"close": [2060.0, 2180.0, 2240.0], "high": [2070.0, 2190.0, 2250.0], "low": [2040.0, 2100.0, 2160.0],
             "open": [2050.0, 2070.0, 2200.0], "volume": [10, 20, 30]}
        return {"chart": {"result": [{"meta": {"shortName": "Telkom", "regularMarketPrice": 2240.0, "previousClose": 2200.0,
                                               "regularMarketTime": days[-1]},
                                      "timestamp": days, "indicators": {"quote": [q]}}]}}

    monkeypatch.setattr(market, "fetch_chart", fetch)
    monkeypatch.setattr(market, "market_open", lambda now=None: False)
    d = chartview.Api(ctx).bars("3M")
    assert [b["time"] for b in d["bars"]] == ["2026-10-20", "2026-10-21", "2026-10-23"]
    assert d["bars"][2] == {"time": "2026-10-23", "open": 2200.0, "high": 2250.0, "low": 2160.0, "close": 2240.0, "volume": 30}
    assert d["markers"][0]["time"] == "2026-10-21" and d["markers"][0]["text"] == "BELI 21/10"
    assert d["quote"] == {"name": "Telkom", "price": "2.240", "change": "+40 (+1,82%)", "up": True}
    assert d["open"] is False and "bursa tutup" in d["status"]


def test_bars_reports_errors_in_the_app_language(ctx, monkeypatch):
    def missing(symbol, rng="1d", interval="5m", timeout=15):
        raise market.MarketError("not_found", symbol)

    monkeypatch.setattr(market, "fetch_chart", missing)
    assert chartview.Api(ctx).bars("1D") == {"error": chartview.t("ID", "not_found", s="TLKM.JK")}


def test_page_embeds_lightweight_charts_with_its_license_header():
    html = chartview.page_html()
    assert "/*LIGHTWEIGHT_CHARTS*/" not in html
    assert "TradingView Lightweight Charts™ v5.2.1" in html and "createSeriesMarkers" in html
    assert (chartview.ASSETS / "lightweight-charts" / "NOTICE").exists()
    assert (chartview.ASSETS / "lightweight-charts" / "LICENSE").exists()
