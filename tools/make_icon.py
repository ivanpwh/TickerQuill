"""Gambar ikon TickerQuill dan simpan semua ukuran/format yang dipakai.

Satu bentuk: tetes tinta (menulis/merangkum, "quill") dengan candlestick sebagai potongan di dalamnya (harga saham,
"ticker"). Hijau Retro Green di atas latar gelap; bentuk solid tanpa detail kecil agar tetap terbaca di 16 px.

    python tools/make_icon.py

Butuh Pillow (`pip install pillow`; hanya untuk membuat ulang ikon, bukan untuk menjalankan aplikasi).
Hasil: tickerquill/assets/icon/tickerquill-<ukuran>.png, tickerquill.ico (Windows), tickerquill.icns (macOS).
"""
import math
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent.parent / "tickerquill" / "assets" / "icon"
BG, FG = "#0a0f0a", "#38ff6a"
MASTER = 1024
SS = 4  # supersampling: digambar 4x lebih besar lalu diperkecil, supaya tepi halus
PNG_SIZES = (16, 24, 32, 48, 64, 128, 256, 512, 1024)
ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)


def draw(size):
    big = size * SS
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    u = big / 100  # satuan: persen dari sisi
    d.rounded_rectangle([2 * u, 2 * u, 98 * u, 98 * u], radius=22 * u, fill=BG)

    # tetes tinta: lingkaran di bawah + segitiga yang menyinggung lingkaran ke ujung atas
    cx, cy, r, top = 50, 60, 28, 10
    a = math.asin(r / (cy - top))
    left = (cx - r * math.cos(a), cy - r * math.sin(a))
    right = (cx + r * math.cos(a), cy - r * math.sin(a))
    d.ellipse([(cx - r) * u, (cy - r) * u, (cx + r) * u, (cy + r) * u], fill=FG)
    d.polygon([(cx * u, top * u), (left[0] * u, left[1] * u), (right[0] * u, right[1] * u)], fill=FG)

    # candlestick sebagai potongan: sumbu dan badan dalam warna latar (lebih tebal di ukuran kecil)
    wick = 3.6 if size <= 32 else 2.6
    d.rectangle([(cx - wick / 2) * u, 40 * u, (cx + wick / 2) * u, 80 * u], fill=BG)
    d.rectangle([(cx - 7) * u, 50 * u, (cx + 7) * u, 70 * u], fill=BG)
    return img.resize((size, size), Image.LANCZOS)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    master = draw(MASTER)
    for s in PNG_SIZES:
        img = master if s == MASTER else draw(s) if s <= 64 else master.resize((s, s), Image.LANCZOS)
        img.save(OUT / f"tickerquill-{s}.png", optimize=True)
    # ukuran kecil digambar sendiri (bukan diperkecil dari 1024) supaya garisnya tetap tegas
    master.save(OUT / "tickerquill.ico", sizes=[(s, s) for s in ICO_SIZES],
                append_images=[draw(s) for s in ICO_SIZES if s <= 64])
    master.save(OUT / "tickerquill.icns")
    print("written:", ", ".join(sorted(p.name for p in OUT.iterdir())))


if __name__ == "__main__":
    main()
