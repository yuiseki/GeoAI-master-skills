"""Build a network from Overture transportation segments and measure distances along it.

Each segment is cut at its connectors' `at` positions, read as fractions of the segment's
length; connectors become nodes and the pieces become undirected edges weighted by their
great-circle length (sphere of radius 6,371 km) along the line. Shortest paths use Dijkstra.
Pairs that cannot reach each other are infinite, never filled with a number.

Commands:
    build    SEGMENTS --out-edges E --out-nodes N [--classes c1,c2 | --exclude-classes ...]
    detour   E N --pairs 2000: network distance / straight-line distance between random node pairs
    reach    E N --lon X --lat Y --within 500 1000 2000: nodes within each distance
    matrix   E N --origins O --destinations D --out M: network distance for every pair, with the
             snapping distances and the straight-line distance (input tables: id, lon, lat)

Usage:
    uvx --with numpy --with scipy --with scikit-learn --with shapely --with duckdb --with pyarrow \
        python road_network.py build \
        tmp/segments.parquet --exclude-classes footway,steps,path,pedestrian,cycleway \
        --out-edges tmp/edges.parquet --out-nodes tmp/nodes.parquet
"""

import argparse
import math

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components, dijkstra
from sklearn.neighbors import BallTree

EARTH_M = 6_371_000.0


def _hav(lon1, lat1, lon2, lat2):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    a = (np.sin((p2 - p1) / 2) ** 2
         + np.cos(p1) * np.cos(p2) * np.sin(np.radians(np.asarray(lon2) - lon1) / 2) ** 2)
    return 2 * EARTH_M * np.arcsin(np.sqrt(a))


def _cumulative(coords):
    c = np.asarray(coords, float)
    steps = _hav(c[:-1, 0], c[:-1, 1], c[1:, 0], c[1:, 1])
    return c, np.r_[0.0, np.cumsum(steps)]


def line_length_m(line):
    return float(_cumulative(line.coords)[1][-1])


def _point_at(c, cum, d):
    """Point at distance d along the line (linear in degrees within a step)."""
    i = min(int(np.searchsorted(cum, d, side="right")) - 1, len(cum) - 2)
    i = max(i, 0)
    span = cum[i + 1] - cum[i]
    t = 0.0 if span == 0 else (d - cum[i]) / span
    return tuple(c[i] + t * (c[i + 1] - c[i]))


def build_edges(segments):
    """segments: dicts with id, class, geometry (shapely LineString), connectors [(id, at)]."""
    edges, nodes = [], {}
    for s in segments:
        c, cum = _cumulative(s["geometry"].coords)
        total = cum[-1]
        conns = sorted(((x["at"], x["connector_id"]) for x in s["connectors"]), key=lambda t: t[0])
        for at, cid in conns:
            if cid not in nodes:
                nodes[cid] = _point_at(c, cum, at * total)
        for (a0, u), (a1, v) in zip(conns[:-1], conns[1:]):
            if u != v:
                edges.append({"u": u, "v": v, "length_m": (a1 - a0) * total,
                              "segment_id": s["id"], "class": s["class"]})
    return edges, nodes


