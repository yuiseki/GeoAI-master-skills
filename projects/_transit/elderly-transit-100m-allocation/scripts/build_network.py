"""Build the pedestrian graph and multi-source bus / station distances.

Run from repository root with the analysis venv:
  /tmp/venv-geoai/bin/python projects/_transit/elderly-transit-100m-allocation/scripts/build_network.py
"""

import json
import math
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import shapely

ROOT = Path(__file__).resolve().parents[4]
PROJECT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts" / PROJECT.parent.name / PROJECT.name
OUTPUT = PROJECT / "outputs"

WALK_CLASSES = {
    "residential", "living_street", "service", "unclassified", "tertiary",
    "tertiary_link", "secondary", "secondary_link", "primary", "primary_link",
    "footway", "pedestrian", "path", "track", "steps",
}


def walkable(highway, foot, access, *, include_steps=False):
    if highway not in WALK_CLASSES or (highway == "steps" and not include_steps):
        return False
    if foot in ("no", "private") or access in ("no", "private"):
        return False
    return True


def build_graph(lines):
    import numpy as np
    from scipy.sparse import csr_matrix

    node_ids = {}
    positions = []
    edges = {}
    line_count = 0
    for line in lines:
        line_count += 1
        if len(line) < 2:
            continue
        ids = []
        for x, y in line:
            key = (round(float(x), 2), round(float(y), 2))
            if key not in node_ids:
                node_ids[key] = len(positions)
                positions.append(key)
            ids.append(node_ids[key])
        for a, b, p, q in zip(ids[:-1], ids[1:], line[:-1], line[1:]):
            length = math.hypot(q[0] - p[0], q[1] - p[1])
            if a == b or length <= 0:
                continue
            key = (min(a, b), max(a, b))
            if key not in edges or length < edges[key]:
                edges[key] = length
    if not edges:
        raise ValueError("no traversable road edges")
    u = np.fromiter((a for a, _ in edges), dtype=np.int32)
    v = np.fromiter((b for _, b in edges), dtype=np.int32)
    w = np.fromiter(edges.values(), dtype=float)
    graph = csr_matrix(
        (np.r_[w, w], (np.r_[u, v], np.r_[v, u])),
        shape=(len(positions), len(positions)),
    )
    return graph, np.asarray(positions, dtype=float), {
        "lines": line_count,
        "nodes": len(positions),
        "edges": len(edges),
        "length_km": float(w.sum() / 1000),
    }


def snap_points(positions, coordinates, *, max_snap_m, tree=None):
    from scipy.spatial import cKDTree

    if tree is None:
        tree = cKDTree(coordinates)
    if positions is None or len(positions) == 0:
        return []
    d, ids = tree.query(positions)
    return [
        (int(i), float(m)) if m <= max_snap_m else (None, float(m))
        for i, m in zip(ids, d)
    ]


def multi_source_distances(graph, coordinates, destinations, *, max_snap_m=200, tree=None):
    import numpy as np
    from scipy.sparse import coo_matrix, hstack, vstack
    from scipy.sparse.csgraph import dijkstra

    snapped = snap_points(destinations, coordinates, max_snap_m=max_snap_m, tree=tree)
    sources = {}
    for node, offset in snapped:
        if node is not None:
            sources[node] = min(offset, sources.get(node, math.inf))
    if not sources:
        return np.full(graph.shape[0], math.inf), snapped
    n = graph.shape[0]
    top = coo_matrix(
        (list(sources.values()), ([0] * len(sources), list(sources))),
        shape=(1, n),
    ).tocsr()
    # A strictly positive connector avoids sparse matrices silently dropping 0 edges.
    top.data = np.maximum(top.data, 1e-6)
    augmented = vstack(
        [hstack([graph, top.T]), hstack([top, coo_matrix((1, 1))])]
    ).tocsr()
    distances = dijkstra(augmented, directed=False, indices=n)[:n]
    return distances, snapped


def self_test():
    from scipy.sparse import csr_matrix

    # 0--100--1--100--2 ; 3 isolated
    graph = csr_matrix(
        (
            np.array([100.0, 100.0, 100.0, 100.0]),
            (np.array([0, 1, 1, 2]), np.array([1, 0, 2, 1])),
        ),
        shape=(4, 4),
    )
    coords = np.array([[0.0, 0.0], [100.0, 0.0], [200.0, 0.0], [500.0, 500.0]])
    d, _ = multi_source_distances(
        graph, coords, [(0.0, 0.0)], max_snap_m=1.0, tree=None
    )
    assert np.allclose(d[:3], [0.0, 100.0, 200.0], atol=1e-4)
    assert not np.isfinite(d[3])
    # A destination 30 m from node 1 adds the snap offset.
    d2, _ = multi_source_distances(
        graph, coords, [(130.0, 0.0)], max_snap_m=50.0, tree=None
    )
    assert np.allclose([d2[0], d2[2]], [130.0, 130.0], atol=1e-4)
    # Too far to snap: no source, all unknown.
    d3, snaps = multi_source_distances(
        graph, coords, [(1000.0, 1000.0)], max_snap_m=50.0, tree=None
    )
    assert not np.isfinite(d3).any() and snaps[0][0] is None


