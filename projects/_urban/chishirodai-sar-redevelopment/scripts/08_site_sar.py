"""The Sentinel-1 VV of the site by period, in the layout and at the scale of the photos: outputs/site_sar.png
(with outputs/site_sar.json).

env -u GDAL_DATA -u PROJ_LIB -u PROJ_DATA uvx --with numpy --with rasterio --with pillow --with pyproj python scripts/08_site_sar.py

Reads stack.npy and aux.npz (02_grid.py; orbit 46, RTC gamma0, UTM 54N 10 m). For each period, the VV of all the
period's dates is averaged in linear power and turned into dB. The mean is drawn on the same web-mercator window as
07_site_photos.py (3 x 3 tiles at zoom 17 around the site, 768 px square, north up) by nearest-neighbour resampling, so
one 10 m SAR pixel shows as a block of about 10 x 10 screen pixels. One grey scale for all panels (the 2nd and 98th
percentiles of the window pooled over the periods), with the same red outline (labels/site.geojson) and white circle.

Periods: FY2017 (the first full year of the series), FY2019 and FY2024 (the photos' years), FY2022 (the last year
before the demolition of 2023 autumn; FY2023 mixes before and after and is left out) and the latest 12 months.
"""
import json
import math

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from rasterio.transform import Affine, from_bounds
from rasterio.warp import Resampling, reproject

from common import ART, HERE, OUT, SITE, UTM

Z = 17
CX, CY = 116579, 51641  # z17 tile of the site, as in 07_site_photos.py
W = 768
PERIODS = [("2017 年度", "2017-04-01", "2018-03-31"), ("2019 年度", "2019-04-01", "2020-03-31"),
           ("2022 年度 (解体の前)", "2022-04-01", "2023-03-31"), ("2024 年度", "2024-04-01", "2025-03-31"),
           ("最新の 1 年", "2025-10-25", "2026-10-24")]
FONT = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
SOURCE = ("出典: Contains modified Copernicus Sentinel data 2017-2026 (Planetary Computer sentinel-1-rtc、軌道 46)。"
          "赤線は © OpenStreetMap contributors (ODbL) の工事区域 way 1423054131")
R = 6378137.0


def merc_x(tx):
    return tx / 2 ** Z * 2 * math.pi * R - math.pi * R


def merc_y(ty):
    return math.pi * R - ty / 2 ** Z * 2 * math.pi * R


def pixel(lon, lat):
    n = 2 ** Z
    gx = (lon + 180) / 360 * n
    gy = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n
    return (gx - (CX - 1)) * 256, (gy - (CY - 1)) * 256