class Network:
    def __init__(self, edges, nodes):
        self.ids = list(nodes)
        self.index = {n: i for i, n in enumerate(self.ids)}
        self.lon = np.array([nodes[n][0] for n in self.ids])
        self.lat = np.array([nodes[n][1] for n in self.ids])
        u = np.array([self.index[e["u"]] for e in edges], int)
        v = np.array([self.index[e["v"]] for e in edges], int)
        w = np.array([e["length_m"] for e in edges], float)
        # A zero-length edge would vanish from the sparse matrix; keep it as a tiny weight.
        w = np.maximum(w, 1e-6)
        n = len(self.ids)
        # Two segments may join the same pair of connectors; keep the shorter.
        self.graph = self._min_parallel(u, v, w, n)
        self.total_length_m = float(w.sum())

    @staticmethod
    def _min_parallel(u, v, w, n):
        best = {}
        for a, b, x in zip(u, v, w):
            k = (min(a, b), max(a, b))
            if k not in best or x < best[k]:
                best[k] = x
        if not best:
            return coo_matrix((n, n)).tocsr()
        ks = np.array(list(best), int)
        ws = np.array(list(best.values()))
        return coo_matrix((np.r_[ws, ws], (np.r_[ks[:, 0], ks[:, 1]], np.r_[ks[:, 1], ks[:, 0]])),
                          shape=(n, n)).tocsr()

    def distances(self, origins, destinations):
        o = [self.index[x] for x in origins]
        d = [self.index[x] for x in destinations]
        return dijkstra(self.graph, directed=False, indices=o)[:, d]

    def components(self):
        k, labels = connected_components(self.graph, directed=False)
        sizes = np.bincount(labels)
        return {"count": int(k), "largest_share": float(sizes.max() / len(labels)), "labels": labels}

    def snap(self, lon, lat, largest_only=False):
        """Nearest node to each point by great-circle distance; with largest_only, nearest node of
        the largest connected component, so that a point does not land on an unconnected island
        (a station passage, a private yard) from which nothing can be reached."""
        cand = np.arange(len(self.ids))
        if largest_only:
            labels = self.components()["labels"]
            cand = np.flatnonzero(labels == np.bincount(labels).argmax())
        tree = BallTree(np.radians(np.c_[self.lat[cand], self.lon[cand]]), metric="haversine")
        dist, idx = tree.query(np.radians(np.c_[lat, lon]), k=1)
        return [self.ids[cand[i]] for i in idx[:, 0]], dist[:, 0] * EARTH_M


def distance_matrix(net, o_lon, o_lat, d_lon, d_lat):
    """Network distance (m) from every origin to every destination, each point snapped to the
    largest component; also the snapping distances and the straight-line distances. Network
    distances are between the snapped nodes; the snapping legs are not added."""
    o_node, o_snap = net.snap(o_lon, o_lat, largest_only=True)
    d_node, d_snap = net.snap(d_lon, d_lat, largest_only=True)
    uniq = sorted(set(o_node))
    row = {n: i for i, n in enumerate(uniq)}
    dist = dijkstra(net.graph, directed=False, indices=[net.index[n] for n in uniq])
    cols = [net.index[n] for n in d_node]
    network = np.array([dist[row[n], cols] for n in o_node])
    straight = _hav(np.asarray(o_lon)[:, None], np.asarray(o_lat)[:, None],
                    np.asarray(d_lon)[None, :], np.asarray(d_lat)[None, :])
    return {"network_m": network, "straight_m": straight, "origin_snap_m": o_snap,
            "dest_snap_m": d_snap}


def _read_segments(path, classes=None, exclude=None):
    import duckdb
    from shapely import wkb

    where = "true"
    if classes:
        where += " and class in (" + ",".join(f"'{c}'" for c in classes) + ")"
    if exclude:
        where += " and coalesce(class, '') not in (" + ",".join(f"'{c}'" for c in exclude) + ")"
    con = duckdb.connect()
    con.sql("install spatial; load spatial;")
    rows = con.sql(f"select id, class, ST_AsWKB(geometry), connectors from '{path}' where {where}").fetchall()
    return [{"id": r[0], "class": r[1], "geometry": wkb.loads(bytes(r[2])), "connectors": r[3]}
            for r in rows]


def _save(edges, nodes, out_edges, out_nodes):
    import duckdb
    import pyarrow as pa

    e = pa.table({k: [x[k] for x in edges] for k in ("u", "v", "length_m", "segment_id", "class")})
    n = pa.table({"id": list(nodes), "lon": [p[0] for p in nodes.values()],
                  "lat": [p[1] for p in nodes.values()]})
    duckdb.sql(f"copy (select * from e) to '{out_edges}' (format parquet)")
    duckdb.sql(f"copy (select * from n) to '{out_nodes}' (format parquet)")


