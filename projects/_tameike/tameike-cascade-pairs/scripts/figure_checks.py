"""The visual check of B1: for the nodes that enter the top 10 % only by cumulative storage, draw the DEM's shading,
the water surfaces upstream, and the flow paths from each upstream node down to the node. Takes the first 4, 3 and
3 such nodes by cumulative storage in kagawa, fukuyama and awaji. Writes outputs/fig_check_<box>.png and
outputs/fig_check_nodes.csv (the nodes drawn, the ponds upstream and the path lengths).

  env -u GDAL_DATA -u PROJ_LIB -u PROJ_DATA systemd-run --user --scope -q -p MemoryMax=8G -p MemorySwapMax=0 \
    -p CPUQuota=400% -- uvx --python 3.12 --with pyflwdir --with numpy --with rasterio --with pyproj --with scipy \
    --with duckdb --with matplotlib python scripts/figure_checks.py
"""

import csv
import json

import matplotlib
import numpy as np
from pyproj import Transformer

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402

from cascade_pairs import assign_nodes, fill_holes  # noqa: E402
from hydro import flow  # noqa: E402
from run_boxes import BOXES, DST, OUT, mosaic, ponds_in, to_utm, utm_grid  # noqa: E402

PICK = {"kagawa": 4, "fukuyama": 3, "awaji": 3}
for f in ("Noto Sans CJK JP", "IPAexGothic", "IPAGothic"):
    if any(f in x.name for x in font_manager.fontManager.ttflist):
        plt.rcParams["font.family"] = f
        break


def hillshade(z, cell):
    gy, gx = np.gradient(np.nan_to_num(z, nan=np.nanmin(z)), cell)
    slope = np.arctan(np.hypot(gx, gy))
    aspect = np.arctan2(-gx, gy)
    az, alt = np.radians(315), np.radians(45)
    return np.sin(alt) * np.cos(slope) + np.cos(alt) * np.sin(slope) * np.cos(az - aspect)


def main():
    out_rows = []
    for key, n_pick in PICK.items():
        box = BOXES[key]
        summary = json.loads((OUT / f"{key}_summary.json").read_text(encoding="utf-8"))
        nodes_csv = {int(r["node"]): r for r in csv.DictReader(open(OUT / f"{key}_nodes.csv", encoding="utf-8"))}
        top = [n for n in summary["top_only_in_cum"]["0.1"]]
        top.sort(key=lambda n: -float(nodes_csv[n]["cum_thousand_m3"]))
        picks = top[:n_pick]

        ponds = ponds_in(box)
        (h, w), tr = utm_grid(box, 5.0)
        arr, tr3857, _ = mosaic("dem5a", box)
        z = to_utm(arr, tr3857, ((h, w), tr))
        filled, labels = fill_holes(z)
        to = Transformer.from_crs("EPSG:4326", DST, always_xy=True)
        xs, ys = to.transform([p["lon"] for p in ponds], [p["lat"] for p in ponds])
        cols, rows = ~tr * (np.array(xs), np.array(ys))
        nodes, _, _ = assign_nodes(labels, np.floor(rows).astype(int), np.floor(cols).astype(int), max_cells=6)
        _, _, fd = flow(np.where(np.isnan(filled), -9999.0, filled), tr)
        upa = fd.upstream_area(unit="cell").ravel()
        ds = fd.idxs_ds
        down = {n: (int(r["down_node_5m"]) if r["down_node_5m"] else None) for n, r in nodes_csv.items()}

        def upstream_of(n):
            out, stack = [], [n]
            while stack:
                m = stack.pop()
                for k, d in down.items():
                    if d == m:
                        out.append(k)
                        stack.append(k)
            return out

        def outlet_path(n, stop):
            cells = np.flatnonzero(nodes.ravel() == n)
            cur = int(cells[np.argmax(upa[cells])])
            path = [cur]
            while ds[cur] != cur and nodes.ravel()[cur] != stop:
                cur = int(ds[cur])
                path.append(cur)
            return np.array(path)

        fig, axes = plt.subplots(1, len(picks), figsize=(5.2 * len(picks), 5.6))
        axes = np.atleast_1d(axes)
        for ax, n in zip(axes, picks):
            ups = upstream_of(n)
            paths = [outlet_path(u, n) for u in ups]
            allcells = np.concatenate([np.flatnonzero(nodes.ravel() == m) for m in ups + [n]] + paths)
            rr, cc = np.unravel_index(allcells, (h, w))
            pad = 40
            r0, r1 = max(rr.min() - pad, 0), min(rr.max() + pad, h)
            c0, c1 = max(cc.min() - pad, 0), min(cc.max() + pad, w)
            sub = (slice(r0, r1), slice(c0, c1))
            ax.imshow(hillshade(filled[sub], 5.0), cmap="gray", vmin=-0.2, vmax=1.0)
            up_mask = np.isin(nodes[sub], ups)
            ax.imshow(np.ma.masked_where(~up_mask, up_mask), cmap="Blues", vmin=0, vmax=1.3, alpha=0.8)
            me = nodes[sub] == n
            ax.imshow(np.ma.masked_where(~me, me), cmap="Reds", vmin=0, vmax=1.2, alpha=0.9)
            for p in paths:
                pr, pc = np.unravel_index(p, (h, w))
                ax.plot(pc - c0, pr - r0, color="#2563eb", linewidth=0.9)
            r = nodes_csv[n]
            ax.set_title(f"{r['names'][:16]} 自分 {float(r['own_thousand_m3']):g} 千m³\n上流を足す {float(r['cum_thousand_m3']):g} 千m³ (上流 {len(ups)} 池)", fontsize=9)
            ax.set_xticks([])
            ax.set_yticks([])
            ax.text(0.01, 0.01, f"{(c1 - c0) * 5 / 1000:.1f} km 幅", transform=ax.transAxes, fontsize=8, color="white",
                    bbox=dict(facecolor="black", alpha=0.5, pad=1))
            lens = [round((len(p) - 1) * 5.0) for p in paths]
            big = max(ups, key=lambda u: float(nodes_csv[u]["own_thousand_m3"])) if ups else None
            out_rows.append(dict(box=key, node=n, names=r["names"], own_thousand_m3=r["own_thousand_m3"],
                                 cum_thousand_m3=r["cum_thousand_m3"], upstream_nodes=len(ups),
                                 largest_upstream=nodes_csv[big]["names"] if big else "",
                                 largest_upstream_thousand_m3=nodes_csv[big]["own_thousand_m3"] if big else "",
                                 max_path_cells_x5_m=max(lens) if lens else 0, verdict=""))
        fig.suptitle(f"{key}: 上流の池 (青) と、そこから対象の池 (赤) への流れ。地理院 DEM5A の陰影", fontsize=10)
        fig.tight_layout()
        fig.savefig(OUT / f"fig_check_{key}.png", dpi=130)
        plt.close(fig)
        print(key, picks, flush=True)
    with open(OUT / "fig_check_nodes.csv", "w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=list(out_rows[0]))
        wr.writeheader()
        wr.writerows(out_rows)


if __name__ == "__main__":
    main()
