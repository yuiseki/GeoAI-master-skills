"""Figure: outputs/ota_compare.png. Left: 大田区浸水実績図 at 田園調布 with the 町丁 boundaries of estat-boundary-2020
placed by the georeference of 07_ota_map.py (red). Right: dVV of orbit 46 (2019-10-13 vs the pre mean, main settings)
with the traced 2019-10-13 extent (blocks and streets, cyan) and the tokyo-flood-record polygons (black).

env -u GDAL_DATA -u PROJ_LIB -u PROJ_DATA uvx --with numpy --with matplotlib --with shapely --with pyproj --with pillow python scripts/08_ota_fig.py
"""
import json
import sys

import matplotlib
import numpy as np
import shapely
from PIL import Image
from pyproj import Transformer

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from common import ART, OUT, RAW, ROOT, UTM  # noqa: E402

sys.path.insert(0, str(ROOT / ".agents/skills/analysis-visualize/scripts"))
from cjk_font import use_cjk_font  # noqa: E402

SOURCE = ("大田区「大田区浸水実績図 (昭和60年〜令和7年)」、e-Stat 国勢調査 2020 境界データ (estat-boundary-2020)、"
          "Contains modified Copernicus Sentinel data 2019 (Planetary Computer sentinel-1-rtc)、東京都「浸水実績図データ」を加工して作成")
CROP = (480, 2160, 1440, 2880)  # map pixels of ota_map_overlay.png (07_ota_map.py)


def main():
    rec_fc = json.loads((RAW / "vectors/rec_2019.geojson").read_text(encoding="utf-8"))
    ext_fc = json.loads((ART / "ota_2019_extent_streets.geojson").read_text(encoding="utf-8"))
    to_utm = Transformer.from_crs("EPSG:4326", UTM, always_xy=True)

    def utm(g):
        return shapely.transform(shapely.from_geojson(json.dumps(g)),
                                 lambda xy: np.column_stack(to_utm.transform(xy[:, 0], xy[:, 1])))
    recs = [utm(f["geometry"]) for f in rec_fc["features"] if f["properties"]["munic"] in ("大田区", "世田谷区")]
    ext = utm(ext_fc["features"][0]["geometry"])
    aux = np.load(ART / "aux.npz")
    t = aux["transform"]
    rows, cols = aux["wc"].shape
    extent = (t[2], t[2] + cols * t[0], t[5] + rows * t[4], t[5])
    d = np.load(ART / "delta_o46.npz")["dvv"]
    d = np.where(aux["wc"] == 80, np.nan, d)
    g = json.loads((OUT / "ota_map.json").read_text(encoding="utf-8"))["georef"]
    ix_utm = Transformer.from_crs("EPSG:2451", UTM, always_xy=True)
    xs, ys = ix_utm.transform([g["X0"] + CROP[0] * g["m_per_px"], g["X0"] + CROP[2] * g["m_per_px"]],
                              [g["Y0"] - CROP[3] * g["m_per_px"], g["Y0"] - CROP[1] * g["m_per_px"]])  # same area as the left panel

    t1, t2 = "大田区浸水実績図 (田園調布)。茶色が令和元年 10 月 13 日、赤は町丁の境界", "雨の後と前の VV の差 (dB)。水色: 地図の令和元年の範囲 (道路を含む)、黒: 浸水実績図データの面"
    use_cjk_font(t1 + t2 + SOURCE + "0123456789-+.()、。dB")
    fig, axes = plt.subplots(1, 2, figsize=(15, 6.6))
    axes[0].imshow(Image.open(OUT / "ota_map_overlay.png"))
    axes[0].set_axis_off()
    axes[0].set_title(t1, fontsize=9)
    cm = plt.get_cmap("RdBu").copy()
    cm.set_bad("#d9d9d9")
    im = axes[1].imshow(d, extent=extent, cmap=cm, vmin=-8, vmax=8, interpolation="nearest")
    for g in [ext] + recs:
        for p in getattr(g, "geoms", [g]):
            c = "#00bcd4" if g is ext else "black"
            axes[1].plot(*np.asarray(p.exterior.coords).T, color=c, lw=1.6 if g is ext else 1.0)
    axes[1].set_xlim(xs)
    axes[1].set_ylim(ys)
    axes[1].set_xticks([])
    axes[1].set_yticks([])
    axes[1].set_title(t2, fontsize=9)
    fig.colorbar(im, ax=axes[1], fraction=0.035)
    fig.text(0.01, 0.01, SOURCE, fontsize=7)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(OUT / "ota_compare.png", dpi=110)
    plt.close(fig)


if __name__ == "__main__":
    main()
