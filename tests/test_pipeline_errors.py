"""Error di langkah 2 (transkripsi) dan 3 (analisis): coba ulang otomatis untuk gangguan sementara, pesan menyebut langkah."""
import queue

import pytest

pytest.importorskip("tkinter")
import httpx2 as httpx  # noqa: E402
import openai  # noqa: E402
import app  # noqa: E402
import remote  # noqa: E402


@pytest.fixture
def no_wait(monkeypatch, tmp_path):
    monkeypatch.setattr(app, "RETRY_WAITS", (0, 0))
    monkeypatch.setattr(app, "TXT_DIR", tmp_path / "transcripts")
    monkeypatch.setattr(app, "CACHE", tmp_path / "cache")
    (tmp_path / "cache").mkdir()
    return tmp_path


def drain(q):
    events = []
    while not q.empty():
        events.append(q.get())
    return events


def upstream_lost():
    return openai.APIError("upstream connection lost", request=httpx.Request("POST", "https://router.test/v1"),
                           body=None)


def unauthorized():
    req = httpx.Request("POST", "https://router.test/v1")
    return openai.AuthenticationError("invalid key", response=httpx.Response(401, request=req), body=None)


class FakeResp:
    def __init__(self, status, lines=()):
        self.status, self._lines = status, list(lines)

    def read(self):
        return b"".join(self._lines)

    def __iter__(self):
        return iter(self._lines)


class FakeConn:
    def __init__(self, resp):
        self.resp = resp

    def putrequest(self, *args):
        pass

    def putheader(self, *args):
        pass

    def endheaders(self):
        pass

    def send(self, data):
        pass

    def getresponse(self):
        return self.resp

    def close(self):
        pass


def colab_events(tmp_path, monkeypatch, resp):
    audio = tmp_path / "a.ogg"
    audio.write_bytes(b"x")
    monkeypatch.setattr(remote, "_connect", lambda base, timeout=60: (FakeConn(resp), ""))
    return list(remote.events("http://colab.test", "token", audio, "large-v3", "id"))


def test_remote_503_and_dropped_stream_are_transient(tmp_path, monkeypatch):
    with pytest.raises(remote.RemoteError) as err:
        colab_events(tmp_path, monkeypatch, FakeResp(503, [b"upstream down"]))
    assert err.value.transient

    with pytest.raises(remote.RemoteError) as err:
        colab_events(tmp_path, monkeypatch, FakeResp(200, [b'{"type":"loading"}\n']))  # tanpa "done"
    assert err.value.transient


def test_remote_auth_and_server_errors_are_not_transient(tmp_path, monkeypatch):
    with pytest.raises(remote.RemoteError, match="token salah") as err:
        colab_events(tmp_path, monkeypatch, FakeResp(401, [b'{"detail":"token salah"}']))
    assert not err.value.transient

    with pytest.raises(remote.RemoteError, match="CUDA out of memory") as err:
        colab_events(tmp_path, monkeypatch, FakeResp(200, [b'{"type":"error","message":"CUDA out of memory"}\n']))
    assert not err.value.transient


def test_colab_drop_is_retried_from_the_last_checkpoint(no_wait, monkeypatch):
    calls = []

    def fake_colab(self, audio, upload, whisper_name, start):
        calls.append(start)

        def segments():
            if len(calls) == 1:
                yield remote.Segment(0.0, 5.0, "satu")
                yield remote.Segment(5.0, 10.0, "dua")
                raise app.StepError(2, "Koneksi ke Colab terputus", transient=True)
            yield remote.Segment(10.0, 15.0, "tiga")

        return segments(), 15.0, "COLAB CUDA"

    monkeypatch.setattr(app.Pipeline, "colab_segments", fake_colab)
    out = queue.Queue()
    pipeline = app.Pipeline("", "tiny", "Indonesia", "EN", out)
    done, partial = app.cache_paths("abcdefghijk", "id")
    _, _, text = pipeline.transcribe(no_wait / "a.ogg", no_wait / "up.ogg", "T", "abcdefghijk", done, partial)

    assert calls == [0.0, 10.0]  # percobaan kedua mulai dari titik checkpoint, bukan dari awal
    assert "satu" in text and "dua" in text and "tiga" in text
    assert done.exists() and not partial.exists()
    assert any(kind == "status" and p[0] == "s_retry_2" for kind, p in drain(out))


