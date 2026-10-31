"""The plan's visual check: for 10 Tokyo underpasses drawn at random (seed 0) among the matched ones, the roads
around the point, the road chosen as the one under it, and its profile on both DEMs.

uvx --from 'duckdb>=1.5.5' --with numpy --with shapely --with matplotlib --with pandas python scripts/06_check_fig.py

Writes outputs/check_profiles_tokyo.png and outputs/check_profiles_tokyo.json (the ids drawn and what the script
read for each). The figure is drawn from the OSM lines only (no imagery); bridges are dashed.
"""
import json
import math
from pathlib import Path

import duckdb
import matplotlib
import numpy as np
from shapely import from_wkb, from_wkt
from shapely.geometry import box

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from roadprofile import lonlat_to_merc  # noqa: E402

HERE = Path(__file__).resolve().parent
ART = HERE.parents[3] / "artifacts/_flood/underpass-ponding-exposure"
OUT = HERE.parent / "outputs"
R = 200  # m around the point


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--measures", default=str(ART / "measures.parquet"))
    ap.add_argument("--out", default=str(OUT / "check_profiles_tokyo.png"))
    a = ap.parse_args()
    profiles = Path(a.measures).with_name(Path(a.measures).name.replace("measures", "profiles"))
    plt.rcParams["font.family"] = ["Noto Sans CJK JP", "sans-serif"]
    c = duckdb.connect()
    c.execute("load spatial")
    m = c.execute(f"""select id, name, lon, lat, match_m, highway, tunnel, ambiguous, depth_5a_100, depth_10b_100,
            bottom_mix_100, dem_mix_100
        from '{a.measures}' join (select id, name from '{ART / 'raw/underpass.parquet'}') using (id)
        where pref = '東京都' and match_m <= 30""").fetchdf()
    pick = m.sample(10, random_state=0).sort_values("id")
    prof = c.execute(f"select * from '{profiles}' where id in (select unnest(?))",
                     [pick["id"].tolist()]).fetchdf().set_index("id")
    fig, axes = plt.subplots(10, 2, figsize=(11, 40), gridspec_kw={"width_ratios": [1, 1.4]})
    log = []
    for (_, r), (ax0, ax1) in zip(pick.iterrows(), axes):
        x, y = lonlat_to_merc(r.lon, r.lat)
        k = 1 / math.cos(math.radians(r.lat))
        bb = box(x - R * k, y - R * k, x + R * k, y + R * k)
        near = c.execute(f"""select highway, bridge, tunnel, st_aswkb(way) from '{ART / 'raw/roads.parquet'}'
            where bbox.xmin <= {bb.bounds[2]} and bbox.xmax >= {bb.bounds[0]}
              and bbox.ymin <= {bb.bounds[3]} and bbox.ymax >= {bb.bounds[1]}""").fetchall()
        for hw, br, tu, wkb in near:
            g = from_wkb(bytes(wkb)).intersection(bb)
            for part in getattr(g, "geoms", [g]):
                if part.is_empty or part.geom_type != "LineString":
                    continue
                xs, ys = part.xy
                ax0.plot((np.array(xs) - x) / k, (np.array(ys) - y) / k, color="#999",
                         lw=1.6 if br not in (None, "no") else 0.8, ls="--" if br not in (None, "no") else "-")
        p = prof.loc[r.id]
        for w in p["other_wkt"]:
            xs, ys = from_wkt(w).xy
            ax0.plot((np.array(xs) - x) / k, (np.array(ys) - y) / k, color="#3b7dd8", lw=1.2)
        xs, ys = from_wkt(p["chain_wkt"]).xy
        ax0.plot((np.array(xs) - x) / k, (np.array(ys) - y) / k, color="#d8452b", lw=2.2)
        ax0.plot(0, 0, marker="*", color="black", ms=12)
        ax0.set_xlim(-R, R)
        ax0.set_ylim(-R, R)
        ax0.set_aspect("equal")
        ax0.set_title(f"{r.id} {r['name']}", fontsize=9)
        ax0.tick_params(labelsize=7)
        s = np.array(p["s"])
        ax1.plot(s, p["e5a"], color="#d8452b", label="DEM5A")
        ax1.plot(s, p["e10b"], color="#3b7dd8", label="DEM10B")
        if "emt" in p and p["emt"] is not None:
            ax1.plot(s, p["emt"], color="#2a9d5c", lw=1.0, label="Mapterhorn z16")
        ax1.axvline(0, color="black", lw=0.6)
        ax1.axvspan(-30, 30, color="#eee")
        ax1.set_xlabel("点からの距離 (m、縦断に沿って)", fontsize=8)
        ax1.set_ylabel("標高 (m)", fontsize=8)
        ax1.tick_params(labelsize=7)
        d5 = "測れない" if r.depth_5a_100 is None or np.isnan(r.depth_5a_100) else f"{r.depth_5a_100:.2f} m"
        d10 = "測れない" if r.depth_10b_100 is None or np.isnan(r.depth_10b_100) else f"{r.depth_10b_100:.2f} m"
        ax1.set_title(f"{r.highway}、tunnel={bool(r.tunnel)}、曖昧={bool(r.ambiguous)}、対応 {r.match_m:.1f} m、"
                      f"深さ (L=100) 5A {d5} / 10B {d10}", fontsize=8)
        ax1.legend(fontsize=7)
        log.append({"id": r.id, "name": r["name"], "match_m": r.match_m, "highway": r.highway, "tunnel": bool(r.tunnel),
                    "ambiguous": bool(r.ambiguous), "roads_drawn": len(near)})
    fig.text(0.01, 0.995, "赤: 下を通る道路として選んだ線 (つないだ縦断)、青: 50 m 以内の他の候補、灰色の破線: 橋。"
             "右の灰色の帯は底を探す範囲 (±30 m)。出典: OpenStreetMap、国土地理院の標高タイル (Mapterhorn の線は © Mapterhorn、国土地理院の数値標高モデル)", fontsize=8, va="top")
    fig.tight_layout(rect=(0, 0, 1, 0.99))
    Path(a.out).parent.mkdir(exist_ok=True)
    fig.savefig(a.out, dpi=110)
    Path(a.out).with_suffix(".json").write_text(json.dumps(log, ensure_ascii=False, indent=1) + "\n")


if __name__ == "__main__":
    main()
