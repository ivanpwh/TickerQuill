"""Bersihkan pengulangan halusinasi Whisper dari transkrip."""
import re

TS = re.compile(r"^(\[\d{2}:\d{2}:\d{2}\]\s*)?(.*)$")
# 1-4 kata yang berulang >= 4 kali berturut-turut ("iya iya iya iya", "ya kan ya kan ya kan ya kan")
RUN = re.compile(r"\b((?:\w[\w'-]*\s+){0,3}?\w[\w'-]*)(?:[\s,.]+\1\b){3,}", re.IGNORECASE)
KEEP = 2  # sisakan sekian kali pengulangan


def collapse_runs(text):
    return RUN.sub(lambda m: " ".join([m.group(1)] * KEEP), text)


def clean_repeats(text):
    """Collapse pengulangan kata/frasa dalam baris dan hapus baris identik berturutan.
    Penanda waktu [hh:mm:ss] di awal baris dipertahankan."""
    out, prev = [], None
    for line in text.splitlines():
        stamp, body = TS.match(line).groups()
        body = collapse_runs(body).strip()
        key = body.lower()
        if not body or key == prev:
            continue
        prev = key
        out.append((stamp or "") + body)
    return "\n".join(out)


if __name__ == "__main__":
    import sys
    from pathlib import Path

    src = Path(sys.argv[1])
    raw = src.read_text(encoding="utf-8")
    cleaned = clean_repeats(raw)
    print(f"lines {len(raw.splitlines())} -> {len(cleaned.splitlines())}, chars {len(raw)} -> {len(cleaned)}")
    if len(sys.argv) > 2:
        Path(sys.argv[2]).write_text(cleaned + "\n", encoding="utf-8")
