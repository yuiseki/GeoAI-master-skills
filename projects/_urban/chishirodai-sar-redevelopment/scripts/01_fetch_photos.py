"""Fetch the GSI aerial photo tiles of FY2019 and FY2024 over the 12 x 12 z16 tiles, and draw the labelling sheets.

uvx --with pillow --with pyproj python scripts/01_fetch_photos.py

- raw/photo/nendophoto<year>/16/<x>_<y>.png from https://cyberjapandata.gsi.go.jp/xyz/nendophoto<year>/16/<x>/<y>.png
- raw/photo/sheets/sheet_<i>.png: 16 sheets, each a 3 x 3 block of tiles, FY2019 on the left and FY2024 on the right,
  with the tile ids, used to label the tiles by eye (labels/labels.csv) before any SAR value is read
- raw/MANIFEST_photo.json: url, bytes and sha256 of every tile
"""
import json
import time
import urllib.error
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from common import RAW, TX, TY, Z, get, sha

YEARS = (2019, 2024)
FONT = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"


def main():
    manifest = []
    for yr in YEARS:
        d = RAW / "photo" / f"nendophoto{yr}" / str(Z)
        d.mkdir(parents=True, exist_ok=True)
        for x in TX:
            for y in TY:
                p = d / f"{x}_{y}.png"
                url = f"https://cyberjapandata.gsi.go.jp/xyz/nendophoto{yr}/{Z}/{x}/{y}.png"
                if not p.exists():
                    try:
                        p.write_bytes(get(url))
                    except urllib.error.HTTPError as e:
                        raise RuntimeError(f"missing tile {url}: {e}")
                    time.sleep(0.05)
                manifest.append({"path": str(p.relative_to(RAW)), "url": url, "bytes": p.stat().st_size, "sha256": sha(p)})
    (RAW / "MANIFEST_photo.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    sd = RAW / "photo" / "sheets"
    sd.mkdir(parents=True, exist_ok=True)
    font = ImageFont.truetype(FONT, 18)
    big = ImageFont.truetype(FONT, 26)
    xs, ys = list(TX), list(TY)
    k = 0
    for by in range(0, 12, 3):
        for bx in range(0, 12, 3):
            sheet = Image.new("RGB", (2 * 768 + 20, 768 + 40), (255, 255, 255))
            dr = ImageDraw.Draw(sheet)
            for side, yr in enumerate(YEARS):
                ox = side * (768 + 20)
                dr.text((ox + 4, 4), f"{yr} 年度", fill=(0, 0, 0), font=big)
                for i in range(3):
                    for j in range(3):
                        x, y = xs[bx + i], ys[by + j]
                        im = Image.open(RAW / "photo" / f"nendophoto{yr}" / str(Z) / f"{x}_{y}.png").convert("RGB")
                        sheet.paste(im, (ox + 256 * i, 40 + 256 * j))
                        dr.rectangle((ox + 256 * i, 40 + 256 * j, ox + 256 * i + 255, 40 + 256 * j + 255),
                                     outline=(255, 255, 0), width=1)
                        dr.rectangle((ox + 256 * i + 2, 42 + 256 * j, ox + 256 * i + 120, 64 + 256 * j), fill=(0, 0, 0))
                        dr.text((ox + 256 * i + 4, 42 + 256 * j), f"{x}_{y}", fill=(255, 255, 0), font=font)
            sheet.save(sd / f"sheet_{k:02d}.png")
            k += 1
    print("tiles", len(manifest), "sheets", k)


if __name__ == "__main__":
    main()
