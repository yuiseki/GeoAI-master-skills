"""Figures for 田園調布.

env -u GDAL_DATA -u PROJ_LIB -u PROJ_DATA uvx --with numpy --with matplotlib --with shapely --with pyproj --with pillow --with duckdb==1.5.5 python scripts/08_ota_fig.py

- outputs/ota_sar.png (in the repository): dVV of orbit 46 (2019-10-13 vs the pre mean, main settings) over the area of
  the map crop, with the tokyo-flood-record polygons (black) and the 町丁 boundaries of estat-boundary-2020 (grey).
  Nothing from the ward's map is drawn.
- artifacts/.../local_only/ota_compare.png (kept out of the repository): the ward's map crop next to the same SAR panel
  with the extent traced from the map (cyan). The ward's terms (https://www.city.ota.tokyo.jp/aboutweb/policy.html)
  forbid reuse of its material without permission, so this one is for checking only.
"""
import json
import sys

import duckdb
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

SOURCE = ("Contains modified Copernicus Sentinel data 2019 (Planetary Computer sentinel-1-rtc)、東京都「浸水実績図データ」、"
          "e-Stat 国勢調査 2020 境界データ (estat-boundary-2020) を加工して作成")
CROP = (480, 2160, 1440, 2880)  # map pixels of the crop checked by eye (07_ota_map.py)


def main():
    to_utm = Transformer.from_crs("EPSG:4326", UTM, always_xy=True)

    def utm(g):
        return shapely.transform(g, lambda xy: np.column_stack(to_utm.transform(xy[:, 0], xy[:, 1])))
    rec_fc = json.loads((RAW / "vectors/rec_2019.geojson").read_text(encoding="utf-8"))
    recs = [utm(shapely.from_geojson(json.dumps(f["geometry"]))) for f in rec_fc["features"]
            if f["properties"]["munic"] in ("大田区", "世田谷区")]
    ext = utm(shapely.from_geojson(json.dumps(json.loads((ART / "ota_2019_extent_streets.geojson").read_text(
        encoding="utf-8"))["features"][0]["geometry"])))
    c = duckdb.connect()
    c.sql("INSTALL spatial; LOAD spatial")
    est = [utm(shapely.from_wkb(bytes(r[0]))) for r in c.sql(
        f"select ST_AsWKB(ST_GeomFromWKB(geometry)) from '{RAW / 'estat/parquet/r2ka13.parquet'}' "
        "where CITY_NAME in ('大田区', '世田谷区')").fetchall()]
    aux = np.load(ART / "aux.npz")
    t = aux["transform"]
    rows, cols = aux["wc"].shape
    extent = (t[2], t[2] + cols * t[0], t[5] + rows * t[4], t[5])
    d = np.where(aux["wc"] == 80, np.nan, np.load(ART / "delta_o46.npz")["dvv"])
    g = json.loads((OUT / "ota_map.json").read_text(encoding="utf-8"))["georef"]
    ix_utm = Transformer.from_crs("EPSG:2451", UTM, always_xy=True)
    xs, ys = ix_utm.transform([g["X0"] + CROP[0] * g["m_per_px"], g["X0"] + CROP[2] * g["m_per_px"]],
                              [g["Y0"] - CROP[3] * g["m_per_px"], g["Y0"] - CROP[1] * g["m_per_px"]])

    def sar_panel(ax, title, with_ext):
        cm = plt.get_cmap("RdBu").copy()
        cm.set_bad("#d9d9d9")
        im = ax.imshow(d, extent=extent, cmap=cm, vmin=-8, vmax=8, interpolation="nearest")
        for e in est:
            for p in getattr(e, "geoms", [e]):
                ax.plot(*np.asarray(p.exterior.coords).T, color="#555555", lw=0.6, ls="--")
        for r in recs:
            for p in getattr(r, "geoms", [r]):
                ax.plot(*np.asarray(p.exterior.coords).T, color="black", lw=1.0)
        if with_ext:
            for p in getattr(ext, "geoms", [ext]):
                ax.plot(*np.asarray(p.exterior.coords).T, color="#00bcd4", lw=1.6)
        ax.set_xlim(xs)
        ax.set_ylim(ys)
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_title(title, fontsize=9)
        return im

    t1 = "田園調布の雨の後と前の VV の差 (dB)。黒: 浸水実績図データの面、灰の破線: 町丁の境界 (国勢調査 2020)"
    use_cjk_font(t1 + SOURCE + "0123456789-+.()、。dB水色地図からなぞった令和元年の範囲確認用大田区浸水実績図リポジトリに入れない")
    fig, ax = plt.subplots(figsize=(9, 6.6))
    im = sar_panel(ax, t1, False)
    fig.colorbar(im, ax=ax, fraction=0.035)
    fig.text(0.01, 0.01, SOURCE, fontsize=6)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(OUT / "ota_sar.png", dpi=110)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(15, 6.6))
    axes[0].imshow(Image.open(ART / "local_only/ota_map_overlay.png"))
    axes[0].set_axis_off()
    axes[0].set_title("大田区浸水実績図 (確認用、リポジトリに入れない)", fontsize=9)
    im = sar_panel(axes[1], "水色: 地図からなぞった令和元年の範囲", True)
    fig.colorbar(im, ax=axes[1], fraction=0.035)
    fig.tight_layout()
    fig.savefig(ART / "local_only/ota_compare.png", dpi=110)
    plt.close(fig)


if __name__ == "__main__":
    main()
