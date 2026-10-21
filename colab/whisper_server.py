"""Server Whisper untuk Google Colab (GPU). Dijalankan oleh Whisper_Server.ipynb.

POST /transcribe  (multipart: file, model, language, start) -> aliran NDJSON, satu objek JSON per baris:
  {"type":"loading"} | {"type":"info","duration":..,"device":..} | {"type":"seg","start":..,"end":..,"text":..}
  | {"type":"ping"} | {"type":"done"} | {"type":"error","message":..}
GET  /health      -> info perangkat dan model yang sudah dimuat
Semua endpoint wajib header "Authorization: Bearer <WHISPER_TOKEN>".
"""
import json
import os
import queue
import secrets
import shutil
import tempfile
import threading

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

TOKEN = os.environ["WHISPER_TOKEN"]
PING_EVERY = 3  # detik; menjaga tunnel tetap hidup dan membuat klien yang putus cepat terdeteksi
TAKEOVER_WAIT = 30  # detik; tunggu pekerjaan lama berhenti bila ada permintaan baru

app = FastAPI()
models = {}
busy = threading.Lock()  # satu transkripsi pada satu waktu
current_stop = [None]  # Event pekerjaan yang sedang jalan; permintaan baru menghentikannya (klien lama bisa sudah mati)


def device_info():
    import ctranslate2

    return ("cuda", "float16") if ctranslate2.get_cuda_device_count() > 0 else ("cpu", "int8")


def get_model(name):
    if name not in models:
        from faster_whisper import WhisperModel

        device, compute = device_info()
        models[name] = WhisperModel(name, device=device, compute_type=compute)
    return models[name]


def authorize(authorization):
    if not secrets.compare_digest(authorization.encode(), f"Bearer {TOKEN}".encode()):
        raise HTTPException(401, "token salah")


@app.get("/health")
def health(authorization: str = Header(default="")):
    authorize(authorization)
    return {"status": "busy" if busy.locked() else "ok", "device": device_info()[0], "models": sorted(models)}


@app.post("/transcribe")
def transcribe(file: UploadFile = File(...), model: str = Form("large-v3"), language: str = Form(""),
               start: float = Form(0.0), authorization: str = Header(default="")):
    authorize(authorization)
    if current_stop[0]:
        current_stop[0].set()
    if not busy.acquire(timeout=TAKEOVER_WAIT):
        raise HTTPException(409, "server sedang memproses transkripsi lain")
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".audio") as tmp:
            shutil.copyfileobj(file.file, tmp)
    except BaseException:
        busy.release()
        raise

    out, stop = queue.Queue(), threading.Event()
    current_stop[0] = stop

    def work():
        try:
            if model not in models:
                out.put({"type": "loading"})
            wm = get_model(model)
            kwargs = {"language": language or None, "task": "transcribe", "vad_filter": True,
                      "condition_on_previous_text": False}
            if start > 0:
                kwargs["clip_timestamps"] = str(start)
            segments, tinfo = wm.transcribe(tmp.name, **kwargs)
            out.put({"type": "info", "duration": tinfo.duration, "device": device_info()[0]})
            for seg in segments:
                if stop.is_set():
                    return
                out.put({"type": "seg", "start": seg.start, "end": seg.end, "text": seg.text.strip()})
            out.put({"type": "done"})
        except Exception as e:
            out.put({"type": "error", "message": f"{type(e).__name__}: {e}"})
        finally:
            os.unlink(tmp.name)
            busy.release()

    threading.Thread(target=work, daemon=True).start()

    def stream():
        try:
            while True:
                try:
                    item = out.get(timeout=PING_EVERY)
                except queue.Empty:
                    item = {"type": "ping"}
                yield json.dumps(item, ensure_ascii=False) + "\n"
                if item["type"] in ("done", "error"):
                    return
        finally:
            stop.set()  # klien memutus koneksi / membatalkan: hentikan transkripsi

    return StreamingResponse(stream(), media_type="application/x-ndjson", headers={"X-Accel-Buffering": "no"})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("PORT", "8000")), log_level="warning")
