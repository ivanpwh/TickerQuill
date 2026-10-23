"""Settings helpers, history cache helpers and the Colab client's error paths (needs tkinter to import app)."""
import json

import pytest

pytest.importorskip("tkinter")
import app  # noqa: E402
import remote  # noqa: E402


@pytest.fixture
def files(tmp_path, monkeypatch):
    monkeypatch.setattr(app, "ENV_FILE", tmp_path / ".env")
    monkeypatch.setattr(app, "SETTINGS_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(app, "CACHE", tmp_path / "cache")
    (tmp_path / "cache").mkdir()
    for key in ("NINEROUTER_API_KEY", "APP_LANG", "WHISPER_ENGINE", "COLAB_WHISPER_URL", "COLAB_WHISPER_TOKEN"):
        monkeypatch.delenv(key, raising=False)
    return tmp_path


def test_write_env_updates_appends_and_keeps_everything_else(files):
    app.ENV_FILE.write_text("# comment\nNINEROUTER_API_KEY=old\n\nFOO=bar\n# APP_LANG=ID\n", encoding="utf-8")
    app.write_env({"NINEROUTER_API_KEY": "new key #1", "APP_LANG": "EN", "WHISPER_ENGINE": ""})
    lines = app.ENV_FILE.read_text(encoding="utf-8").splitlines()
    assert lines[:4] == ["# comment", 'NINEROUTER_API_KEY="new key #1"', "", "FOO=bar"]
    assert "# APP_LANG=ID" in lines              # commented line untouched
    assert "APP_LANG=EN" in lines and "WHISPER_ENGINE=" in lines
    assert app.setting("NINEROUTER_API_KEY") == "new key #1"
    assert app.setting("WHISPER_ENGINE", "Local") == "Local"   # empty value means "use the default"


def test_write_env_creates_the_file(files):
    app.write_env({"APP_LANG": "EN"})
    assert app.ENV_FILE.read_text(encoding="utf-8") == "APP_LANG=EN\n"


def test_setting_precedence_env_file_then_os_then_default(files, monkeypatch):
    assert app.setting("APP_LANG", "ID") == "ID"
    monkeypatch.setenv("APP_LANG", "EN")
    assert app.setting("APP_LANG", "ID") == "EN"
    app.ENV_FILE.write_text("APP_LANG='ID'\n", encoding="utf-8")
    assert app.setting("APP_LANG", "xx") == "ID"


def test_settings_json_is_merged_not_overwritten(files):
    app.save_settings(model="m1", theme="dark")
    app.save_settings(theme="light")
    assert json.loads(app.SETTINGS_FILE.read_text(encoding="utf-8")) == {"model": "m1", "theme": "light"}
    assert app.load_saved_model() == "m1"


def test_corrupt_settings_json_falls_back_to_defaults(files):
    app.SETTINGS_FILE.write_text("{not json", encoding="utf-8")
    assert app.load_settings() == {}
    assert app.load_saved_model() == app.DEFAULT_MODEL  # empty unless NINEROUTER_MODEL is set


def test_fresh_install_has_no_llm_model(files, monkeypatch):
    monkeypatch.setattr(app, "DEFAULT_MODEL", "")
    assert app.FALLBACK_MODEL == "" and app.load_saved_model() == ""


def test_analysis_requires_api_key_and_model(files, monkeypatch):
    import queue

    monkeypatch.setattr(app, "DEFAULT_MODEL", "")
    pipeline = app.Pipeline("u", "tiny", "Indonesia", "EN", queue.Queue(), model="")
    with pytest.raises(RuntimeError, match="NINEROUTER_API_KEY"):
        pipeline.analyze("title", "text")
    app.write_env({"NINEROUTER_API_KEY": "k"})
    with pytest.raises(RuntimeError, match="No LLM model"):
        pipeline.analyze("title", "text")


def test_llm_ready_needs_both_key_and_model(files):
    from types import SimpleNamespace

    assert not app.App.llm_ready(SimpleNamespace(model="m"))
    app.write_env({"NINEROUTER_API_KEY": "k"})
    assert app.App.llm_ready(SimpleNamespace(model="m"))
    assert not app.App.llm_ready(SimpleNamespace(model=""))


def test_colab_conf_prefers_settings_json(files):
    app.ENV_FILE.write_text("COLAB_WHISPER_URL=http://env\nCOLAB_WHISPER_TOKEN=envtok\n", encoding="utf-8")
    assert app.colab_conf() == ("http://env", "envtok")
    app.save_settings(colab_url="http://json", colab_token="jsontok")
    assert app.colab_conf() == ("http://json", "jsontok")


@pytest.mark.parametrize("url, vid", [
    ("https://www.youtube.com/watch?v=_4TXZNx3veY&t=5s", "_4TXZNx3veY"),
    ("https://youtu.be/_4TXZNx3veY", "_4TXZNx3veY"),
    ("https://www.youtube.com/shorts/_4TXZNx3veY", "_4TXZNx3veY"),
    ("https://example.com/video", None), ("", None), (None, None),
])
def test_video_id(url, vid):
    assert app.video_id(url) == vid


def test_cache_state_and_history(files):
    done, partial = app.cache_paths("abcdefghijk", "id")
    assert app.cache_state("abcdefghijk", "id") is None
    app.write_json_atomic(partial, {"title": "T", "lines": ["[00:00:01] a"], "done_until": 50, "duration": 200,
                                    "whisper_model": "small"})
    state = app.cache_state("abcdefghijk", "id")
    assert state[0] == "partial" and state[2] == 25
    app.write_json_atomic(done, {"title": "T", "transcript": "[00:00:01] a", "whisper_model": "small"})
    assert app.cache_state("abcdefghijk", "id")[0] == "done"
    items = app.list_history()
    assert {(i["vid"], i["partial"]) for i in items} == {("abcdefghijk", True), ("abcdefghijk", False)}


def test_remote_errors_are_wrapped():
    with pytest.raises(remote.RemoteError):
        remote.health("ftp://nope", "t")
    with pytest.raises(remote.RemoteError):
        remote.health("http://127.0.0.1:1", "t")   # nothing listens on port 1


def test_opened_transcript_file_appears_in_history(files):
    import queue

    src = files / "my notes.txt"
    src.write_text("[00:00:01] BBCA bagus\n[00:00:02] BBCA bagus\n[00:00:03] MEDC turun\n", encoding="utf-8")
    pipeline = app.Pipeline("", "tiny", "Indonesia", "EN", queue.Queue(), transcript_path=str(src))
    title, text = pipeline.read_transcript_file()
    assert title == "my notes" and "MEDC" in text
    pipeline.read_transcript_file()  # same content again must not create a second entry
    items = app.list_history()
    assert len(items) == 1
    entry = items[0]
    assert entry["is_file"] and entry["url"] == "" and not entry["partial"] and entry["pct"] == 100
    assert entry["meta"]["title"] == "my notes" and entry["meta"]["transcript"] == text


def test_preloaded_history_entry_skips_download_and_whisper(files):
    import queue

    out = queue.Queue()
    pipeline = app.Pipeline("", "tiny", "Indonesia", "EN", out, preloaded=("T", "some text"))
    pipeline.run()  # no API key in the test environment: analysis fails, but the transcript is delivered first
    events = []
    while not out.empty():
        events.append(out.get())
    assert ("transcript", ("T", "some text", {"file": "T"})) in events
    assert events[-1][0] == "error" and "NINEROUTER_API_KEY" in events[-1][1]
