"""Reproduce nationwide bus-operator concentration from pinned public data.

uv run --no-project --with duckdb --with numpy --with scipy --with shapely \
  python3 projects/_traffic_bus/japan-bus-operator-concentration-replication/scripts/analysis.py
"""

import csv
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

PROJECT = Path(__file__).resolve().parents[1]
ARTIFACTS = PROJECT.parents[2] / "artifacts" / PROJECT.parent.name / PROJECT.name
DATASETS = {
    "census": ("estat-census-mesh-2020", "6c486c8649484e09e549c0c99b5fa89b4f416edb", "parquet/T001140.parquet"),
    "stops": ("ksj-p11-bus-stop-jp", "442223b4544103a922f21081c070dd5c69e4c23e", "parquet/bus_stop.parquet"),
    "admin": ("jp-admin-2026-09", "e6c87b1d7095c17422147962185071a986e13135", "municipalities.parquet"),
}
EARTH_KM = 6371.0088


def url(which):
    name, revision, path = DATASETS[which]
    return f"https://huggingface.co/datasets/yuiseki/{name}/resolve/{revision}/{path}"


def aggregate_census(rows):
    """Preserve suppression if any slice of a mesh has hidden age."""
    out = {}
    for code, pop, raw_age in rows:
        if not isinstance(code, str) or len(code) != 8 or not code.isdigit():
            raise ValueError(f"bad mesh code: {code!r}")
        total, age = out.get(code, (0, 0))
        population = int(pop)
        if population < 0:
            raise ValueError("negative population")
        if raw_age == "*" or raw_age is None:
            age = None
        elif age is not None:
            age += int(raw_age)
        out[code] = (total + population, age)
    return out


def mesh_center(code):
    if len(code) != 8 or not code.isdigit():
        raise ValueError(f"bad mesh code: {code!r}")
    lat = int(code[:2]) / 1.5 + int(code[4]) * 5 / 60 + int(code[6]) / 120 + 1 / 240
    lon = int(code[2:4]) + 100 + int(code[5]) * 7.5 / 60 + int(code[7]) / 80 + 1 / 160
    return lon, lat


def unit_xyz(lon, lat):
    lon, lat = np.deg2rad(lon), np.deg2rad(lat)
    clat = np.cos(lat)
    return np.column_stack((clat * np.cos(lon), clat * np.sin(lon), np.sin(lat)))


def classify_neighbors(mesh_lon, mesh_lat, stop_lon, stop_lat, operators, radii):
    radii = tuple(sorted(radii))
    if not radii or radii[0] <= 0:
        raise ValueError("radii must be positive")
    mesh_xyz = unit_xyz(np.asarray(mesh_lon), np.asarray(mesh_lat))
    stop_xyz = unit_xyz(np.asarray(stop_lon), np.asarray(stop_lat))
    tree = cKDTree(stop_xyz)
    answer = {r: np.zeros(len(mesh_xyz), dtype=np.int16) for r in radii}
    max_chord = 2 * np.sin((radii[-1] / 1000 / EARTH_KM) / 2)
    for start in range(0, len(mesh_xyz), 4000):
        neighbors = tree.query_ball_point(mesh_xyz[start:start + 4000], max_chord, workers=4)
        for offset, indices in enumerate(neighbors):
            if not indices:
                continue
            xyz = stop_xyz[indices]
            chords = np.linalg.norm(xyz - mesh_xyz[start + offset], axis=1)
            meters = 2000 * EARTH_KM * np.arcsin(np.minimum(chords / 2, 1))
            for radius in radii:
                answer[radius][start + offset] = len({operators[i] for i, d in zip(indices, meters) if d <= radius})
        if start and start % 20000 == 0:
            print(f"classified {start}/{len(mesh_xyz)} meshes", flush=True)
    return answer


def weighted_share(counts, ages):
    denominator = sum(age for count, age in zip(counts, ages) if age is not None and count > 0)
    numerator = sum(age for count, age in zip(counts, ages) if age is not None and count == 1)
    return numerator / denominator if denominator else None


def assign_municipalities(lons, lats, admin_rows):
    from shapely import from_wkb, points
    from shapely.strtree import STRtree

    geoms = from_wkb([r[2] for r in admin_rows])
    tree = STRtree(geoms)
    pts = points(lons, lats)
    left, right = tree.query(pts, predicate="intersects")
    matches = defaultdict(list)
    for mi, gi in zip(left.tolist(), right.tolist()):
        matches[mi].append(gi)
    assignments = np.full(len(pts), -1, dtype=np.int32)
    multi = 0
    for mi, found in matches.items():
        if len(found) > 1:
            multi += 1
        assignments[mi] = min(found, key=lambda k: admin_rows[k][0])
    missing = np.flatnonzero(assignments < 0)
    if len(missing):
        nearest = tree.query_nearest(pts[missing])
        # query_nearest may return multiple equidistant matches.
        for local, gi in zip(*nearest):
            mi = missing[local]
            if assignments[mi] < 0 or admin_rows[gi][0] < admin_rows[assignments[mi]][0]:
                assignments[mi] = gi
    if np.any(assignments < 0):
        raise ValueError("some meshes could not be assigned to municipalities")
    return assignments, {"within_one": len(matches) - multi, "within_multiple": multi, "nearest": len(missing)}


