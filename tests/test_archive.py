"""Archive records and cross-video calculations in archive.py (no Tk, no network)."""
import json
from datetime import datetime

import pytest

import archive


def raw(*stocks, summary="ringkasan", sentiment="BULLISH"):
    return json.dumps({"summary": summary, "market_sentiment": sentiment, "stocks": list(stocks)})


def stock(ticker, stance="WATCH", **levels):
    return {"ticker": ticker, "stance": stance, "levels": levels, "speaker_confidence": "MEDIUM"}


def meta(vid, date="", title=None, channel="Kanal"):
    return {"title": title or f"Video {vid}", "url": f"https://youtu.be/{vid}", "vid": vid, "lang": "Indonesia",
            "video_date": date, "channel": channel}


def rec(vid, date, *stocks, at="2026-10-23 10:00", **kw):
    r = archive.build_record(raw(*stocks), " ".join(s["ticker"] for s in stocks), meta(vid, date, **kw),
                             f"{vid}.id.json", "m", datetime.strptime(at, "%Y-%m-%d %H:%M"))
    return r


@pytest.fixture
def tlkm():
    """Five videos about TLKM, like the real history: WATCH x4, BUY x1, levels that move."""
    return [
        rec("v1", "2026-10-21", stock("TLKM")),
        rec("v2", "2026-10-21", stock("TLKM", entry="2100", resistance="2.110")),
        rec("v3", "2026-10-22", stock("TLKM", entry="2.060-2.080", target="2.100", resistance="2.100")),
        rec("v4", "2026-10-22", stock("TLKM", "BUY", target="2.200, 2.340", stop_loss="1.985", support="1.985")),
        rec("v5", "2026-10-23", stock("TLKM", resistance="2.290")),
    ]


def test_build_record_keeps_metadata_levels_and_numbers():
    r = rec("abcdefghijk", "2026-10-21", stock("TLKM", "BUY", entry="2.100", target="2.200, 2.340"),
            at="2026-10-23 10:01")
    assert r["id"] == "20261023-100100-abcdefghijk" and r["entry"] == "abcdefghijk.id.json"
    assert (r["source"], r["video_date"], r["channel"], r["llm_model"]) == ("youtube", "2026-10-21", "Kanal", "m")
    s = r["stocks"][0]
    assert s["levels"] == {"entry": "2.100", "target": "2.200, 2.340"}
    assert s["prices"]["entry"] == 2100 and s["prices"]["target"] == 2200 and s["prices"]["stop_loss"] is None
    assert r["tone"] == 1.0 and r["sentiment"] == "BULLISH" and r["summary"] == "ringkasan"


def test_build_record_rejects_unreadable_replies():
    with pytest.raises(ValueError):
        archive.build_record("not json", "", meta("x"), "x.id.json", "m", datetime.now())


def test_file_records_have_no_video_date_and_use_the_analysis_date():
    r = archive.build_record(raw(stock("BBCA")), "BBCA", {"title": "notes", "vid": "file-abc", "lang": "file"},
                             "file-abc.file.json", "m", datetime(2026, 10, 20, 9, 0))
    assert r["source"] == "file" and r["url"] == "" and archive.date_of(r) == "2026-10-20"
    assert archive.date_is_fallback(r)


def test_save_load_latest_and_delete(tmp_path):
    old = rec("v1", "2026-10-21", stock("TLKM"), at="2026-10-21 10:00")
    new = rec("v1", "2026-10-21", stock("TLKM", "BUY"), at="2026-10-22 10:00")
    other = rec("v2", "2026-10-22", stock("BBCA"))
    for r in (old, new, other):
        archive.save_record(tmp_path, r)
    (tmp_path / "broken.json").write_text("{", encoding="utf-8")
    records = archive.load_records(tmp_path)
    assert len(records) == 3
    latest = archive.latest_per_video(records)
    assert [r["vid"] for r in latest] == ["v2", "v1"] and latest[1]["stocks"][0]["stance"] == "BUY"
    assert archive.delete_video(tmp_path, "v1") == 2
    assert [r["vid"] for r in archive.load_records(tmp_path)] == ["v2"]


def test_import_runs_once_and_deleted_videos_stay_deleted(tmp_path):
    entry = tmp_path / "cache" / "v1.id.json"
    entry.parent.mkdir()
    entry.write_text("{}", encoding="utf-8")
    good = {**meta("v1", "2026-10-21"), "analysis": raw(stock("TLKM")), "transcript": "TLKM", "analysis_model": "m"}
    bad = {**meta("v2"), "analysis": "garbage", "transcript": ""}
    folder = tmp_path / "analyses"
    assert archive.import_entries(folder, [(entry, good), (entry, bad)]) == 1
    [r] = archive.load_records(folder)
    assert r["vid"] == "v1" and r["llm_model"] == "m"
    archive.delete_video(folder, "v1")
    assert archive.import_entries(folder, [(entry, good)]) == 0
    assert archive.load_records(folder) == []