def main():
    aux = np.load(ART / "aux.npz")
    dates = [str(d) for d in aux["dates"]]
    t = aux["transform"]
    src_t = Affine(t[0], t[1], t[2], t[3], t[4], t[5])
    st = np.load(ART / "stack.npy", mmap_mode="r")
    dst_t = from_bounds(merc_x(CX - 1), merc_y(CY + 2), merc_x(CX + 2), merc_y(CY - 1), W, W)
    means, counts = [], []
    for label, a, b in PERIODS:
        sel = [i for i, d in enumerate(dates) if a <= d <= b]
        if not sel:
            raise RuntimeError(f"no date in {label}")
        lin = np.nanmean(np.asarray(st[0, sel], float), axis=0)
        dst = np.full((W, W), np.nan)
        reproject(lin, dst, src_transform=src_t, src_crs=UTM, dst_transform=dst_t, dst_crs="EPSG:3857",
                  resampling=Resampling.nearest, src_nodata=np.nan, dst_nodata=np.nan)
        if np.isnan(dst).any():
            raise RuntimeError(f"{label}: {int(np.isnan(dst).sum())} screen pixels without SAR")
        means.append(10 * np.log10(dst))
        counts.append((label, a, b, len(sel), dates[sel[0]], dates[sel[-1]]))
    lo, hi = (float(v) for v in np.percentile(np.stack(means), [2, 98]))

    ring = json.loads((HERE.parent / "labels/site.geojson").read_text(encoding="utf-8"))["features"][0]["geometry"][
        "coordinates"][0]
    font, small = ImageFont.truetype(FONT, 26), ImageFont.truetype(FONT, 17)
    panels = []
    for db, (label, a, b, n, first, last) in zip(means, counts):
        g = np.clip((db - lo) / (hi - lo), 0, 1)
        im = Image.fromarray((g * 255).round().astype(np.uint8), "L").convert("RGB")
        dr = ImageDraw.Draw(im)
        dr.line([pixel(lon, lat) for lon, lat in ring], fill=(255, 40, 40), width=3)
        px, py = pixel(*SITE)
        dr.ellipse((px - 9, py - 9, px + 9, py + 9), outline=(255, 255, 255), width=3)
        dr.rectangle((0, 0, W, 40), fill=(255, 255, 255))
        dr.text((8, 2), f"{label}  {n} 回の平均", fill=(0, 0, 0), font=font)
        panels.append(im)
    out = Image.new("RGB", (3 * W + 20, 2 * W + 10 + 70), (255, 255, 255))
    for k, p in enumerate(panels):
        out.paste(p, ((k % 3) * (W + 10), (k // 3) * (W + 10)))
    dr = ImageDraw.Draw(out)
    x0, y0 = 2 * (W + 10) + 10, W + 30
    dr.text((x0, y0), "Sentinel-1 の VV (γ0) の期間の平均、dB\nズームレベル 17、3 × 3 タイル (約 750 m 四方)、北が上\n"
            "1 画素 10 m (写真と同じ範囲と縮尺に拡大)\n赤線: OSM の工事区域 (SITE)\n白丸: 千葉市若葉区千城台東 2-13",
            fill=(0, 0, 0), font=small)
    bx, by, bw = x0, y0 + 150, 600
    bar = np.tile(np.linspace(0, 255, bw).round().astype(np.uint8), (24, 1))
    out.paste(Image.fromarray(bar, "L").convert("RGB"), (bx, by))
    dr.rectangle((bx, by, bx + bw, by + 24), outline=(0, 0, 0))
    for v in range(math.ceil(lo), math.floor(hi) + 1):
        if v % 2 == 0:
            x = bx + (v - lo) / (hi - lo) * bw
            dr.line((x, by + 24, x, by + 32), fill=(0, 0, 0), width=2)
            dr.text((x - 12, by + 34), f"{v}", fill=(0, 0, 0), font=small)
    dr.text((bx, by + 60), "暗い: 電波が返らない (平らな面、水)。明るい: 建物の壁や角で強く返る", fill=(0, 0, 0), font=small)
    dr.text((10, 2 * W + 30), SOURCE, fill=(0, 0, 0), font=small)
    out = out.resize((round(out.width * 0.75), round(out.height * 0.75)), Image.LANCZOS)
    out.save(OUT / "site_sar.png", optimize=True)
    (OUT / "site_sar.json").write_text(json.dumps({
        "question": "地理院の写真 (図 0) と同じ範囲と縮尺で、調べた街区の SAR の明るさは期間ごとにどう変わったか",
        "inputs": ["artifacts/_urban/chishirodai-sar-redevelopment/stack.npy", "aux.npz", "labels/site.geojson"],
        "polarisation": "VV", "orbit": 46, "mean": "linear power, then dB", "resampling": "nearest, UTM 54N 10 m to EPSG:3857",
        "window": {"zoom": Z, "tiles_x": [CX - 1, CX + 1], "tiles_y": [CY - 1, CY + 1], "pixels": W},
        "grey_db": [round(lo, 2), round(hi, 2)], "grey_rule": "2nd and 98th percentiles of the window, pooled over periods",
        "periods": [{"label": p[0], "fiscal_year": int(p[0][:4]) if p[0][:4].isdigit() else None, "from": p[1],
                     "to": p[2], "dates": p[3], "first": p[4], "last": p[5]} for p in counts],
        "site_mean_db": {p[0]: round(float(10 * np.log10(np.nanmean(np.asarray(st[0, [i for i, d in enumerate(dates)
                                                                                         if p[1] <= d <= p[2]]], float)
                                                                         [:, aux["site"]]))), 2) for p in counts},
    }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(lo, hi, counts, (OUT / "site_sar.png").stat().st_size)


if __name__ == "__main__":
    main()
