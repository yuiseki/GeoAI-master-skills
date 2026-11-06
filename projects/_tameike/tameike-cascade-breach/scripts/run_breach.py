"""B0-B2 of EXPERIMENT_PLAN.md.

  env -u GDAL_DATA -u PROJ_LIB -u PROJ_DATA systemd-run --user --scope -q -p MemoryMax=8G -p MemorySwapMax=0 \
    -p CPUQuota=400% -- uvx --python 3.12 --with pyflwdir --with numpy --with rasterio --with pyproj --with scipy \
    --with duckdb python scripts/run_breach.py

Reads outputs/rain_annual_max.csv (fetch_rain.py), the DEM5A tiles cached by tameike-cascade-pairs, the ledger and
WorldPop 2020 100 m. Writes outputs/rain_gumbel.csv, outputs/<box>_ponds.csv, outputs/<box>_chains.csv and
outputs/summary.csv.
"""

import csv
import json
import math
import sys
from pathlib import Path

import numpy as np
import rasterio
from pyproj import Geod, Transformer
from rasterio.warp import Resampling, reproject
from rasterio.windows import from_bounds
from scipy import ndimage

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "tameike-cascade-pairs/scripts"))
from breach import froehlich, gev_lmoments, gev_quantile, gumbel_lmoments, gumbel_quantile, macdonald, run_chain  # noqa: E402
from cascade_pairs import assign_nodes, downstream_nodes, fill_holes  # noqa: E402
from hydro import flow  # noqa: E402
from run_boxes import BOXES, DST, PLACEHOLDER_STORAGE, mosaic, ponds_in, to_utm, utm_grid  # noqa: E402

PROJECT = HERE.parent
OUT = PROJECT / "outputs"
WORLDPOP = ("https://huggingface.co/datasets/yuiseki/worldpop-jp-2026-01/resolve/main/cog/GIS/Population/"
            "Global_2015_2030/R2025A/2020/JPN/v1/100m/constrained/jpn_pop_2020_CN_100m_R2025A_v1.tif")
MAIN_STATION = {"kagawa": "a0729", "fukuyama": "s47767", "awaji": "a0970"}
ALT_STATION = {"kagawa": "s47891", "fukuyama": "a0951", "awaji": "s47776"}
MIN_DAYS = 330
MIN_START_M3 = 1000.0
TAIL_M = 2000.0
BUFFER_CELLS = 20  # 100 m on the 5 m grid
CELL = 5.0