def test_video_dates_can_be_filled_in_later(tmp_path):
    r = rec("v1", "", stock("TLKM"))
    archive.save_record(tmp_path, r)
    assert archive.missing_dates([r]) == {"v1": "https://youtu.be/v1"}
    assert archive.upload_date({"upload_date": "20261021"}) == "2026-10-21"
    assert archive.upload_date({}) == ""
    archive.set_video_meta(tmp_path, "v1", "2026-10-21", "Kanal Baru")
    [r] = archive.load_records(tmp_path)
    assert (r["video_date"], r["channel"]) == ("2026-10-21", "Kanal Baru") and archive.missing_dates([r]) == {}


def test_group_by_date_uses_video_date_newest_first(tlkm):
    groups = archive.group_by_date(tlkm)
    assert list(groups) == ["2026-10-23", "2026-10-22", "2026-10-21"]
    assert [r["vid"] for r in groups["2026-10-21"]] == ["v1", "v2"]


def test_consensus_and_agreement(tlkm):
    c = archive.consensus(archive.views(tlkm, "TLKM"))
    assert c == {"counts": {"BUY": 1, "WATCH": 4}, "dominant": "WATCH", "top": ["WATCH"], "agreement": 80}
    assert archive.consensus([])["dominant"] is None
    tie = archive.consensus([{"stance": "WATCH"}, {"stance": "BUY"}])
    assert tie["top"] == ["BUY", "WATCH"] and tie["agreement"] == 50  # a tie is not a majority


def test_conflict_needs_buy_and_sell_or_avoid(tlkm):
    vs = archive.views(tlkm, "TLKM")
    assert not archive.conflict(vs)
    flip = [rec("a", "2026-10-21", stock("SQMI", "SELL")), rec("b", "2026-10-23", stock("SQMI", "BUY"))]
    assert archive.conflict(archive.views(flip, "SQMI"))


def test_price_zone_medians_repeats_and_combined_reward_risk(tlkm):
    z = archive.price_zone(archive.views(tlkm, "TLKM"))
    assert z["levels"]["entry"] == {"min": 2060, "max": 2100, "median": 2080, "n": 2}
    assert z["levels"]["target"] == {"min": 2100, "max": 2200, "median": 2150, "n": 2}
    assert z["levels"]["stop_loss"]["n"] == 1
    assert z["repeated"] == [(2100, 2)]  # v2 entry and v3 target+resistance: one count per video
    assert z["rr"]["ratio"] == pytest.approx((2150 - 2080) / (2080 - 1985))


def test_changes_report_stance_and_target_moves(tlkm):
    ch = archive.changes(archive.views(tlkm, "TLKM"))
    stance = [(c["from"], c["to"], c["date"]) for c in ch if c["kind"] == "stance"]
    assert stance == [("WATCH", "BUY", "2026-10-22"), ("BUY", "WATCH", "2026-10-23")]
    assert {"kind": "target", "from": 2100, "to": 2200}.items() <= next(c for c in ch if c["kind"] == "target").items()


def test_reliability_counts_doubtful_and_averages_confidence():
    vs = [{"confidence": "HIGH", "doubtful": False}, {"confidence": "LOW", "doubtful": True},
          {"confidence": "", "doubtful": False}]
    assert archive.reliability(vs) == {"doubtful": 1, "n": 3, "confidence": "MEDIUM", "rated": 2}


def test_trending_and_tone_by_date(tlkm):
    records = tlkm + [rec("v6", "2026-10-23", stock("BBCA", "SELL"))]
    top = archive.trending(records)
    assert top[0]["ticker"] == "TLKM" and top[0]["videos"] == 5 and top[0]["dominant"] == "WATCH"
    assert top[1]["ticker"] == "BBCA" and top[1]["videos"] == 1
    tones = dict((d, (t, n)) for d, t, n in archive.tone_by_date(records))
    assert tones["2026-10-23"] == (pytest.approx((0.25 - 1.0) / 2), 2)


def test_ai_cache_key_changes_when_a_video_is_added(tmp_path, tlkm):
    a = archive.ai_path(tmp_path, "ticker", "TLKM", tlkm[:4], "ID")
    b = archive.ai_path(tmp_path, "ticker", "TLKM", tlkm, "ID")
    assert a != b and a.parent == tmp_path / "ai"
    assert archive.ai_path(tmp_path, "ticker", "TLKM", list(reversed(tlkm)), "ID") == b
    archive.write_json(a, {"text": "lama", "created": "2026-10-22 10:00"})
    path, data = archive.latest_ai(tmp_path, "ticker", "TLKM")
    assert path == a and data["text"] == "lama"
