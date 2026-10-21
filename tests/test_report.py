"""Calculations and parsing in report.py (no Tk, no network)."""
import json

import pytest

import report


def stock(ticker, stance="BUY", **kw):
    return {"ticker": ticker, "stance": stance, **kw}


@pytest.mark.parametrize("text, expected", [
    ("1.250", 1250.0), ("9.000", 9000.0), ("1,5", 1.5), ("Rp 1.200 - 1.250", 1200.0), ("12", 12.0),
    ("", None), (None, None), ("tidak disebut", None), ("1.2.3.4", None),
])
def test_parse_price(text, expected):
    assert report.parse_price(text) == expected


def test_compute_example_from_methodology():
    raw = {"stocks": [
        stock("BBCA", reason="stable profit", levels={"entry": "9.000", "target": "10.000", "stop_loss": "8.500"}),
        stock("MEDC", "SELL", doubtful=True, levels={})]}
    d = report.compute(raw, "BBCA BBCA BBCA MEDC", "m")
    bbca, medc = d["stocks"]  # sorted by mentions
    assert (bbca["ticker"], bbca["mentions"], medc["mentions"]) == ("BBCA", 3, 1)
    assert bbca["share"] == pytest.approx(75.0) and medc["share"] == pytest.approx(25.0)
    assert bbca["completeness"] == 100 and medc["completeness"] == 0
    assert bbca["rr"]["ratio"] == pytest.approx(2.0)
    assert bbca["rr"]["gain"] == pytest.approx(100 / 9) and bbca["rr"]["loss"] == pytest.approx(50 / 9)
    assert medc["rr"] is None
    assert d["tone"] == pytest.approx(0.5)
    assert d["reliability"] == 50 and d["doubtful"] == 1 and d["total_mentions"] == 4


def test_spoken_as_variants_are_counted_as_whole_words():
    raw = {"stocks": [stock("MEDC", spoken_as=["MEDCO"])]}
    d = report.compute(raw, "MEDCO naik, medco bagus, MEDCOX bukan", "m")
    assert d["stocks"][0]["mentions"] == 2


@pytest.mark.parametrize("levels", [
    {"entry": "100", "target": "90", "stop_loss": "80"},   # target below entry
    {"entry": "100", "target": "120", "stop_loss": "110"},  # stop above entry
    {"entry": "100", "target": "120"},                      # missing stop
])
def test_reward_risk_requires_sensible_order(levels):
    d = report.compute({"stocks": [stock("AAA", levels=levels)]}, "AAA", "m")
    assert d["stocks"][0]["rr"] is None


@pytest.mark.parametrize("tone, key", [
    (0.5, "tone_vpos"), (0.15, "tone_pos"), (0.1, "tone_neu"), (-0.1, "tone_neu"), (-0.15, "tone_neg"),
    (-0.5, "tone_vneg"),
])
def test_tone_labels(tone, key):
    assert report.tone_key(tone) == key


def test_unknown_values_are_normalised():
    d = report.compute({"stocks": [stock("aaa", "STRONG BUY", speaker_confidence="certain"),
                                   {"stance": "BUY"}, "junk"]}, "AAA", "m")
    assert [s["ticker"] for s in d["stocks"]] == ["AAA"]
    assert d["stocks"][0]["stance"] == "WATCH" and d["stocks"][0]["confidence"] == ""


def test_no_stocks_is_handled():
    d = report.compute({"stocks": []}, "nothing", "m")
    assert d["tone"] == 0.0 and d["reliability"] is None
    assert any(kind == "para" for kind, _ in report.blocks(d, "EN"))


def test_parse_report_tolerates_wrappers_and_trailing_commas():
    payload = '<think>hmm</think>\n```json\n{"summary": "ok", "stocks": [],}\n```'
    obj, truncated = report.parse_report(payload)
    assert obj["summary"] == "ok" and truncated is False


def test_parse_report_repairs_truncated_reply():
    full = json.dumps({"summary": "s", "stocks": [
        {"ticker": "AAA", "stance": "BUY", "reason": "r1"},
        {"ticker": "BBB", "stance": "SELL", "reason": "a reason that gets cut o"}]})
    obj, truncated = report.parse_report(full[:full.index("gets cut") + 4])
    assert truncated is True
    assert obj["stocks"][0]["ticker"] == "AAA"


def test_parse_report_rejects_non_json():
    with pytest.raises(ValueError):
        report.parse_report("sorry, I cannot help")


def test_tips_follow_the_rules():
    raw = {"stocks": [stock("BBCA", levels={"entry": "100"}, reason="x"), stock("TLKM", doubtful=True)]}
    d = report.compute(raw, "BBCA BBCA BBCA TLKM", "m")
    tips = " ".join(report.advice(d, "EN"))
    assert "no loss limit" in tips          # BUY without stop loss
    assert "TLKM" in tips                   # doubtful stock listed
    assert "FOMO" in tips                   # tone >= 0.5
    assert "licensed investment adviser" in tips
    assert "FOMO" not in " ".join(report.advice({**d, "tone": 0.0}, "EN"))


def test_blocks_and_text_export_contain_the_stocks():
    d = report.compute({"stocks": [stock("BBCA")]}, "BBCA", "m")
    for ui in ("ID", "EN"):
        blocks = report.blocks(d, ui)
        assert {"title", "gauge", "stock"} <= {kind for kind, _ in blocks}
        assert "BBCA" in report.blocks_to_text(blocks)
        assert "BBCA" in report.report_markdown(d, ui)
