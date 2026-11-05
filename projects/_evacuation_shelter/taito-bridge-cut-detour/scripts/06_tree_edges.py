"""Edges of the main run's shortest-path forest: how many Taito-ku origins route over each walkable way.

systemd-run --user --scope -q -p MemoryMax=8G -p MemorySwapMax=0 -p CPUQuota=400% -- \
  uvx --from 'duckdb>=1.5.5' --with numpy --with scipy --with shapely --with pyproj --with pyarrow --with pandas \
  python scripts/06_tree_edges.py

Writes artifacts/.../main/tree_edges.parquet (one row per walkable way within 600 m of Taito-ku: n_origins, the
origins whose route to the nearest flood site uses at least one segment of the way; lengthening, whether the way
belongs to a bridge structure whose cut lengthens some origin's route; name; geometry in EPSG:6677),
artifacts/.../main/sites_xy.csv (flood sites, x and y in EPSG:6677) and outputs/main/tree_edges_summary.json.
Same graph, sites, origins and bridge groups as 02_run.py --variant main.
"""
import importlib
import json
import math
import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import shapely

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
run = importlib.import_module("02_run")
import cutdetour as cd  # noqa: E402

VIEW_M = 600.0


def main():
    cfg = run.MAIN
    raw = run.ART / f"raw_b{cfg['buffer_m']}"
    c = duckdb.connect()
    c.execute("load spatial")
    lines = c.execute(f"select * exclude (g), st_aswkb(g) wkb from '{raw}/lines.parquet'").df()
    lines["geom"] = shapely.from_wkb(lines.pop("wkb").map(bytes))
    water = shapely.from_wkb(c.execute(f"select st_aswkb(g) wkb from '{raw}/water.parquet'").df().wkb.map(bytes))
    taito = shapely.from_wkb(bytes(c.execute(f"select st_aswkb(g) from '{raw}/taito.parquet'").fetchall()[0][0]))
    sites = c.execute(f"select * exclude (g), st_x(g) x, st_y(g) y from '{raw}/sites.parquet'").df()

    walk = lines[[run.walkable(r, cfg["corridor"]) for r in lines.itertuples()]].reset_index(drop=True)
    g = cd.build_graph(walk.geom.values)
    is_bridge = walk.bridge.map(run.is_set).values
    struct_idx = np.flatnonzero(is_bridge)
    groups = cd.cluster_lines(walk.geom.values, struct_idx, cfg["cluster_m"])
    hz = sites[sites[cfg["hazard"]].fillna(False)]
    ground = cd.ground_nodes(g, struct_idx, min_component_m=run.GROUND_MIN_M)
    src, _ = cd.snap(g, hz[["x", "y"]].values, allowed=ground)

    o = pd.read_parquet(run.ART / "main" / "origins.parquet")
    o = o[o.used]
    onode, _ = cd.snap(g, o[["x", "y"]].values, allowed=ground)
    _, pred, _ = cd.multi_source(g, src, predecessors=True)

    best = {}
    for k in range(len(g.u)):
        a, b = sorted((int(g.u[k]), int(g.v[k])))
        if (a, b) not in best or g.length[k] < g.length[best[(a, b)]]:
            best[(a, b)] = k
    n_origins = np.zeros(len(walk), int)
    for x in onode:  # walk each origin's route; a way counts once per origin
        seen = set()
        x = int(x)
        while pred[x] >= 0:
            p = int(pred[x])
            seen.add(int(g.line[best[tuple(sorted((p, x)))]]))
            x = p
        for li in seen:
            n_origins[li] += 1

    st = pd.read_csv(HERE.parent / "outputs" / "main" / "structures.csv")
    lengthening_groups = set(st.struct)
    lengthening = np.array([groups.get(i, -1) in lengthening_groups for i in range(len(walk))])
    view = taito.buffer(VIEW_M)
    keep = shapely.intersects(walk.geom.values, view)
    out = pd.DataFrame({"n_origins": n_origins, "lengthening": lengthening,
                        "name": [n if isinstance(n, str) and n else None for n in walk.name.values],
                        "wkb": shapely.to_wkb(walk.geom.values)})[keep]
    art = run.ART / "main"
    c.register("t", out)
    c.execute(f"copy (select n_origins, lengthening, name, st_geomfromwkb(wkb) geometry from t) "
              f"to '{art / 'tree_edges.parquet'}' (format parquet)")
    in_view = hz[[view.contains(shapely.Point(x, y)) for x, y in zip(hz.x, hz.y)]]
    in_view[["x", "y"]].to_csv(art / "sites_xy.csv", index=False, encoding="utf-8")
    summary = dict(ways_in_view=int(keep.sum()), ways_on_routes=int((n_origins[keep] > 0).sum()),
                   n_origins_max=int(n_origins.max()), origins=int(len(onode)),
                   lengthening_ways=int(lengthening[keep].sum()), sites_in_view=int(len(in_view)), view_m=VIEW_M)
    (HERE.parent / "outputs" / "main" / "tree_edges_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