def summarize(counts, ages):
    valid = np.array([a is not None and a > 0 for a in ages])
    weight = np.array([a or 0 for a in ages], dtype=np.int64)
    one = (counts == 1) & valid
    any_stop = (counts > 0) & valid
    return {
        "eligible_meshes": int(valid.sum()),
        "stop_meshes": int(any_stop.sum()),
        "single_meshes": int(one.sum()),
        "stop_older_population": int(weight[any_stop].sum()),
        "single_older_population": int(weight[one].sum()),
        "no_stop_older_population": int(weight[valid & (counts == 0)].sum()),
        "single_share": weighted_share(counts, ages),
    }


def main():
    import duckdb

    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial")
    con.execute("SET threads=4")
    con.execute("SET memory_limit='4GB'")
    census_rows = con.execute("SELECT KEY_CODE, T001140001, T001140019 FROM read_parquet(?)", [url("census")]).fetchall()
    census = aggregate_census(census_rows)
    if len(census_rows) != 177861 or sum(p for p, _ in census.values()) != 126146099:
        raise ValueError("census source audit failed")
    codes = sorted(code for code, (pop, _) in census.items() if pop > 0)
    mesh_xy = np.asarray([mesh_center(code) for code in codes])
    ages = [census[code][1] for code in codes]
    stop_rows = con.execute("SELECT operator, ST_X(geometry), ST_Y(geometry) FROM read_parquet(?)", [url("stops")]).fetchall()
    operators = [r[0] for r in stop_rows]
    stop_xy = np.asarray([r[1:] for r in stop_rows], dtype=float)
    if len(stop_rows) != 278515 or len(set(operators)) != 1445:
        raise ValueError("bus stop source audit failed")
    counts = classify_neighbors(mesh_xy[:, 0], mesh_xy[:, 1], stop_xy[:, 0], stop_xy[:, 1], operators, (500, 800, 1000))
    summaries = {str(r): summarize(c, ages) for r, c in counts.items()}
    admin_rows = con.execute("SELECT code5, name, ST_AsWKB(geometry) FROM read_parquet(?) WHERE ward IS NULL AND geometry IS NOT NULL ORDER BY code5", [url("admin")]).fetchall()
    assignments, join_audit = assign_municipalities(mesh_xy[:, 0], mesh_xy[:, 1], admin_rows)
    groups = defaultdict(list)
    for i, ai in enumerate(assignments):
        groups[int(ai)].append(i)
    municipalities = []
    for ai, idx in groups.items():
        local_ages = [ages[i] for i in idx]
        local_counts = counts[800][idx]
        row = summarize(local_counts, local_ages)
        row.update(code5=admin_rows[ai][0], name=admin_rows[ai][1])
        municipalities.append(row)
    municipalities.sort(key=lambda r: r["code5"])
    if sum(r["single_older_population"] for r in municipalities) != summaries["800"]["single_older_population"]:
        raise ValueError("municipality totals do not match national totals")
    outputs = PROJECT / "outputs"
    outputs.mkdir(parents=True, exist_ok=True)
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    with (outputs / "municipalities.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=municipalities[0].keys(), lineterminator="\n")
        writer.writeheader()
        writer.writerows(municipalities)
    with (ARTIFACTS / "meshes.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(("mesh_code", "longitude", "latitude", "population", "age65", "municipality_code", "operators_500m", "operators_800m", "operators_1000m"))
        for i, code in enumerate(codes):
            writer.writerow((code, *mesh_xy[i], census[code][0], ages[i], admin_rows[assignments[i]][0], *[int(counts[r][i]) for r in (500, 800, 1000)]))
    audit = {
        "datasets": {k: {"revision": v[1], "url": url(k)} for k, v in DATASETS.items()},
        "census_rows": len(census_rows),
        "inhabited_meshes": len(codes),
        "suppressed_age_meshes": sum(a is None for a in ages),
        "stop_rows": len(stop_rows),
        "operator_strings": len(set(operators)),
        "municipality_rows": len(admin_rows),
        "join": join_audit,
        "radii": summaries,
        "municipalities_with_mesh": len(municipalities),
        "method": "spherical haversine on mesh center; P11 operator distinct strings; age65 population weighted",
    }
    (outputs / "audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(audit, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
