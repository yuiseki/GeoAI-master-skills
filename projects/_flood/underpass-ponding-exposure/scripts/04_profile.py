"""Measure every underpass by the plan: the road under it, the dip on its profile, the surface dip, the catchment.

uvx --from 'duckdb>=1.5.5' --with numpy --with shapely --with pyarrow python scripts/04_profile.py [--max-lon LON]

Writes artifacts/_flood/underpass-ponding-exposure/measures.parquet (one row per underpass) and profiles.parquet
(the sampled profiles of the main road, both DEMs, for the figures and checks). --max-lon limits the run to the
points west of a longitude (for trying the script while tiles are still being fetched). --chain vertices (the
exploratory rule added after the results) writes to --out measures_vertices.parquet.
"""
import argparse
import math
from pathlib import Path

import duckdb
import numpy as np
from shapely import STRtree, from_wkb
from shapely.geometry import Point

from dem import Tiles, drain_to, global_pixel
from roadprofile import (ambiguous, build_chain, depth, eligible, lonlat_to_merc, merc_to_lonlat, node_index, samples,
                         surface_depth)

HERE = Path(__file__).resolve().parent
ART = HERE.parents[3] / "artifacts/_flood/underpass-ponding-exposure"
MATCH_MAX = 50.0          # m; the nearest line is kept up to this distance, the plan's 30 m is applied downstream
LS = (50, 100, 200)
CATCH_R = 300.0           # m, half side of the catchment window
CATCH_PIT = 15.0          # m from the bottom within which a stopping pixel counts
DEMS = {"5a": "dem5a", "10b": "dem"}


def load_roads(all_vertices=False):
    c = duckdb.connect()
    c.execute("load spatial")
    rows = c.execute(f"""select osm_id, highway, bridge, tunnel, layer, covered, st_aswkb(way)
        from '{ART / 'raw/roads.parquet'}'""").fetchall()
    keep = [r for r in rows if eligible(r[1], r[2], r[4])]
    lines = list(from_wkb([bytes(r[6]) for r in keep]))
    meta = [r[:6] for r in keep]
    return lines, meta, node_index(lines, all_vertices), len(rows)


def catchment(tiles, lon, lat, blon, blat):
    win, m, r, c = tiles.window(lon, lat, CATCH_R)
    if np.isnan(win).mean() > 0.5:
        return None
    d = drain_to(win)
    gx, gy = global_pixel(lon, lat, tiles.z)
    bx, by = global_pixel(blon, blat, tiles.z)
    br, bc = r + int(by) - int(gy), c + int(bx) - int(gx)
    yy, xx = np.indices(win.shape)
    pits = np.flatnonzero((np.hypot(yy - br, xx - bc) * m <= CATCH_PIT).ravel())
    return float(np.isin(d, pits).sum() * m * m)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-lon", type=float, default=None)
    ap.add_argument("--out", default=str(ART / "measures.parquet"))
    ap.add_argument("--chain", choices=["ends", "vertices"], default="ends",
                    help="ends: the plan's rule; vertices: also follow lines through a node (exploratory)")
    a = ap.parse_args()
    lines, meta, ends, n_roads = load_roads(a.chain == "vertices")
    tree = STRtree(lines)
    tiles = {k: Tiles(ART / "dem", v) for k, v in DEMS.items()}
    q = f"select id, pref, block, lon, lat from '{ART / 'raw/underpass.parquet'}'"
    if a.max_lon:
        q += f" where lon < {a.max_lon}"
    pts = duckdb.sql(q + " order by id").fetchall()
    print("roads", n_roads, "eligible", len(lines), "points", len(pts), flush=True)
    out, prof = [], []
    for n, (pid, pref, block, lon, lat) in enumerate(pts):
        scale = math.cos(math.radians(lat))
        P = Point(*lonlat_to_merc(lon, lat))
        row = {"id": pid, "pref": pref, "block": block, "lon": lon, "lat": lat}
        for k, key in DEMS.items():
            win, m, r, c = tiles[k].window(lon, lat, 55)
            row[f"surface_{k}"] = surface_depth(win, m, r, c)
        cand = tree.query(P.buffer(MATCH_MAX / scale))
        cand = [i for i in cand if lines[i].distance(P) * scale <= MATCH_MAX]
        if not cand:
            row["match_m"] = None
            out.append(row)
            continue
        cand.sort(key=lambda i: lines[i].distance(P))
        k0 = cand[0]
        row.update(match_m=lines[k0].distance(P) * scale, osm_id=meta[k0][0], highway=meta[k0][1],
                   tunnel=meta[k0][3] is not None and meta[k0][3] != "no",
                   covered=meta[k0][5] is not None and meta[k0][5] != "no",
                   ambiguous=ambiguous(P, [lines[i] for i in cand], 0, scale))
        chain, used = build_chain(k0, lines, ends, max(LS) * 1.2 / scale)
        smp, left, right = samples(chain, P, scale, max(LS))
        row.update(chain_lines=len(used), left_m=left, right_m=right,
                   chain_tunnel=any(meta[i][3] not in (None, "no") for i in used))
        s = np.array([t[0] for t in smp])
        lonlat = [merc_to_lonlat(x, y) for _, x, y in smp]
        elev = {}
        for k in DEMS:
            elev[k] = np.array([tiles[k].bilinear(*global_pixel(lo, la, tiles[k].z)) for lo, la in lonlat])
            for L in LS:
                d, sb, ok = depth(s, elev[k], L)
                row[f"depth_{k}_{L}"], row[f"bottom_{k}_{L}"], row[f"ok_{k}_{L}"] = d, sb, ok
                d, sb, _ = depth(s, elev[k], L, bottom_within=L)
                row[f"depthw_{k}_{L}"], row[f"bottomw_{k}_{L}"] = d, sb
        for L in LS:
            use = "5a" if row[f"ok_5a_{L}"] else "10b"
            row[f"dem_mix_{L}"] = use
            for f in ("depth", "bottom", "ok", "depthw", "bottomw"):
                row[f"{f}_mix_{L}"] = row[f"{f}_{use}_{L}"]
        row["surface_mix"] = row["surface_5a"] if row["surface_5a"] is not None else row["surface_10b"]
        if row["ok_mix_100"]:
            k = row["dem_mix_100"]
            ib = int(np.argmin(np.abs(s - row["bottom_mix_100"])))
            row["catch_m2"] = catchment(tiles[k], lon, lat, *lonlat[ib])
        prof.append({"id": pid, "s": s.tolist(), "e5a": elev["5a"].tolist(), "e10b": elev["10b"].tolist(),
                     "chain_wkt": chain.wkt, "other_wkt": [lines[i].wkt for i in cand[1:]]})
        out.append(row)
        if n % 250 == 0:
            print(n, len(pts), flush=True)
            for t in tiles.values():
                t.cache.clear()
    import pyarrow as pa
    import pyarrow.parquet as pq
    pq.write_table(pa.Table.from_pylist(out), a.out)
    pq.write_table(pa.Table.from_pylist(prof), str(Path(a.out).with_name(Path(a.out).stem.replace("measures", "profiles") + ".parquet")))
    print("wrote", len(out), flush=True)


if __name__ == "__main__":
    main()
