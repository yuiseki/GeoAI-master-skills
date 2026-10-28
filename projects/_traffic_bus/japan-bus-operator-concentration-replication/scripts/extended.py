"""Explore planned within-mesh comparison and bus-kind composition.

This is a post-result extension of the independent reproduction, not a
confirmatory analysis. It reads the pinned source files and saved mesh output.

uv run --no-project --with duckdb --with numpy --with scipy python3 \
  projects/_traffic_bus/japan-bus-operator-concentration-replication/scripts/extended.py
"""

import csv
import json
from collections import defaultdict
from statistics import median

import numpy as np
from scipy.spatial import cKDTree

from analysis import (
    ARTIFACTS,
    EARTH_KM,
    PROJECT,
    aggregate_census,
    summarize,
    unit_xyz,
    url,
)
from diagnostics import top_overlap


def mesh_bounds(code):
    if len(code) != 8 or not code.isdigit():
        raise ValueError(f"bad mesh code: {code!r}")
    from analysis import mesh_center

    lon, lat = mesh_center(code)
    return lon - 1 / 160, lat - 1 / 240, lon + 1 / 160, lat + 1 / 240


def classify_single_kind(kinds_by_stop):
    kinds = {k for stop in kinds_by_stop for k in stop}
    if not kinds:
        raise ValueError("single-operator mesh has no bus kind")
    if kinds == {1}:
        return "private"
    if kinds == {2}:
        return "public"
    if kinds == {3}:
        return "community"
    return "mixed"


def inspect_mesh(code, lon, lat, neighbor_indices, stop_rows, radius_m=800, *, point_xyz=None, stops_xyz=None):
    """One mesh from a spherical candidate neighborhood; no network claim."""
    west, south, east, north = mesh_bounds(code)
    candidates = []
    internal = []
    xyz = point_xyz if point_xyz is not None else unit_xyz(np.array([lon]), np.array([lat]))[0]
    indices = list(neighbor_indices)
    if stops_xyz is not None and indices:
        chords = np.linalg.norm(stops_xyz[indices] - xyz, axis=1)
        distances = 2000 * EARTH_KM * np.arcsin(np.minimum(chords / 2, 1))
    else:
        distances = [2000 * EARTH_KM * np.arcsin(min(
            float(np.linalg.norm(unit_xyz(np.array([stop_rows[i][0]]), np.array([stop_rows[i][1]]))[0] - xyz)) / 2,
            1,
        )) for i in indices]
    for i, distance_m in zip(indices, distances):
        stop = stop_rows[i]
        if distance_m <= radius_m:
            candidates.append(stop)
        if west <= stop[0] < east and south <= stop[1] < north:
            internal.append(stop)
    operators = {s[2] for s in candidates}
    category = None
    route_pairs = None
    if len(operators) == 1:
        if any(len(s[3]) != len(s[4]) for s in candidates):
            raise ValueError(f"route and kind arrays differ in {code}")
        category = classify_single_kind(s[3] for s in candidates)
        route_pairs = len({(s[2], route) for s in candidates for route in s[4]})
    return {
        "operators_800m": len(operators),
        "operators_in_mesh": len({s[2] for s in internal}),
        "single_kind": category,
        "route_pairs": route_pairs,
    }


