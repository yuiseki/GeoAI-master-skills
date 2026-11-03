"""The GSI aerial photos of the site, side by side: outputs/site_photos.png (source line in site_photos_source.txt).

uvx --with pillow --with numpy python scripts/07_site_photos.py

Fetches 3 x 3 tiles at zoom 17 around the site (about 750 m square) into raw/photo/site_z17/ for: 国土画像情報 1987-1990
(gazo4), 年度別空中写真 FY2009, FY2019, FY2024 (nendophoto<year>) and 電子国土基本図 (ort, the latest), and draws them
with the outline of labels/site.geojson (red) and the requester's point (white circle). Tiles already there are not
fetched again; raw/photo/MANIFEST_site_z17.json lists them with sha256.
"""
import io
import json
import math

from PIL import Image, ImageDraw, ImageFont

from common import HERE, OUT, RAW, SITE, get, sha

Z = 17
CX, CY = 116579, 51641  # z17 tile of the site
LAYERS = [("gazo4", "jpg", "1987〜1990 年 (国土画像情報)"), ("nendophoto2009", "png", "2009 年度"),
          ("nendophoto2019", "png", "2019 年度"), ("nendophoto2024", "png", "2024 年度"),
          ("ort", "jpg", "電子国土基本図 (最新)")]
FONT = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
SOURCE = ("出典: 国土地理院 (地理院タイル 年度別空中写真 nendophoto2009、2019、2024、電子国土基本図 (オルソ画像) ort、"
          "国土画像情報 gazo4)。赤線は © OpenStreetMap contributors (ODbL) の工事区域 way 1423054131")


def pixel(lon, lat):
    n = 2 ** Z
    gx = (lon + 180) / 360 * n
    gy = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n
    return (gx - (CX - 1)) * 256, (gy - (CY - 1)) * 256


def main():
    d = RAW / "photo" / "site_z17"
    d.mkdir(parents=True, exist_ok=True)
    ring = json.loads((HERE.parent / "labels/site.geojson").read_text(encoding="utf-8"))["features"][0]["geometry"][
        "coordinates"][0]
    font, small = ImageFont.truetype(FONT, 26), ImageFont.truetype(FONT, 17)
    manifest, panels = [], []
    for name, ext, label in LAYERS:
        im = Image.new("RGB", (768, 768))
        for i in range(3):
            for j in range(3):
                x, y = CX - 1 + i, CY - 1 + j
                p = d / f"{name}_{x}_{y}.{ext}"
                url = f"https://cyberjapandata.gsi.go.jp/xyz/{name}/{Z}/{x}/{y}.{ext}"
                if not p.exists():
                    p.write_bytes(get(url))
                manifest.append({"path": str(p.relative_to(RAW)), "url": url, "bytes": p.stat().st_size, "sha256": sha(p)})
                im.paste(Image.open(io.BytesIO(p.read_bytes())).convert("RGB"), (256 * i, 256 * j))
        dr = ImageDraw.Draw(im)
        dr.line([pixel(lon, lat) for lon, lat in ring], fill=(255, 40, 40), width=3)
        px, py = pixel(*SITE)
        dr.ellipse((px - 9, py - 9, px + 9, py + 9), outline=(255, 255, 255), width=3)
        dr.rectangle((0, 0, 768, 40), fill=(255, 255, 255))
        dr.text((8, 2), label, fill=(0, 0, 0), font=font)
        panels.append(im)
    W = 768
    out = Image.new("RGB", (3 * W + 20, 2 * W + 10 + 70), (255, 255, 255))
    for k, p in enumerate(panels):
        out.paste(p, ((k % 3) * (W + 10), (k // 3) * (W + 10)))
    dr = ImageDraw.Draw(out)
    dr.text((2 * (W + 10) + 10, W + 30),
            "ズームレベル 17、3 × 3 タイル (約 750 m 四方)、北が上\n赤線: OSM の工事区域 (SITE)\n白丸: 千葉市若葉区千城台東 2-13\n"
            "扇形の街区の低層の棟は 2019 年度まであり、\n2024 年度には全て消えている", fill=(0, 0, 0), font=small)
    dr.text((10, 2 * W + 30), SOURCE, fill=(0, 0, 0), font=small)
    out = out.resize((round(out.width * 0.75), round(out.height * 0.75)), Image.LANCZOS)  # keep the PNG near 3 MB
    out.save(OUT / "site_photos.png", optimize=True)
    (RAW / "photo" / "MANIFEST_site_z17.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n",
                                                          encoding="utf-8")
    (OUT / "site_photos_source.txt").write_text(SOURCE + "\n", encoding="utf-8")
    print("tiles", len(manifest), (OUT / "site_photos.png").stat().st_size)


if __name__ == "__main__":
    main()
