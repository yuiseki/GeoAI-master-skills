"""Why the road chain of a matched underpass stops short of 50 m on a side (exploratory, after the results).

uvx --from 'duckdb>=1.5.5' --with numpy --with shapely --with pyarrow python scripts/07_chain_stops.py --chain ends|vertices

For each matched point (30 m) with a side shorter than 50 m, rebuilds the chain as 04_profile.py does and looks at
the node where the short side ends:
- turn: an eligible line continues there but turns by more than CHAIN_ANGLE;
- through_vertex: an eligible line passes through the node at a middle vertex (followed only with --chain vertices);
- bridge: only a bridge (or a line above ground) continues there;
- other_class: only lines of other highway classes (footway, track ...) continue there;
- dead_end: no other line touches the node.
Writes outputs/chain_stops_<chain>.json.
"""
import argparse
import collections
import importlib.util
import json
import math
from pathlib import Path

import duckdb
import numpy as np
from shapely import STRtree, from_wkb
from shapely.geometry import Point

from roadprofile import CHAIN_ANGLE, _out_dir, angle_between, build_chain, eligible, lonlat_to_merc

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("p4", HERE / "04_profile.py")
p4 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p4)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chain", choices=["ends", "vertices"], default="ends")
    a = ap.parse_args()
    lines, meta, nodes, _ = p4.load_roads(a.chain == "vertices")
    tree = STRtree(lines)
    rows = duckdb.sql(f"select highway, bridge, layer, st_aswkb(way) from '{p4.ART / 'raw/roads.parquet'}'").fetchall()
    every = list(from_wkb([bytes(r[3]) for r in rows]))
    every_tree = STRtree(every)
    measures = p4.ART / ("measures.parquet" if a.chain == "ends" else "measures_vertices.parquet")
    pts = duckdb.sql(f"""select id, lon, lat from '{measures}'
        where match_m <= 30 and (left_m < 50 or right_m < 50) order by id""").fetchall()
    reasons = collections.Counter()
    for pid, lon, lat in pts:
        scale = math.cos(math.radians(lat))
        P = Point(*lonlat_to_merc(lon, lat))
        cand = [i for i in tree.query(P.buffer(30 / scale)) if lines[i].distance(P) * scale <= 30]
        k0 = min(cand, key=lambda i: lines[i].distance(P))
        chain, used = build_chain(k0, lines, nodes, max(p4.LS) * 1.2 / scale)
        coords = list(chain.coords)
        if chain.project(P) * scale < 50:
            coords = coords[::-1]
        end, din = Point(coords[-1]), _out_dir(coords)
        near = [i for i in tree.query(end.buffer(0.01)) if i not in used and lines[i].distance(end) < 0.01]
        if near:
            angs = []
            for i in near:
                c = list(lines[i].coords)
                j = int(np.argmin([Point(x).distance(end) for x in c]))
                for part in (c[j:], c[j::-1]):
                    if len(part) >= 2:
                        d = np.array(part[1]) - np.array(part[0])
                        angs.append(angle_between(din, d / (np.hypot(*d) or 1), undirected=False))
            touches_end = any(tuple(lines[i].coords[0]) == end.coords[0] or tuple(lines[i].coords[-1]) == end.coords[0]
                              for i in near)
            reasons["turn" if touches_end or min(angs) > CHAIN_ANGLE else "through_vertex"] += 1
            continue
        other = [i for i in every_tree.query(end.buffer(0.01)) if every[i].distance(end) < 0.01]
        other = [rows[i] for i in other if not any(every[i].equals(lines[u]) for u in used)]
        if not other:
            reasons["dead_end"] += 1
        elif any(r[1] not in (None, "no") or not eligible(r[0], None, r[2]) and r[0] in p4_road_classes() for r in other):
            reasons["bridge"] += 1
        else:
            reasons["other_class"] += 1
    out = {"chain": a.chain, "short_points": len(pts), "reasons": dict(reasons.most_common())}
    (HERE.parent / f"outputs/chain_stops_{a.chain}.json").write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(out))


def p4_road_classes():
    from roadprofile import ROAD_CLASSES
    return ROAD_CLASSES


if __name__ == "__main__":
    main()
