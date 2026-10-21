"""Klien untuk server Whisper di Google Colab (colab/whisper_server.py). Hanya library standar + PyAV."""
import http.client
import json
import ssl
import urllib.parse
import uuid
from collections import namedtuple
from pathlib import Path

Segment = namedtuple("Segment", "start end text")
CHUNK = 1 << 20


class RemoteError(Exception):
    pass


def compress_audio(src, dst, check=lambda: None, bitrate=32000):
    """Ubah ke Opus mono 16 kHz (format asli Whisper): ~14 MB per jam, jadi unggahan cepat dan di bawah batas tunnel."""
    import av

    dst.parent.mkdir(exist_ok=True)
    tmp = dst.with_suffix(".part")  # baru dipindah ke dst setelah lengkap, supaya file setengah jadi tidak dipakai ulang
    resampler = av.AudioResampler(format="s16", layout="mono", rate=16000)
    try:
        with av.open(str(src)) as inp, av.open(str(tmp), "w", format="ogg") as out:
            stream = out.add_stream("libopus", rate=16000)
            stream.bit_rate = bitrate
            stream.layout = "mono"
            for frame in inp.decode(audio=0):
                check()
                for f in resampler.resample(frame):
                    out.mux(stream.encode(f))
            for f in resampler.resample(None):
                out.mux(stream.encode(f))
            out.mux(stream.encode(None))
        tmp.replace(dst)
    finally:
        tmp.unlink(missing_ok=True)


def _connect(base, timeout=60):
    u = urllib.parse.urlsplit(base.strip())
    if u.scheme not in ("http", "https") or not u.netloc:
        raise RemoteError(f"URL Colab tidak valid: {base!r}")
    if u.scheme == "https":
        try:
            import certifi

            ctx = ssl.create_default_context(cafile=certifi.where())
        except ImportError:
            ctx = ssl.create_default_context()
        return http.client.HTTPSConnection(u.netloc, timeout=timeout, context=ctx), u.path.rstrip("/")
    return http.client.HTTPConnection(u.netloc, timeout=timeout), u.path.rstrip("/")


def _fail(resp):
    body = resp.read().decode("utf-8", "replace")
    try:
        body = json.loads(body).get("detail", body)
    except ValueError:
        pass
    raise RemoteError(f"Server Colab menjawab {resp.status}: {str(body)[:200]}")


def health(base, token):
    conn, prefix = _connect(base, timeout=15)
    try:
        conn.request("GET", prefix + "/health", headers={"Authorization": f"Bearer {token}"})
        resp = conn.getresponse()
        if resp.status != 200:
            _fail(resp)
        return json.load(resp)
    except (OSError, http.client.HTTPException, ValueError) as e:
        raise RemoteError(f"{type(e).__name__}: {e}") from e
    finally:
        conn.close()


def _multipart(fields, boundary):
    return b"".join(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
                    for k, v in fields.items())


def events(base, token, audio, model, language, start=0.0, check=lambda: None, on_upload=lambda frac: None):
    """Unggah audio, lalu hasilkan (jenis, nilai): ('loading', None), ('info', dict), ('seg', Segment).
    Menutup koneksi saat generator ditutup, sehingga server berhenti memproses."""
    audio = Path(audio)
    boundary = uuid.uuid4().hex
    head = _multipart({"model": model, "language": language or "", "start": start}, boundary) + (
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{audio.name}"\r\n'
        "Content-Type: application/octet-stream\r\n\r\n").encode()
    tail = f"\r\n--{boundary}--\r\n".encode()
    size = audio.stat().st_size
    conn, prefix = _connect(base)
    try:
        conn.putrequest("POST", prefix + "/transcribe")
        conn.putheader("Authorization", f"Bearer {token}")
        conn.putheader("Content-Type", f"multipart/form-data; boundary={boundary}")
        conn.putheader("Content-Length", str(len(head) + size + len(tail)))
        conn.endheaders()
        conn.send(head)
        sent = 0
        with audio.open("rb") as f:
            while chunk := f.read(CHUNK):
                check()
                conn.send(chunk)
                sent += len(chunk)
                on_upload(sent / max(size, 1))
        conn.send(tail)
        resp = conn.getresponse()
        if resp.status != 200:
            _fail(resp)
        done = False
        for line in resp:
            check()
            if not line.strip():
                continue
            ev = json.loads(line)
            kind = ev["type"]
            if kind == "error":
                raise RemoteError(ev["message"])
            if kind == "done":
                done = True
            elif kind == "loading":
                yield "loading", None
            elif kind == "info":
                yield "info", ev
            elif kind == "seg":
                yield "seg", Segment(ev["start"], ev["end"], ev["text"])
        if not done:
            raise RemoteError("Koneksi ke Colab terputus sebelum transkripsi selesai.")
    except (OSError, http.client.HTTPException, ValueError) as e:
        raise RemoteError(f"{type(e).__name__}: {e}") from e
    finally:
        conn.close()
