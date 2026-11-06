"""B3 of EXPERIMENT_PLAN.md: for the 3 candidates per box with the most people near the chain's line
(outputs/candidates.csv), draw GSI aerial photos (seamlessphoto) and the GSI standard map at zoom 16 (and a close-up of the ponds on the zoom 17 photo) with the start
pond (red), the overflowed ponds (orange, ledger points), the flow line (blue) and its 100 m band.
Writes outputs/fig_visual_<box>.jpg and outputs/visual_picks.csv. The verdicts are written by hand in
outputs/visual_verdicts.csv.

  systemd-run --user --scope -q -p MemoryMax=4G -p MemorySwapMax=0 -p CPUQuota=200% -- uvx --python 3.12 \
    --with duckdb==1.5.5 --with numpy --with pillow --with matplotlib --with pyproj --with shapely python scripts/visual.py
"""

import csv
import io
import json
import math
import time
import urllib.request
from pathlib import Path

import duckdb
import matplotlib
import numpy as np
from PIL import Image
from pyproj import Transformer
from shapely.geometry import LineString

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402

PROJECT = Path(__file__).resolve().parent.parent
OUT = PROJECT / "outputs"
CACHE = PROJECT.parents[2] / "artifacts/_tameike/tameike-cascade-wide/gsi"
TAMEIKE = ("https://huggingface.co/datasets/yuiseki/maff-tameike-list-jp-2026-03/resolve/"
           "ee87755e53cf5b049b31bc307aca56ad950771cc/parquet/maff_tameike_ichiran_20260331.parquet")
Z = 16
LAYERS = {"seamlessphoto": "jpg", "std": "png"}
N_PICK = 3
R = 6378137.0
for fam in ("Noto Sans CJK JP", "Noto Sans CJK TC"):
    if any(fam == x.name for x in font_manager.fontManager.ttflist):
        plt.rcParams["font.family"] = fam
        break


def tile(layer, x, y, z=Z):
    path = CACHE / layer / f"{z}_{x}_{y}.{LAYERS[layer]}"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        url = f"https://cyberjapandata.gsi.go.jp/xyz/{layer}/{z}/{x}/{y}.{LAYERS[layer]}"
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                path.write_bytes(r.read())
        except urllib.error.HTTPError as e:   # no tile (sea): leave it blank, but say so
            if e.code != 404:
                raise
            path.write_bytes(b"")
        time.sleep(0.05)
    b = path.read_bytes()
    return Image.open(io.BytesIO(b)).convert("RGB") if b else Image.new("RGB", (256, 256), (230, 230, 230))


def mosaic(layer, x0, y0, x1, y1, z=Z):
    """web mercator bounds (m) -> image and its extent"""
    n = 2 ** z
    tx = lambda x: (x + math.pi * R) / (2 * math.pi * R) * n
    ty = lambda y: (math.pi * R - y) / (2 * math.pi * R) * n
    c0, c1, r0, r1 = int(tx(x0)), int(tx(x1)), int(ty(y1)), int(ty(y0))
    img = Image.new("RGB", ((c1 - c0 + 1) * 256, (r1 - r0 + 1) * 256))
    for c in range(c0, c1 + 1):
        for r in range(r0, r1 + 1):
            img.paste(tile(layer, c, r, z), ((c - c0) * 256, (r - r0) * 256))
    size = 2 * math.pi * R / n
    ext = (-math.pi * R + c0 * size, -math.pi * R + (c1 + 1) * size, math.pi * R - (r1 + 1) * size, math.pi * R - r0 * size)
    return np.asarray(img), ext


