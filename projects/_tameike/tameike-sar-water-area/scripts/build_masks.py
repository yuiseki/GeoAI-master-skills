"""Pond outlines on the 10 m grid of each box: the DEM5A water holes that a ledger point falls in or within 30 m of
(the same matching as tameike-cascade-pairs), moved from 5 m to 10 m by a 2 x 2 majority (a 10 m pixel belongs to a
hole if at least 2 of its 4 cells do).

Writes artifacts/_tameike/tameike-sar-water-area/<box>_ponds10.tif (int32 pond id, 0 = none) and
outputs/<box>_ponds.csv (pond id, area from the 5 m cells, size class, pixels at 10 m and after a 1 pixel erosion,
the ledger ponds in it).

  env -u GDAL_DATA -u PROJ_LIB -u PROJ_DATA systemd-run --user --scope -q -p MemoryMax=8G -p MemorySwapMax=0 \
    -p CPUQuota=400% -- uvx --python 3.12 --with pyflwdir --with numpy --with rasterio --with pyproj --with scipy \
    --with duckdb python scripts/build_masks.py
"""

import csv
import sys
from pathlib import Path

import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.transform import from_origin
from scipy import ndimage

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "tameike-cascade-pairs/scripts"))
from cascade_pairs import REPO, assign_nodes, fill_holes  # noqa: E402
from run_boxes import BOXES, DST, mosaic, ponds_in, to_utm, utm_grid  # noqa: E402

PROJECT = HERE.parent
OUT = PROJECT / "outputs"
ART = REPO / "artifacts/_tameike/tameike-sar-water-area"
CLASSES = [(0.1, 0.5), (0.5, 1.0), (1.0, 5.0), (5.0, float("inf"))]


def size_class(ha):
    for lo, hi in CLASSES:
        if lo <= ha < hi:
            return f"{lo:g}-{hi:g}ha" if hi != float("inf") else f">={lo:g}ha"
    return "<0.1ha"


def grid10(box):
    (h5, w5), tr5 = utm_grid(box, 5.0)
    return (h5 // 2, w5 // 2), from_origin(tr5.c, tr5.f, 10.0, 10.0), (h5, w5), tr5


def build(key):
    box = BOXES[key]
    (h, w), tr10, (h5, w5), tr5 = grid10(box)
    ponds = ponds_in(box)
    arr, tr3857, _ = mosaic("dem5a", box)
    z5 = to_utm(arr, tr3857, ((h5, w5), tr5))
    _, labels = fill_holes(z5)
    to = Transformer.from_crs("EPSG:4326", DST, always_xy=True)
    xs, ys = to.transform([p["lon"] for p in ponds], [p["lat"] for p in ponds])
    cols, rows = ~tr5 * (np.array(xs), np.array(ys))
    nodes, node_of, how = assign_nodes(labels, np.floor(rows).astype(int), np.floor(cols).astype(int), max_cells=6)
    # keep only nodes that are holes (point footprints have no outline)
    hole_nodes = sorted({int(n) for n, hw in zip(node_of, how) if hw == "hole"})
    keep = np.isin(nodes, hole_nodes)
    nodes5 = np.where(keep, nodes, 0)[:h * 2, :w * 2]
    blocks = nodes5.reshape(h, 2, w, 2).transpose(0, 2, 1, 3).reshape(h, w, 4)
    first = blocks.max(axis=2)
    votes = (blocks == first[..., None]).sum(axis=2)
    p10 = np.where((first > 0) & (votes >= 2), first, 0).astype(np.int32)

    area5 = ndimage.sum_labels(np.ones_like(nodes5), nodes5, index=hole_nodes) * 25.0 / 1e4  # ha
    n10 = ndimage.sum_labels(np.ones_like(p10), p10, index=hole_nodes)
    inner = np.zeros_like(p10)
    for k, sl in enumerate(ndimage.find_objects(p10), start=1):
        if sl is None:
            continue
        sl = tuple(slice(max(s.start - 1, 0), s.stop + 1) for s in sl)
        m = ndimage.binary_erosion(p10[sl] == k, structure=np.ones((3, 3)))
        inner[sl][m] = k
    n_inner = ndimage.sum_labels(np.ones_like(inner), inner, index=hole_nodes)

    ART.mkdir(parents=True, exist_ok=True)
    for name, a in (("ponds10", p10), ("inner10", inner)):
        with rasterio.open(ART / f"{key}_{name}.tif", "w", driver="GTiff", height=h, width=w, count=1, dtype="int32",
                           crs=DST, transform=tr10, compress="deflate") as d:
            d.write(a, 1)
    members = {}
    for p, n, hw in zip(ponds, node_of, how):
        if hw == "hole":
            members.setdefault(int(n), []).append(p)
    rows_out = []
    for n, a, c10, ci in zip(hole_nodes, area5, n10, n_inner):
        ms = members[n]
        rows_out.append(dict(pond=n, area_ha=round(float(a), 3), size_class=size_class(a), pixels10=int(c10),
                             inner10=int(ci), ledger_ponds=len(ms), names="|".join(str(m["name"]) for m in ms),
                             source_rows="|".join(str(m["source_row"]) for m in ms)))
    with open(OUT / f"{key}_ponds.csv", "w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows_out[0]))
        wr.writeheader()
        wr.writerows(rows_out)
    print(key, "grid", (h, w), "ponds with outlines", len(rows_out),
          {c: sum(r["size_class"] == c for r in rows_out) for c in sorted({r["size_class"] for r in rows_out})}, flush=True)


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    for k in sys.argv[1:] or list(BOXES):
        build(k)