def rain_200():
    rows = list(csv.DictReader(open(OUT / "rain_annual_max.csv", encoding="utf-8")))
    out = {}
    for st in sorted({r["station"] for r in rows}):
        rs = [r for r in rows if r["station"] == st and int(r["days_ok"]) >= MIN_DAYS and r["max_1h_mm"]]
        x = [float(r["max_1h_mm"]) for r in rs]
        mu, beta = gumbel_lmoments(x)
        qg = gumbel_quantile(mu, beta, 200)
        xi, alpha, k = gev_lmoments(x)
        q = gev_quantile(xi, alpha, k, 200)  # GEV: changed after the Gumbel fit failed B0 at Fukuyama (plan change)
        out[st] = dict(station=st, name=rs[0]["name"], box=rs[0]["box"], role=rs[0]["role"], years=len(x),
                       observed_max_mm=max(x), gev_xi=round(xi, 3), gev_alpha=round(alpha, 3), gev_k=round(k, 4),
                       r200_mm_h=round(q, 1), r200_ge_observed_max=bool(q >= max(x)),
                       # the design guideline takes the largest of the 200-year value and the largest observed
                       # (plan change 2): this is the rainfall used
                       r_design_mm_h=round(max(q, max(x)), 1),
                       gumbel_mu=round(mu, 3), gumbel_beta=round(beta, 3), r200_gumbel_mm_h=round(qg, 1))
    with open(OUT / "rain_gumbel.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(next(iter(out.values()))))
        w.writeheader()
        w.writerows(out.values())
    return out


def population_5m(box, shape, tr):
    """People per 5 m cell: WorldPop's people per pixel divided by the pixel's area, times 25 m2."""
    geod = Geod(ellps="WGS84")
    with rasterio.open(WORLDPOP) as src:
        win = from_bounds(box[0] - 0.01, box[1] - 0.01, box[2] + 0.01, box[3] + 0.01, src.transform).round_offsets().round_lengths()
        pop = src.read(1, window=win).astype("float64")
        wtr = src.window_transform(win)
    pop[pop < 0] = 0.0
    dx, dy = wtr.a, -wtr.e
    lat = wtr.f - (np.arange(pop.shape[0]) + 0.5) * dy
    area = np.array([abs(geod.polygon_area_perimeter([0, dx, dx, 0], [la - dy / 2, la - dy / 2, la + dy / 2, la + dy / 2])[0])
                     for la in lat])
    dens = pop / area[:, None]
    out = np.zeros(shape, dtype="float64")
    reproject(dens, out, src_transform=wtr, src_crs="EPSG:4326", dst_transform=tr, dst_crs=DST,
              resampling=Resampling.nearest)
    return out * CELL * CELL, float(pop.sum())


def walk(ds, start, stop_cells=None, max_m=None, ncol=None):
    path, cur, dist = [start], start, 0.0
    while ds[cur] != cur:
        nxt = int(ds[cur])
        if nxt < 0:                         # NoData: the flow stops here
            break
        dist += CELL * (math.sqrt(2) if (nxt % ncol != cur % ncol and nxt // ncol != cur // ncol) else 1.0)
        cur = nxt
        path.append(cur)
        if stop_cells is not None and cur in stop_cells:
            break
        if max_m is not None and dist >= max_m:
            break
    return path


def exposed(path, pop, shape):
    r, c = np.unravel_index(np.array(path), shape)
    b = BUFFER_CELLS
    r0, r1, c0, c1 = max(r.min() - b, 0), min(r.max() + b + 1, shape[0]), max(c.min() - b, 0), min(c.max() + b + 1, shape[1])
    m = np.zeros((r1 - r0, c1 - c0), bool)
    m[r - r0, c - c0] = True
    yy, xx = np.ogrid[-b:b + 1, -b:b + 1]
    m = ndimage.binary_dilation(m, structure=(yy * yy + xx * xx) <= b * b)
    return float(pop[r0:r1, c0:c1][m].sum())


def run_box(key, rain, box=None, start_box=None, out=OUT, lines=False):
    """box: the area the flow is computed over (default the plan's box). start_box: only ponds with a ledger point
    inside it start a chain (default all). out: where the csv and figure go. lines: also write
    <key>_chain_lines.geojson, the flow line of each chain of 2 or more overflowed ponds (main setting)."""
    box = box or BOXES[key]
    ponds = ponds_in(box)
    (h, w), tr = utm_grid(box, CELL)
    arr, tr3857, _ = mosaic("dem5a", box)
    z = to_utm(arr, tr3857, ((h, w), tr))
    filled, labels = fill_holes(z)
    to = Transformer.from_crs("EPSG:4326", DST, always_xy=True)
    xs, ys = to.transform([p["lon"] for p in ponds], [p["lat"] for p in ponds])
    cols, rows = ~tr * (np.array(xs), np.array(ys))
    nodes, node_of, how = assign_nodes(labels, np.floor(rows).astype(int), np.floor(cols).astype(int), max_cells=6)
    _, _, fd = flow(np.where(np.isnan(filled), -9999.0, filled), tr)
    lengths = {}
    down = downstream_nodes(nodes, fd, lengths=lengths, cell=CELL)
    upa = fd.upstream_area(unit="km2").ravel()
    ds = fd.idxs_ds
    flat = nodes.ravel()
    idx = np.flatnonzero(flat)
    idx = idx[np.argsort(flat[idx], kind="stable")]
    ids, starts = np.unique(flat[idx], return_index=True)
    cells_of = {int(n): c for n, c in zip(ids, np.split(idx, starts[1:]))}
    outlet = {n: int(c[np.argmax(upa[c])]) for n, c in cells_of.items()}

    info = {}
    for p, n, hw in zip(ponds, node_of, how):
        if n == 0:
            continue
        d = info.setdefault(int(n), dict(members=[], v=0.0, h=None, hole=hw == "hole", big=-1.0))
        d["members"].append(p)
        v = p["storage_thousand_m3"]
        if v is not None and v != PLACEHOLDER_STORAGE:
            d["v"] += v * 1000.0
            if v > d["big"] and p["dam_height_m"]:
                d["big"], d["h"] = v, float(p["dam_height_m"])
    # a point pond whose 3 x 3 footprint was already taken by other ponds has no cells of its own: count and leave out
    no_cells = sorted(n for n in info if n not in cells_of)
    for n in no_cells:
        info.pop(n)
    pond_tab = {}
    for n, d in info.items():
        pond_tab[n] = dict(v=d["v"] or None, h=d["h"] if d["h"] and d["h"] > 0 else None,
                           s=len(cells_of[n]) * CELL * CELL if d["hole"] else None,
                           a=float(upa[outlet[n]]), dist=lengths.get(n))
    pop, pop_window_total = population_5m(box, (h, w), tr)

    starts_ = [n for n, p in pond_tab.items() if p["v"] and p["v"] >= MIN_START_M3 and p["h"]]
    if start_box:
        inside = lambda m: start_box[0] <= m["lon"] <= start_box[2] and start_box[1] <= m["lat"] <= start_box[3]
        starts_ = [n for n in starts_ if any(inside(m) for m in info[n]["members"])]
    r_main = rain[MAIN_STATION[key]]["r_design_mm_h"]
    r_alt = rain[ALT_STATION[key]]["r_design_mm_h"]
    base = dict(f=0.7, r=r_main, margin=1.2, freeboard=1.0, max_dist=1000.0, peak=froehlich)
    variants = {"main": {}, "f_0.5": dict(f=0.5), "f_0.9": dict(f=0.9), "r_alt_station": dict(r=r_alt),
                "r_x1.5": dict(r=r_main * 1.5), "r_gumbel": dict(r=rain[MAIN_STATION[key]]["r200_gumbel_mm_h"]),
                "r_gev_only": dict(r=rain[MAIN_STATION[key]]["r200_mm_h"]), "margin_1.0": dict(margin=1.0), "margin_0.5": dict(margin=0.5),
                "freeboard_0.5": dict(freeboard=0.5), "freeboard_2.0": dict(freeboard=2.0),
                "dist_500": dict(max_dist=500.0), "dist_2000": dict(max_dist=2000.0), "macdonald": dict(peak=macdonald)}
    ncol = w
    cache = {}

    def chain_path(start, failed):
        # one unbroken flow line: from the start's outlet down through each overflowed pond to the last one's
        # outlet, then 2 km further (so the chain's line always holds the single breach's first part)
        path = [outlet[start]]
        if failed:
            path = walk(ds, outlet[start], stop_cells={outlet[failed[-1]]}, ncol=ncol)
        return path + walk(ds, path[-1], max_m=TAIL_M, ncol=ncol)[1:]

    def chain_exposure(start, failed):
        k = (start, tuple(failed))
        if k not in cache:
            cache[k] = exposed(chain_path(start, failed), pop, (h, w))
        return cache[k]

    def end_at_edge(start, failed):
        # where the flow below the last overflowed pond (or the start) ends: on the border of the grid or not
        end = walk(ds, outlet[failed[-1] if failed else start], ncol=ncol)[-1]
        r, c = divmod(end, ncol)
        return r in (0, h - 1) or c in (0, w - 1)

    summary, chain_rows = [], []
    for name, change in variants.items():
        params = {**base, **change}
        n1 = n2 = n2p = 0
        for s in starts_:
            failed, why = run_chain(s, down, pond_tab, params)
            if len(failed) >= 1:
                n1 += 1
            if len(failed) >= 2:
                n2 += 1
                ppl = chain_exposure(s, failed)
                if ppl >= 1.0:
                    n2p += 1
            if name == "main":
                single = chain_exposure(s, [])
                ppl = chain_exposure(s, failed) if failed else single
                names = lambda n: "|".join(str(m["name"]) for m in info[n]["members"])
                rows_of = lambda n: "|".join(str(m["source_row"]) for m in info[n]["members"])
                chain_rows.append(dict(box=key, start=s, start_names=names(s), start_m3=round(pond_tab[s]["v"]),
                                       start_h_m=pond_tab[s]["h"], overflowed=len(failed),
                                       overflowed_names=" > ".join(names(n) for n in failed),
                                       overflowed_m3=" > ".join(str(round(pond_tab[n]["v"] or 0)) for n in failed),
                                       stop=why, people_single=round(single, 1), people_chain=round(ppl, 1),
                                       end_at_edge=end_at_edge(s, failed),
                                       start_source_rows=rows_of(s),
                                       overflowed_source_rows=" > ".join(rows_of(n) for n in failed),
                                       _failed=failed))
        summary.append(dict(box=key, variant=name, r_mm_h=params["r"], nodes=len(pond_tab), nodes_without_cells=len(no_cells),
                            starts=len(starts_), chains_1plus=n1,
                            chains_2plus=n2, chains_2plus_people=n2p,
                            verdict="ありそう" if n2p >= 1 else "なさそう"))
    draw_top(key, chain_rows, cells_of, outlet, ds, filled, pop, (h, w), ncol, out=out)
    if lines:
        back = Transformer.from_crs(DST, "EPSG:4326", always_xy=True)
        feats = []
        for r in chain_rows:
            if r["overflowed"] < 2:
                continue
            rr, cc = np.unravel_index(np.array(chain_path(r["start"], r["_failed"])), (h, w))
            x, y = tr * (cc + 0.5, rr + 0.5)
            lon, lat = back.transform(x, y)
            feats.append(dict(type="Feature", properties=dict(start=r["start"], start_source_rows=r["start_source_rows"],
                                                              people_chain=r["people_chain"]),
                              geometry=dict(type="LineString", coordinates=[[round(a, 6), round(b, 6)] for a, b in zip(lon, lat)])))
        (out / f"{key}_chain_lines.geojson").write_text(json.dumps(dict(type="FeatureCollection", features=feats)), encoding="utf-8")
    pond_rows = [dict(node=n, names="|".join(str(m["name"]) for m in info[n]["members"]),
                      storage_m3=round(p["v"] or 0), dam_height_m=p["h"] or "", surface_m2=p["s"] or "",
                      catchment_km2=round(p["a"], 4), down_node=down.get(n) or "",
                      to_down_m=round(p["dist"]) if p["dist"] is not None else "",
                      source_rows="|".join(str(m["source_row"]) for m in info[n]["members"]))
                 for n, p in sorted(pond_tab.items())]
    write(out / f"{key}_ponds.csv", pond_rows)
    write(out / f"{key}_chains.csv", [{k: v for k, v in r.items() if k != "_failed"}
                                      for r in sorted(chain_rows, key=lambda r: (-r["overflowed"], -r["people_chain"]))])
    print(key, "starts", len(starts_), "nodes", len(pond_tab), "nodes without cells", len(no_cells),
          "worldpop in window", round(pop_window_total), flush=True)
    for s in summary:
        print("  ", s, flush=True)
    return summary


def draw_top(key, chain_rows, cells_of, outlet, ds, filled, pop, shape, ncol, n_top=3, out=OUT):
    """outputs/fig_chains_<box>.png: the 3 chains of 2 or more overflowed ponds with the most people near the line."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    for fam in ("Noto Sans CJK JP", "Noto Sans CJK TC"):
        if any(fam == x.name for x in font_manager.fontManager.ttflist):
            plt.rcParams["font.family"] = fam
            break
    top = sorted([r for r in chain_rows if r["overflowed"] >= 2], key=lambda r: -r["people_chain"])[:n_top]
    if not top:
        return
    node_of_name = {}
    fig, axes = plt.subplots(1, len(top), figsize=(5.4 * len(top), 5.8))
    for ax, r in zip(np.atleast_1d(axes), top):
        start = r["start"]
        failed = [int(x) for x in r["_failed"]]
        path = walk(ds, outlet[start], stop_cells={outlet[failed[-1]]}, ncol=ncol)
        path += walk(ds, path[-1], max_m=TAIL_M, ncol=ncol)[1:]
        cells = np.concatenate([cells_of[start]] + [cells_of[n] for n in failed] + [np.array(path)])
        rr, cc = np.unravel_index(cells, shape)
        pad = 40
        r0, r1 = max(rr.min() - pad, 0), min(rr.max() + pad, shape[0])
        c0, c1 = max(cc.min() - pad, 0), min(cc.max() + pad, shape[1])
        sub = (slice(r0, r1), slice(c0, c1))
        zz = np.nan_to_num(filled[sub], nan=np.nanmin(filled[sub]))
        gy, gx = np.gradient(zz, CELL)
        slope, aspect = np.arctan(np.hypot(gx, gy)), np.arctan2(-gx, gy)
        shade = np.sin(np.radians(45)) * np.cos(slope) + np.cos(np.radians(45)) * np.sin(slope) * np.cos(np.radians(315) - aspect)
        ax.imshow(shade, cmap="gray", vmin=-0.2, vmax=1.0)
        pp = pop[sub] / (CELL * CELL) * 1e4
        ax.imshow(np.ma.masked_where(pp < 1, pp), cmap="YlOrRd", alpha=0.45, vmin=0, vmax=60)
        for n, color in [(start, "#dc2626")] + [(n, "#f59e0b") for n in failed]:
            m = np.zeros(shape, bool).ravel()
            m[cells_of[n]] = True
            m = m.reshape(shape)[sub]
            ax.imshow(np.ma.masked_where(~m, m), cmap=matplotlib.colors.ListedColormap([color]), alpha=0.95)
        pr, pc = np.unravel_index(np.array(path), shape)
        ax.plot(pc - c0, pr - r0, color="#1d4ed8", linewidth=1.0)
        ax.set_title(f"{r['start_names'][:12]} ({r['start_m3']:,} m³) から {r['overflowed']} 池\n"
                     f"線の 100 m 以内の人口 {r['people_chain']:.0f} 人 (単独なら {r['people_single']:.0f} 人)", fontsize=9)
        ax.set_xticks([])
        ax.set_yticks([])
        ax.text(0.01, 0.01, f"{(c1 - c0) * CELL / 1000:.1f} km 幅", transform=ax.transAxes, fontsize=8, color="white",
                bbox=dict(facecolor="black", alpha=0.5, pad=1))
    fig.suptitle(f"{key}: 初めに決壊する池 (赤)、次々にあふれる池 (橙)、流れの線 (青)、人口 (WorldPop 2020、薄い赤)。"
                 "陰影は地理院 DEM5A", fontsize=9)
    fig.tight_layout()
    fig.savefig(out / f"fig_chains_{key}.png", dpi=130)
    plt.close(fig)


def write(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def main():
    rain = rain_200()
    for r in rain.values():
        print(r, flush=True)
    # B0's rule (200-year value >= observed maximum) was dropped by plan change 2: in 50 years the largest value
    # exceeds the 200-year value with probability 1 - (1 - 1/200)^50, about 0.22
    summary = []
    for key in sys.argv[1:] or list(BOXES):
        summary += run_box(key, rain)
    write(OUT / "summary.csv", summary)


if __name__ == "__main__":
    main()