def main():
    cands = list(csv.DictReader(open(OUT / "candidates.csv", encoding="utf-8")))
    con = duckdb.connect()
    to = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
    picks = []
    for box in ("kagawa", "fukuyama", "awaji"):
        top = sorted([c for c in cands if c["box"] == box], key=lambda c: -float(c["people_chain"]))[:N_PICK]
        if not top:
            continue
        lines = {f["properties"]["start"]: f["geometry"]["coordinates"] for f in
                 json.loads((OUT / f"{box}_chain_lines.geojson").read_text(encoding="utf-8"))["features"]}
        chains = {c["start"]: c for c in csv.DictReader(open(OUT / f"{box}_chains.csv", encoding="utf-8"))}
        fig, axes = plt.subplots(len(top), 3, figsize=(18, 7.2 * len(top)))
        axes = np.atleast_2d(axes)
        for row, c in zip(axes, top):
            ch = chains[c["start_node"]]
            groups = [ch["start_source_rows"]] + ch["overflowed_source_rows"].split(" > ")
            pts = []
            for i, g in enumerate(groups):
                for sr in g.split("|"):
                    lon, lat = con.execute(f"select lon, lat from '{TAMEIKE}' where source_row = {int(sr)}").fetchone()
                    if lon is not None:
                        pts.append((i, *to.transform(lon, lat)))
            xy = np.array(to.transform(*np.array(lines[int(c["start_node"])]).T)).T
            band = LineString(xy).buffer(100.0 / math.cos(math.radians(float(np.mean(np.array(lines[int(c["start_node"])])[:, 1])))))
            xs = np.concatenate([xy[:, 0], [p[1] for p in pts]])
            ys = np.concatenate([xy[:, 1], [p[2] for p in pts]])
            m = 250.0
            x0, x1, y0, y1 = xs.min() - m, xs.max() + m, ys.min() - m, ys.max() + m
            # third panel: the ponds up close on the zoom 17 photo
            px_, py_ = np.array([p[1] for p in pts]), np.array([p[2] for p in pts])
            cx, cy = (px_.min() + px_.max()) / 2, (py_.min() + py_.max()) / 2
            half = max(px_.max() - px_.min(), py_.max() - py_.min()) / 2 + 180.0
            views = [(row[0], "seamlessphoto", (x0, y0, x1, y1), Z), (row[1], "std", (x0, y0, x1, y1), Z),
                     (row[2], "seamlessphoto", (cx - half, cy - half, cx + half, cy + half), 17)]
            for ax, layer, (vx0, vy0, vx1, vy1), zz in views:
                img, ext = mosaic(layer, vx0, vy0, vx1, vy1, zz)
                ax.imshow(img, extent=ext, interpolation="bilinear")
                bx, by = band.exterior.xy
                ax.fill(bx, by, facecolor="#60a5fa", alpha=0.18, edgecolor="#1d4ed8", linewidth=0.6)
                ax.plot(xy[:, 0], xy[:, 1], color="#1d4ed8", linewidth=1.4)
                for i, px, py in pts:
                    ax.plot(px, py, "o", ms=9 if i == 0 else 7, mfc="#dc2626" if i == 0 else "#f59e0b", mec="white", mew=1.2)
                    ax.annotate(str(i), (px, py), xytext=(5, 5), textcoords="offset points", fontsize=9, color="white",
                                bbox=dict(facecolor="black", alpha=0.6, pad=1))
                ax.set_xlim(vx0, vx1)
                ax.set_ylim(vy0, vy1)
                ax.set_xticks([])
                ax.set_yticks([])
            row[0].set_title(f"{c['start_names']} ({c['municipality']} {c['address']}, {int(float(c['start_m3'])):,} m³)\n"
                             f"0 = 初めの池、1〜{c['overflowed']} = あふれる池: {c['overflowed_names']}\n"
                             f"線の 100 m 以内の人口 {float(c['people_chain']):.0f} 人 (単独 {float(c['people_single']):.0f} 人)",
                             fontsize=9, loc="left")
            row[1].set_title(f"幅 {(x1 - x0) * math.cos(math.radians(34.3)) / 1000:.1f} km", fontsize=9, loc="right")
            row[2].set_title(f"池の近く (空中写真 z17、幅 {2 * half * math.cos(math.radians(34.3)):.0f} m)", fontsize=9, loc="right")
            picks.append(dict(box=box, start_node=c["start_node"], start_names=c["start_names"], municipality=c["municipality"],
                              address=c["address"], start_m3=c["start_m3"], overflowed=c["overflowed"],
                              overflowed_names=c["overflowed_names"], people_single=c["people_single"],
                              people_chain=c["people_chain"]))
        fig.suptitle(f"{box}: 左 地理院 空中写真 (seamlessphoto)、右 地理院 標準地図。赤 初めの池、橙 あふれる池 (台帳の点)、"
                     "青 流れの線と 100 m の帯。出典: 国土地理院", fontsize=10)
        fig.tight_layout(rect=(0, 0, 1, 0.985))
        fig.savefig(OUT / f"fig_visual_{box}.jpg", dpi=100, pil_kwargs=dict(quality=85))
        plt.close(fig)
        print(box, [p["start_names"] for p in picks if p["box"] == box], flush=True)
    with open(OUT / "visual_picks.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(picks[0]))
        w.writeheader()
        w.writerows(picks)


if __name__ == "__main__":
    main()
