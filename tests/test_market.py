"""Yahoo Finance chart parsing and price-since-video calculations in market.py (no Tk, no network)."""
import io
import json
import urllib.error
from datetime import datetime

import pytest

import market

T0 = int(datetime(2026, 10, 23, 9, 0, tzinfo=market.WIB).timestamp())


def chart(closes, highs=None, lows=None, step=300, **meta):
    m = {"symbol": "TLKM.JK", "shortName": "Telkom Indonesia", "currency": "IDR", "regularMarketPrice": 2240.0,
         "chartPreviousClose": 2200.0, "regularMarketDayHigh": 2250.0, "regularMarketDayLow": 2160.0,
         "regularMarketVolume": 238905400, "regularMarketTime": T0 + 3600, **meta}
    return {"chart": {"result": [{"meta": m, "timestamp": [T0 + i * step for i in range(len(closes))],
                                  "indicators": {"quote": [{"close": closes, "high": highs or closes,
                                                            "low": lows or closes}]}}], "error": None}}


def daily(*rows):
    """rows: (YYYY-MM-DD, close, high, low)."""
    stamps = [int(datetime.strptime(d, "%Y-%m-%d").replace(hour=9, tzinfo=market.WIB).timestamp()) for d, *_ in rows]
    data = chart([r[1] for r in rows], [r[2] for r in rows], [r[3] for r in rows])
    data["chart"]["result"][0]["timestamp"] = stamps
    return market.parse_chart(data)["points"]


def test_symbol_for_adds_the_idx_suffix_once():
    assert market.symbol_for(" tlkm ") == "TLKM.JK"
    assert market.symbol_for("AAPL.US") == "AAPL.US"


def test_parse_chart_reads_quote_and_drops_empty_bars():
    q = market.parse_chart(chart([2200.0, None, 2230.0, 2240.0]))
    assert (q["symbol"], q["name"], q["price"], q["prev_close"]) == ("TLKM.JK", "Telkom Indonesia", 2240.0, 2200.0)
    assert q["change"] == 40 and q["change_pct"] == pytest.approx(40 / 2200 * 100)
    assert [p[1] for p in q["points"]] == [2200.0, 2230.0, 2240.0]
    assert q["points"][0][0].hour == 9 and q["time"].tzinfo is market.WIB


def test_parse_chart_prefers_previous_close_and_survives_missing_price():
    q = market.parse_chart(chart([2100.0, 2150.0], regularMarketPrice=None, previousClose=2000.0))
    assert q["price"] == 2150.0 and q["prev_close"] == 2000.0 and q["change"] == 150.0


def test_parse_chart_rejects_unexpected_shapes():
    with pytest.raises(market.MarketError) as e:
        market.parse_chart({"chart": {"result": []}})
    assert e.value.kind == "bad_data"


class FakeResp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_fetch_chart_maps_errors(monkeypatch):
    def respond(payload):
        monkeypatch.setattr(market.urllib.request, "urlopen", lambda req, timeout=15: FakeResp(json.dumps(payload).encode()))

    respond(chart([1.0]))
    assert market.fetch_chart("TLKM.JK")["chart"]["result"]

    respond({"chart": {"result": None, "error": {"code": "Not Found", "description": "No data found"}}})
    with pytest.raises(market.MarketError) as e:
        market.fetch_chart("XXXX.JK")
    assert e.value.kind == "not_found"

    def http404(req, timeout=15):
        raise urllib.error.HTTPError(req.full_url, 404, "Not Found", {}, io.BytesIO(b"{}"))

    monkeypatch.setattr(market.urllib.request, "urlopen", http404)
    with pytest.raises(market.MarketError) as e:
        market.fetch_chart("XXXX.JK")
    assert e.value.kind == "not_found"

    def offline(req, timeout=15):
        raise urllib.error.URLError("getaddrinfo failed")

    monkeypatch.setattr(market.urllib.request, "urlopen", offline)
    with pytest.raises(market.MarketError) as e:
        market.fetch_chart("TLKM.JK")
    assert e.value.kind == "network" and "getaddrinfo" in e.value.detail


@pytest.mark.parametrize("when, expected", [
    (datetime(2026, 10, 23, 10, 0), True), (datetime(2026, 10, 23, 8, 59), False),
    (datetime(2026, 10, 23, 16, 15), False), (datetime(2026, 10, 24, 10, 0), False),  # Saturday
])
def test_market_open_follows_the_idx_session(when, expected):
    assert market.market_open(when.replace(tzinfo=market.WIB)) is expected


def test_since_video_start_price_hits_and_distance():
    pts = daily(("2026-10-20", 2150, 2160, 2140), ("2026-10-21", 2180, 2190, 2100),
                ("2026-10-22", 2200, 2210, 2170), ("2026-10-23", 2240, 2250, 2160))
    s = market.since(pts, "2026-10-21", {"target": 2200.0, "stop_loss": 1985.0})
    assert (s["start"], s["start_date"], s["now"]) == (2180, "2026-10-21", 2240)
    assert s["change_pct"] == pytest.approx(60 / 2180 * 100)
    assert s["max_high"] == 2250 and s["min_low"] == 2160  # after the video day only
    assert s["target_hit"] is True and s["stop_hit"] is False
    assert s["to_target_pct"] == pytest.approx((2200 - 2240) / 2240 * 100)


def test_since_handles_weekends_missing_levels_and_future_dates():
    pts = daily(("2026-10-23", 2240, 2250, 2160))
    s = market.since(pts, "2026-10-18", {})  # Sunday video -> next trading day
    assert s["start_date"] == "2026-10-23" and s["target_hit"] is None and s["stop_hit"] is None
    assert s["max_high"] is None  # nothing after the start day yet
    assert market.since(pts, "2026-10-30", {}) is None
    assert market.since(pts, "", {}) is None