def test_colab_drop_that_keeps_failing_stops_after_three_tries(no_wait, monkeypatch):
    calls = []

    def fake_colab(self, audio, upload, whisper_name, start):
        calls.append(start)
        raise app.StepError(2, "Koneksi ke Colab terputus", transient=True)

    monkeypatch.setattr(app.Pipeline, "colab_segments", fake_colab)
    pipeline = app.Pipeline("", "tiny", "Indonesia", "EN", queue.Queue())
    done, partial = app.cache_paths("abcdefghijk", "id")
    with pytest.raises(app.StepError) as err:
        pipeline.transcribe(no_wait / "a.ogg", no_wait / "up.ogg", "T", "abcdefghijk", done, partial)
    assert len(calls) == app.TRIES and err.value.tries == app.TRIES


def test_colab_auth_error_is_not_retried_and_says_which_step(no_wait, monkeypatch):
    calls = []

    def fake_colab(self, audio, upload, whisper_name, start):
        calls.append(start)
        raise app.StepError(2, "Server Colab menjawab 401: token salah", transient=False)

    monkeypatch.setattr(app.Pipeline, "colab_segments", fake_colab)
    out = queue.Queue()
    pipeline = app.Pipeline("", "tiny", "Indonesia", "EN", out)
    done, partial = app.cache_paths("abcdefghijk", "id")
    with pytest.raises(app.StepError) as err:
        pipeline.transcribe(no_wait / "a.ogg", no_wait / "up.ogg", "T", "abcdefghijk", done, partial)
    assert len(calls) == 1 and err.value.tries == 1

    msg = pipeline.failure(err.value.step, err.value.detail, err.value.tries)
    assert msg.startswith("Step 2/3 failed: Server Colab menjawab 401: token salah")
    assert "[ ANALYZE ]" in msg and "Tried" not in msg


def test_step_2_failure_in_run_is_tagged_with_saved_checkpoint_hint(no_wait, monkeypatch):
    def fake_get_transcript(self):
        self.status("s_load", 0)
        self.partial_path = app.cache_paths("abcdefghijk", "id")[1]
        app.write_json_atomic(self.partial_path, {"title": "T", "lines": ["[00:00:01] a"], "done_until": 5,
                                                  "duration": 10, "whisper_model": "tiny"})
        raise RuntimeError("CUDA out of memory")

    monkeypatch.setattr(app.Pipeline, "get_transcript", fake_get_transcript)
    out = queue.Queue()
    app.Pipeline("", "tiny", "Indonesia", "EN", out).run()
    kind, msg = drain(out)[-1]
    assert kind == "error"
    assert msg.startswith("Step 2/3 failed: RuntimeError: CUDA out of memory")
    assert "[ RESUME ]" in msg


def test_llm_upstream_drop_is_retried_then_report_is_used(no_wait, monkeypatch):
    monkeypatch.setattr(app, "setting", lambda name, default=None: "k" if name == "NINEROUTER_API_KEY" else default)
    attempts = []

    def fake_request(self, client, messages):
        attempts.append(1)
        if len(attempts) < 3:
            raise upstream_lost()
        return '{"ok": true}', "stop"

    monkeypatch.setattr(app.Pipeline, "request_report", fake_request)
    out = queue.Queue()
    pipeline = app.Pipeline("", "tiny", "Indonesia", "EN", out, model="m")
    pipeline.analyze("T", "text")
    events = drain(out)
    assert len(attempts) == 3
    assert ("report_raw", ('{"ok": true}', "stop")) in events
    assert not any(kind == "error" for kind, _ in events)


def test_llm_failure_after_retries_is_step_3_and_keeps_the_transcript(no_wait, monkeypatch):
    monkeypatch.setattr(app, "setting", lambda name, default=None: "k" if name == "NINEROUTER_API_KEY" else default)

    def always_lost(self, client, messages):
        raise upstream_lost()

    monkeypatch.setattr(app.Pipeline, "request_report", always_lost)
    out = queue.Queue()
    app.Pipeline("", "tiny", "Indonesia", "EN", out, preloaded=("T", "some text"), model="m").run()
    events = drain(out)
    assert ("transcript", ("T", "some text")) in events  # transkrip tetap dikirim sebelum analisis gagal
    kind, msg = events[-1]
    assert kind == "error"
    assert msg.startswith("Step 3/3 failed: APIError: upstream connection lost")
    assert "Tried 3 times" in msg and "[ ANALYZE ]" in msg and "[ REUSE ]" in msg


