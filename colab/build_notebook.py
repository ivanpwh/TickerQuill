"""Build Whisper_Server.ipynb from whisper_server.py. Re-run whenever the server changes:
    python colab/build_notebook.py
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

INTRO = """# Whisper server (GPU) for TickerQuill

1. Menu **Runtime > Change runtime type**, choose **T4 GPU**.
2. Run the cells below in order (or **Runtime > Run all**).
3. The last cell prints one `URL TOKEN` line. Copy it, then in the app open **Settings > Transcription**, set **Run Whisper on** to **Colab**, paste the line into **Colab server URL**, press **Test connection** and **Save**.
4. Leave the last cell running while you use the app. A new URL and token are created every session.

Audio is sent from your computer to this Colab session through a Cloudflare tunnel protected by a random token. Check Colab's terms of use for your use case."""

INSTALL = """import subprocess

if subprocess.run(["nvidia-smi", "-L"], capture_output=True).returncode != 0:
    print("WARNING: no GPU detected. Choose Runtime > Change runtime type > T4 GPU, then run again.")
!pip -q install faster-whisper fastapi uvicorn python-multipart"""

START = '''import glob, os, re, secrets, site, subprocess, sys, time, urllib.request

token = secrets.token_urlsafe(24)
# CUDA/cuDNN libraries from the pip nvidia-* packages must be on LD_LIBRARY_PATH before the server process starts.
libs = {os.path.dirname(p) for d in site.getsitepackages()
        for p in glob.glob(os.path.join(d, "nvidia", "*", "lib", "*.so*"))}
env = {**os.environ, "WHISPER_TOKEN": token, "PORT": "8000",
       "LD_LIBRARY_PATH": ":".join(sorted(libs) + [os.environ.get("LD_LIBRARY_PATH", "")])}
server = subprocess.Popen([sys.executable, "whisper_server.py"], env=env)

for _ in range(60):
    try:
        req = urllib.request.Request("http://127.0.0.1:8000/health", headers={"Authorization": f"Bearer {token}"})
        urllib.request.urlopen(req, timeout=2).read()
        break
    except Exception:
        time.sleep(1)
else:
    raise RuntimeError("The server did not start; see the error output above.")

if not os.path.exists("cloudflared"):
    urllib.request.urlretrieve(
        "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64", "cloudflared")
    os.chmod("cloudflared", 0o755)
tunnel = subprocess.Popen(["./cloudflared", "tunnel", "--url", "http://127.0.0.1:8000", "--no-autoupdate"],
                          stdout=open("tunnel.log", "w"), stderr=subprocess.STDOUT)
url = None
for _ in range(60):
    m = re.search(r"https://[a-z0-9-]+\\.trycloudflare\\.com", open("tunnel.log").read())
    if m:
        url = m.group(0)
        break
    time.sleep(1)
if not url:
    raise RuntimeError("The tunnel was not created:\\n" + open("tunnel.log").read())

print("Paste this line into TickerQuill > Settings > Transcription > Colab server URL:\\n")
print(f"{url} {token}\\n")
print("Server running. Leave this cell running; press Stop when you are done.")
try:
    while server.poll() is None and tunnel.poll() is None:
        time.sleep(5)
finally:
    server.terminate()
    tunnel.terminate()'''


def cell(kind, source):
    base = {"cell_type": kind, "metadata": {}, "source": source.splitlines(keepends=True)}
    return base if kind == "markdown" else {**base, "execution_count": None, "outputs": []}


server_src = (HERE / "whisper_server.py").read_text(encoding="utf-8")
notebook = {
    "cells": [
        cell("markdown", INTRO),
        cell("code", INSTALL),
        cell("code", "%%writefile whisper_server.py\n" + server_src),
        cell("code", START),
    ],
    "metadata": {"accelerator": "GPU", "colab": {"gpuType": "T4", "name": "Whisper_Server.ipynb"},
                 "kernelspec": {"display_name": "Python 3", "name": "python3"}},
    "nbformat": 4, "nbformat_minor": 4,
}
(HERE / "Whisper_Server.ipynb").write_text(json.dumps(notebook, ensure_ascii=False, indent=1), encoding="utf-8")
print("Whisper_Server.ipynb written")