def main():
    from scipy.sparse import save_npz
    from scipy.sparse.csgraph import connected_components
    from scipy.spatial import cKDTree

    self_test()
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute("set memory_limit='24GB'; set threads=8")
    con.execute("install spatial; load spatial")

    road_file = ARTIFACTS / "osm-lines-buffer.parquet"
    if not road_file.exists():
        raise FileNotFoundError(road_file)
    walk_file = ARTIFACTS / "osm-walk-6677.parquet"
    if not walk_file.exists():
        classes = ",".join(f"'{c}'" for c in sorted(WALK_CLASSES) if c != "steps")
        con.execute(
            f"""copy (
                select highway, foot, access,
                       ST_AsWKB(ST_Transform(way,'EPSG:3857','EPSG:6677',always_xy := true)) as wkb
                from '{road_file}'
                where highway in ({classes})
                  and coalesce(foot,'') not in ('no','private')
                  and coalesce(access,'') not in ('no','private')
            ) to '{walk_file}' (format parquet)"""
        )
    walk_count = con.execute(f"select count(*) from '{walk_file}'").fetchone()[0]

    def lines():
        cursor = con.execute(f"select wkb from '{walk_file}'")
        while chunk := cursor.fetchmany(10000):
            for (wkb,) in chunk:
                geom = shapely.from_wkb(bytes(wkb))
                for part in getattr(geom, "geoms", [geom]):
                    if part.geom_type == "LineString":
                        yield list(part.coords)

    graph, coordinates, graph_info = build_graph(lines())
    components, labels = connected_components(graph, directed=False)
    component_sizes = np.bincount(labels)
    tree = cKDTree(coordinates)

    buses = pd.read_parquet(ARTIFACTS / "bus-buffer.parquet")
    bus_by_coord = (
        buses.assign(lon=buses.lon.round(7), lat=buses.lat.round(7))
        .drop_duplicates(["lon", "lat"])
        .reset_index(drop=True)
    )
    stations = pd.read_parquet(ARTIFACTS / "stations-buffer.parquet")
    active = stations[stations.e_status == 0].reset_index(drop=True)
    if active.empty:
        raise ValueError("no active stations")

    from pyproj import Transformer

    to_metric = Transformer.from_crs(4326, 6677, always_xy=True)
    bus_positions = np.array(
        [to_metric.transform(lon, lat) for lon, lat in zip(bus_by_coord.lon, bus_by_coord.lat)]
    )
    station_positions = np.array(
        [to_metric.transform(lon, lat) for lon, lat in zip(active.lon, active.lat)]
    )

    bus_d, bus_snaps = multi_source_distances(
        graph, coordinates, bus_positions, max_snap_m=200, tree=tree
    )
    rail_d, rail_snaps = multi_source_distances(
        graph, coordinates, station_positions, max_snap_m=200, tree=tree
    )

    save_npz(ARTIFACTS / "walk-graph.npz", graph)
    np.savez_compressed(
        ARTIFACTS / "network.npz",
        positions=coordinates,
        labels=labels.astype(np.int32),
        bus_m=bus_d.astype(np.float32),
        rail_m=rail_d.astype(np.float32),
        bus_positions=bus_positions,
        station_positions=station_positions,
    )

    accounting = {
        "walk_lines": int(walk_count),
        "graph": graph_info
        | {
            "components": int(components),
            "largest_component_nodes": int(component_sizes.max()),
            "largest_component_share": float(component_sizes.max() / len(coordinates)),
        },
        "bus_unique_points": int(len(bus_by_coord)),
        "bus_snapped_within_200m": int(sum(node is not None for node, _ in bus_snaps)),
        "bus_snap_distance_m": {
            "median": float(np.median([m for _, m in bus_snaps])),
            "p95": float(np.quantile([m for _, m in bus_snaps], 0.95)),
            "max": float(np.max([m for _, m in bus_snaps])),
        },
        "station_active_rows": int(len(active)),
        "station_snapped_within_200m": int(sum(node is not None for node, _ in rail_snaps)),
        "station_snap_distance_m": {
            "median": float(np.median([m for _, m in rail_snaps])),
            "p95": float(np.quantile([m for _, m in rail_snaps], 0.95)),
            "max": float(np.max([m for _, m in rail_snaps])),
        },
        "graph_reachable_from_bus": int(np.isfinite(bus_d).sum()),
        "graph_reachable_from_station": int(np.isfinite(rail_d).sum()),
    }
    (OUTPUT / "network-accounting.json").write_text(
        json.dumps(accounting, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(accounting, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