def test_llm_auth_error_is_not_retried(no_wait, monkeypatch):
    monkeypatch.setattr(app, "setting", lambda name, default=None: "k" if name == "NINEROUTER_API_KEY" else default)
    attempts = []

    def rejected(self, client, messages):
        attempts.append(1)
        raise unauthorized()

    monkeypatch.setattr(app.Pipeline, "request_report", rejected)
    out = queue.Queue()
    app.Pipeline("", "tiny", "Indonesia", "EN", out, preloaded=("T", "text"), model="m").run()
    assert len(attempts) == 1
    kind, msg = drain(out)[-1]
    assert kind == "error" and msg.startswith("Step 3/3 failed: AuthenticationError")
    assert "Tried" not in msg


def test_llm_transient_only_covers_connection_style_errors():
    assert app.llm_transient(upstream_lost())
    assert app.llm_transient(openai.APIConnectionError(message="reset", request=httpx.Request("POST", "http://x")))
    assert not app.llm_transient(unauthorized())
    assert not app.llm_transient(ValueError("bad"))


VID = "abcdefghijk"
URL = f"https://www.youtube.com/watch?v={VID}"


def write_transcript_entry(extra=None):
    done, partial = app.cache_paths(VID, "id")
    entry = {"title": "T", "url": URL, "vid": VID, "lang": "Indonesia", "whisper_model": "tiny", "duration": 10,
             "created": "2026-10-21 12:03", "transcript": "[00:00:01] BBCA naik"}
    app.write_json_atomic(done, {**entry, **(extra or {})})
    return done, partial


def write_checkpoint(partial):
    app.write_json_atomic(partial, {"title": "Video sebagian", "url": URL, "vid": VID, "lang": "Indonesia",
                                    "whisper_model": "tiny", "duration": 15, "created": "2026-10-21 12:10",
                                    "done_until": 5.0, "lines": ["[00:00:01] satu"]})


class Broken:
    def __init__(self, opts):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def extract_info(self, url, download=False):
        raise RuntimeError("network unreachable")


def test_history_view_shows_saved_analysis_without_calling_the_llm(no_wait, monkeypatch):
    write_transcript_entry({"analysis": '{"stocks": []}', "analysis_model": "m"})

    def no_llm(self, client, messages):
        raise AssertionError("LLM must not be called when the analysis is saved")

    monkeypatch.setattr(app.Pipeline, "request_report", no_llm)
    out = queue.Queue()
    app.Pipeline(URL, "tiny", "Indonesia", "EN", out, mode="view", model="m").run()
    events = drain(out)
    assert ("report_raw", ('{"stocks": []}', "stop")) in events
    assert events[-1] == ("done", None)


def test_finished_analysis_is_saved_in_the_transcript_entry(no_wait, monkeypatch):
    done, _ = write_transcript_entry()
    monkeypatch.setattr(app, "setting", lambda name, default=None: "k" if name == "NINEROUTER_API_KEY" else default)
    monkeypatch.setattr(app.Pipeline, "request_report", lambda self, c, m: ('{"stocks": []}', "stop"))
    app.Pipeline(URL, "tiny", "Indonesia", "EN", queue.Queue(), mode="reuse", model="m").run()
    saved = app.read_meta(done)
    assert saved["analysis"] == '{"stocks": []}' and saved["analysis_model"] == "m"


def test_truncated_analysis_is_not_saved(no_wait, monkeypatch):
    done, _ = write_transcript_entry()
    monkeypatch.setattr(app, "setting", lambda name, default=None: "k" if name == "NINEROUTER_API_KEY" else default)
    monkeypatch.setattr(app.Pipeline, "request_report", lambda self, c, m: ('{"stocks": [', "error: lost"))
    app.Pipeline(URL, "tiny", "Indonesia", "EN", queue.Queue(), mode="reuse", model="m").run()
    assert "analysis" not in app.read_meta(done)


def test_resume_needs_no_network_when_checkpoint_and_audio_exist(no_wait, monkeypatch, tmp_path):
    import yt_dlp

    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.setattr(app, "WORK", work)
    (work / f"{VID}.ogg").write_bytes(b"audio")
    _, partial = app.cache_paths(VID, "id")
    write_checkpoint(partial)
    monkeypatch.setattr(yt_dlp, "YoutubeDL", lambda opts: (_ for _ in ()).throw(AssertionError("no network call")))
    starts = []

    def fake_colab(self, audio, upload, whisper_name, start):
        starts.append(start)
        return iter([remote.Segment(5.0, 10.0, "dua")]), 15.0, "COLAB CUDA"

    monkeypatch.setattr(app.Pipeline, "colab_segments", fake_colab)
    pipeline = app.Pipeline(URL, "tiny", "Indonesia", "EN", queue.Queue(), engine="Colab")
    vid, title, text = pipeline.get_transcript()
    assert (vid, title) == (VID, "Video sebagian")
    assert starts == [5.0] and "satu" in text and "dua" in text