def main():
    import duckdb

    with (ARTIFACTS / "meshes.csv").open(encoding="utf-8", newline="") as stream:
        meshes = list(csv.DictReader(stream))
    if len(meshes) != 176964 or len({m["mesh_code"] for m in meshes}) != len(meshes):
        raise ValueError("saved mesh output is missing or duplicated")
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial")
    con.execute("SET threads=4")
    con.execute("SET memory_limit='4GB'")
    source_rows = con.execute(
        "SELECT KEY_CODE, T001140001, T001140022 FROM read_parquet(?)", [url("census")]
    ).fetchall()
    age75 = aggregate_census(source_rows)
    if len(source_rows) != 177861 or sum(p for p, _ in age75.values()) != 126146099:
        raise ValueError("census source audit failed")
    stops = con.execute(
        "SELECT ST_X(geometry), ST_Y(geometry), operator, kinds, routes "
        "FROM read_parquet(?)", [url("stops")]
    ).fetchall()
    if len(stops) != 278515:
        raise ValueError("stop source audit failed")
    stop_rows = [(float(x), float(y), operator, tuple(kinds), tuple(routes))
                 for x, y, operator, kinds, routes in stops]
    stop_xy = np.asarray([(r[0], r[1]) for r in stop_rows], dtype=float)
    mesh_xy = np.asarray([(float(m["longitude"]), float(m["latitude"])) for m in meshes], dtype=float)
    stop_xyz = unit_xyz(stop_xy[:, 0], stop_xy[:, 1])
    mesh_xyz = unit_xyz(mesh_xy[:, 0], mesh_xy[:, 1])
    tree = cKDTree(stop_xyz)
    chord = 2 * np.sin((800 / 1000 / EARTH_KM) / 2)
    in_mesh_counts = np.zeros(len(meshes), dtype=np.int16)
    age65 = [int(m["age65"]) if m["age65"] else None for m in meshes]
    age75_values = []
    kinds_summary = defaultdict(lambda: {"meshes": 0, "older_people": 0})
    suppressed = defaultdict(int)
    route_count = []
    m65 = defaultdict(int)
    m75 = defaultdict(int)
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    with (ARTIFACTS / "extended_meshes.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(("mesh_code", "age75", "operators_in_mesh", "single_kind", "single_route_pairs"))
        for start in range(0, len(meshes), 4000):
            neighbor_lists = tree.query_ball_point(mesh_xyz[start:start + 4000], chord, workers=4)
            for offset, indices in enumerate(neighbor_lists):
                i = start + offset
                m = meshes[i]
                code = m["mesh_code"]
                result = inspect_mesh(
                    code, mesh_xy[i, 0], mesh_xy[i, 1], indices, stop_rows,
                    point_xyz=mesh_xyz[i], stops_xyz=stop_xyz,
                )
                if result["operators_800m"] != int(m["operators_800m"]):
                    raise ValueError(f"source mismatch for {code}")
                in_mesh_counts[i] = result["operators_in_mesh"]
                age75_value = age75[code][1]
                age75_values.append(age75_value)
                if age65[i] is None:
                    suppressed[str(result["operators_800m"] if result["operators_800m"] < 2 else "2+")] += 1
                if age65[i] is not None and age65[i] > 0 and result["single_kind"]:
                    item = kinds_summary[result["single_kind"]]
                    item["meshes"] += 1
                    item["older_people"] += age65[i]
                    route_count.append(result["route_pairs"])
                if int(m["operators_800m"]) == 1:
                    if age65[i] is not None and age65[i] > 0:
                        m65[m["municipality_code"]] += age65[i]
                    if age75_value is not None and age75_value > 0:
                        m75[m["municipality_code"]] += age75_value
                writer.writerow((code, age75_value, result["operators_in_mesh"], result["single_kind"], result["route_pairs"]))
            print(f"extended {min(start + 4000, len(meshes))}/{len(meshes)} meshes", flush=True)
    baseline = json.loads((PROJECT / "outputs/audit.json").read_text(encoding="utf-8"))
    within = summarize(in_mesh_counts, age65)
    if sum(x["older_people"] for x in kinds_summary.values()) != baseline["radii"]["800"]["single_older_population"]:
        raise ValueError("kind categories do not sum to the 800m single-operator population")
    result = {
        "sources": {"stops": url("stops"), "census": url("census"), "saved_mesh": "artifacts/_traffic_bus/japan-bus-operator-concentration-replication/meshes.csv"},
        "mode": "exploratory post-result extension",
        "within_mesh": within,
        "age75_800m": summarize(np.array([int(m["operators_800m"]) for m in meshes]), age75_values),
        "age75_top20_overlap_with_age65": top_overlap(m65, m75, 20),
        "single_kind_800m": dict(sorted(kinds_summary.items())),
        "single_route_pairs_median": median(route_count),
        "single_route_pairs_one_meshes": sum(x == 1 for x in route_count),
        "single_route_pairs_observed_meshes": len(route_count),
        "suppressed_age65_by_operator_count": dict(sorted(suppressed.items())),
    }
    (PROJECT / "outputs/extended.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