def _load(edges_path, nodes_path):
    import duckdb

    edges = [dict(zip(("u", "v", "length_m"), r)) for r in
             duckdb.sql(f"select u, v, length_m from '{edges_path}'").fetchall()]
    nodes = {r[0]: (r[1], r[2]) for r in duckdb.sql(f"select id, lon, lat from '{nodes_path}'").fetchall()}
    return Network(edges, nodes)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("segments")
    b.add_argument("--classes")
    b.add_argument("--exclude-classes")
    b.add_argument("--out-edges", required=True)
    b.add_argument("--out-nodes", required=True)
    d = sub.add_parser("detour")
    d.add_argument("edges")
    d.add_argument("nodes")
    d.add_argument("--pairs", type=int, default=2000)
    d.add_argument("--seed", type=int, default=0)
    m = sub.add_parser("matrix")
    m.add_argument("edges")
    m.add_argument("nodes")
    m.add_argument("--origins", required=True, help="table with id, lon, lat")
    m.add_argument("--destinations", required=True, help="table with id, lon, lat")
    m.add_argument("--out", required=True)
    r = sub.add_parser("reach")
    r.add_argument("edges")
    r.add_argument("nodes")
    r.add_argument("--lon", type=float, required=True)
    r.add_argument("--lat", type=float, required=True)
    r.add_argument("--within", type=float, nargs="+", required=True)
    a = p.parse_args()

    if a.cmd == "build":
        segs = _read_segments(a.segments, a.classes and a.classes.split(","),
                              a.exclude_classes and a.exclude_classes.split(","))
        edges, nodes = build_edges(segs)
        _save(edges, nodes, a.out_edges, a.out_nodes)
        net = Network(edges, nodes)
        comp = net.components()
        print(f"segments {len(segs)}, edges {len(edges)}, nodes {len(nodes)}, "
              f"length {net.total_length_m / 1000:.1f} km, components {comp['count']}, "
              f"largest holds {comp['largest_share']:.1%} of nodes")
        return

    net = _load(a.edges, a.nodes)
    if a.cmd == "matrix":
        import duckdb
        import pyarrow as pa

        o = duckdb.sql(f"select id, lon, lat from '{a.origins}'").fetchnumpy()
        d = duckdb.sql(f"select id, lon, lat from '{a.destinations}'").fetchnumpy()
        res = distance_matrix(net, o["lon"], o["lat"], d["lon"], d["lat"])
        no, nd = len(o["id"]), len(d["id"])
        mat = pa.table({
            "origin": np.repeat([str(x) for x in o["id"]], nd),
            "destination": np.tile([str(x) for x in d["id"]], no),
            "network_m": res["network_m"].ravel(),
            "straight_m": res["straight_m"].ravel(),
            "origin_snap_m": np.repeat(res["origin_snap_m"], nd),
            "destination_snap_m": np.tile(res["dest_snap_m"], no),
        })
        duckdb.sql(f"copy (select * from mat) to '{a.out}' (format parquet)")
        unreachable = int(np.isinf(res["network_m"]).sum())
        print(f"origins {no}, destinations {nd}, pairs {no * nd}, unreachable {unreachable}")
        for name, snap in (("origins", res["origin_snap_m"]), ("destinations", res["dest_snap_m"])):
            print(f"{name} snapped: median {np.median(snap):.1f} m, max {snap.max():.1f} m")
        return
    if a.cmd == "detour":
        rng = np.random.default_rng(a.seed)
        n = len(net.ids)
        o = rng.integers(0, n, a.pairs)
        t = rng.integers(0, n, a.pairs)
        keep = o != t
        o, t = o[keep], t[keep]
        dist = dijkstra(net.graph, directed=False, indices=np.unique(o))
        row = {x: i for i, x in enumerate(np.unique(o))}
        dn = np.array([dist[row[x], y] for x, y in zip(o, t)])
        ds = _hav(net.lon[o], net.lat[o], net.lon[t], net.lat[t])
        reach = np.isfinite(dn) & (ds > 0)
        ratio = dn[reach] / ds[reach]
        print(f"pairs {len(o)}, unreachable {int((~np.isfinite(dn)).sum())}")
        print("network / straight-line distance: median {:.3f}, 90th percentile {:.3f}, max {:.2f}".format(
            np.median(ratio), np.percentile(ratio, 90), ratio.max()))
    else:
        near, near_m = net.snap(np.array([a.lon]), np.array([a.lat]))
        node, snap_m = net.snap(np.array([a.lon]), np.array([a.lat]), largest_only=True)
        if near[0] != node[0]:
            print(f"the nearest node ({near_m[0]:.1f} m) is not in the largest component; using the "
                  "nearest node that is")
        dist = dijkstra(net.graph, directed=False, indices=[net.index[node[0]]])[0]
        print(f"start snapped {snap_m[0]:.1f} m to node {node[0]}")
        for w in a.within:
            m = dist <= w
            print(f"  within {w:g} m: nodes {int(m.sum())}")


if __name__ == "__main__":
    main()