def test_download_failure_with_checkpoint_says_it_is_still_saved(no_wait, monkeypatch, tmp_path):
    import yt_dlp

    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.setattr(app, "WORK", work)  # tanpa audio: unduhan dibutuhkan dan gagal
    _, partial = app.cache_paths(VID, "id")
    write_checkpoint(partial)
    monkeypatch.setattr(yt_dlp, "YoutubeDL", Broken)
    out = queue.Queue()
    app.Pipeline(URL, "tiny", "Indonesia", "EN", out).run()
    kind, msg = drain(out)[-1]
    assert kind == "error" and msg.startswith("Step 1/3 failed: RuntimeError: network unreachable")
    assert "still saved" in msg and "HISTORY" in msg


def test_history_click_without_saved_analysis_does_not_call_the_llm(no_wait, monkeypatch):
    write_transcript_entry()

    def no_llm(self, client, messages):
        raise AssertionError("opening a finished transcript must not start step 3")

    monkeypatch.setattr(app.Pipeline, "request_report", no_llm)
    out = queue.Queue()
    app.Pipeline(URL, "tiny", "Indonesia", "EN", out, mode="view", model="m").run()
    events = drain(out)
    assert ("transcript", ("T", "[00:00:01] BBCA naik")) in events
    assert ("notice", app.STR["EN"]["no_saved"]) in events
    assert not any(kind == "report_raw" for kind, _ in events)
    assert events[-1] == ("done", None)


def test_reanalyze_regenerates_step_3_even_when_an_analysis_is_saved(no_wait, monkeypatch):
    done, _ = write_transcript_entry({"analysis": "old", "analysis_model": "m0"})
    monkeypatch.setattr(app, "setting", lambda name, default=None: "k" if name == "NINEROUTER_API_KEY" else default)
    calls = []

    def fresh_llm(self, client, messages):
        calls.append(1)
        return "new", "stop"

    monkeypatch.setattr(app.Pipeline, "request_report", fresh_llm)
    out = queue.Queue()
    app.Pipeline(URL, "tiny", "Indonesia", "EN", out, mode="reanalyze", model="m").run()
    assert calls == [1]
    assert app.read_meta(done)["analysis"] == "new"
    assert ("report_raw", ("new", "stop")) in drain(out)


def test_main_window_reuse_shows_saved_analysis_instead_of_calling_the_llm(no_wait, monkeypatch):
    write_transcript_entry({"analysis": "saved", "analysis_model": "m"})

    def no_llm(self, client, messages):
        raise AssertionError("saved analysis must be shown")

    monkeypatch.setattr(app.Pipeline, "request_report", no_llm)
    out = queue.Queue()
    app.Pipeline(URL, "tiny", "Indonesia", "EN", out, mode="reuse", model="m").run()
    assert ("report_raw", ("saved", "stop")) in drain(out)


def test_file_entry_click_shows_saved_analysis_and_saves_new_ones(no_wait, monkeypatch, tmp_path):
    monkeypatch.setattr(app, "setting", lambda name, default=None: "k" if name == "NINEROUTER_API_KEY" else default)
    entry = app.save_file_entry("notes", "[00:00:01] BBCA naik", tmp_path / "notes.txt")
    text = ("notes", "[00:00:01] BBCA naik")

    def no_llm(self, client, messages):
        raise AssertionError("clicking a file entry must not start step 3")

    monkeypatch.setattr(app.Pipeline, "request_report", no_llm)
    out = queue.Queue()
    app.Pipeline("", "tiny", "Indonesia", "EN", out, mode="view", preloaded=text, entry=entry, model="m").run()
    assert ("notice", app.STR["EN"]["no_saved"]) in drain(out)

    monkeypatch.setattr(app.Pipeline, "request_report", lambda self, c, m: ("saved report", "stop"))
    app.Pipeline("", "tiny", "Indonesia", "EN", queue.Queue(), mode="reanalyze", preloaded=text, entry=entry,
                 model="m").run()
    assert app.read_meta(entry)["analysis"] == "saved report"

    out = queue.Queue()
    app.Pipeline("", "tiny", "Indonesia", "EN", out, mode="view", preloaded=text, entry=entry, model="m").run()
    assert ("report_raw", ("saved report", "stop")) in drain(out)
