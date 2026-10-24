"""Task 31: Tokyo 23-ward accident counts adjusted for road length and population.

Run from repository root:
uv run --no-project --with 'duckdb==1.5.5' --with scipy --with numpy \
  python projects/tokyo23-road-adjusted-accidents/scripts/analyze.py
"""

import csv
import json
import math
from collections import Counter
from datetime import date
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
TMP = PROJECT / "tmp"
OUTPUT = PROJECT / "outputs"
NPA_REV = "389500aae5cec45f1311163f70db6a5f05867838"
OSM_REV = "9a9b4a77e89e28a66bf15781644a16b63501f622"
CENSUS_REV = "6c486c8649484e09e549c0c99b5fa89b4f416edb"
ADMIN_REV = "e6c87b1d7095c17422147962185071a986e13135"
NPA = f"hf://datasets/yuiseki/npa-traffic-accidents@{NPA_REV}/parquet/2025/honhyo.parquet"
OSM = f"hf://datasets/yuiseki/osm-japan-src-2026-08@{OSM_REV}/parquet/planet_osm_line.parquet"
CENSUS = f"hf://datasets/yuiseki/estat-census-mesh-2020@{CENSUS_REV}/parquet/T001140.parquet"
ADMIN = f"hf://datasets/yuiseki/jp-admin-2026-09@{ADMIN_REV}/municipalities.parquet"
ROAD_CLASSES = (
    "motorway", "motorway_link", "trunk", "trunk_link", "primary",
    "primary_link", "secondary", "secondary_link", "tertiary",
    "tertiary_link", "unclassified", "residential", "service", "living_street",
)
SENSITIVITY_EXCLUDE = {"service", "motorway", "motorway_link"}


def is_primary_road(highway):
    return highway in ROAD_CLASSES


def mesh_code(lon, lat):
    if not (120 <= lon < 160 and 20 <= lat < 50):
        raise ValueError("point outside Japanese mesh-code range")
    a = math.floor(lat * 1.5)
    b = math.floor(lon) - 100
    e = math.floor((lat * 1.5 - a) * 8)
    f = math.floor((lon - math.floor(lon)) * 8)
    g = math.floor(((lat * 1.5 - a) * 8 - e) * 10)
    h = math.floor(((lon - math.floor(lon)) * 8 - f) * 10)
    return f"{a:02d}{b:02d}{e}{f}{g}{h}"


def mesh_bounds(code):
    if len(code) != 8 or not code.isdigit():
        raise ValueError("expected eight-digit mesh code")
    south = int(code[:2]) / 1.5 + int(code[4]) / 12 + int(code[6]) / 120
    west = 100 + int(code[2:4]) + int(code[5]) / 8 + int(code[7]) / 80
    return west, south, west + 1 / 80, south + 1 / 120


def aggregate_population(rows):
    population = Counter()
    seen = set()
    for code, pref, amount in rows:
        if len(code) != 8 or (pref, code) in seen:
            raise ValueError("invalid or duplicate census prefecture/mesh key")
        seen.add((pref, code))
        value = int(amount)
        if value < 0:
            raise ValueError("negative population")
        population[code] += value
    return dict(population)


def cached(con, path, query):
    if not path.exists():
        con.sql(f"copy ({query}) to '{path}' (format parquet)")
    return path


def clip_road_lengths(con, lines, cells, *, project=True, where="true"):
    """Clip each line to each cell; cells must already be clipped to the ward union."""
    cut = "ST_Intersection(l.way, c.geometry)"
    metric = (
        f"ST_Transform({cut}, 'EPSG:3857', 'EPSG:6677', always_xy := true)"
        if project else cut
    )
    query = f"""
        select c.mesh, sum(ST_Length({metric})) as length_m
        from {lines} l join {cells} c on ST_Intersects(l.way, c.geometry)
        where {where}
        group by c.mesh
    """
    return {mesh: float(length) for mesh, length in con.sql(query).fetchall()}


def predictive_tail(count, expected, alpha):
    """NB2 Pr(Y >= count), with variance mu + alpha*mu^2."""
    from scipy.stats import nbinom

    if count < 0 or expected <= 0 or alpha <= 0:
        raise ValueError("invalid predictive distribution input")
    return float(nbinom.sf(count - 1, 1 / alpha, 1 / (1 + alpha * expected)))


def bh_qvalues(pvalues):
    n = len(pvalues)
    ranked = sorted(range(n), key=lambda i: pvalues[i])
    answer = [0.0] * n
    running = 1.0
    for position in range(n - 1, -1, -1):
        index = ranked[position]
        running = min(running, pvalues[index] * n / (position + 1))
        answer[index] = running
    return answer


def moran_knn(values, coordinates, *, k, permutations=999, seed=31):
    """Global Moran I, row-standardized k-NN weights, two-sided permutation p."""
    import numpy as np
    from scipy.spatial import cKDTree

    z = np.asarray(values, dtype=float) - np.mean(values)
    if len(z) <= k or not np.isfinite(z).all() or np.dot(z, z) == 0:
        raise ValueError("invalid Moran input")
    _, neighbors = cKDTree(coordinates).query(coordinates, k=k + 1)
    neighbors = neighbors[:, 1:]

    def statistic(x):
        return float(np.sum(x * x[neighbors].mean(axis=1)) / np.dot(x, x))

    observed = statistic(z)
    rng = np.random.default_rng(seed)
    extreme = sum(abs(statistic(rng.permutation(z))) >= abs(observed) for _ in range(permutations))
    return {"i": observed, "pseudo_p_two_sided": (extreme + 1) / (permutations + 1), "k": k, "permutations": permutations, "seed": seed}


def design_matrix(rows, *, road=True):
    import numpy as np

    columns = [np.ones(len(rows))]
    if road:
        columns.append(np.log([row["road_km"] + 0.25 for row in rows]))
    columns.append(np.log([row["population"] + 1000 for row in rows]))
    return np.column_stack(columns)


def fit_nb(rows, *, road=True):
    import numpy as np
    from scipy.optimize import minimize
    from scipy.special import gammaln

    x = design_matrix(rows, road=road)
    y = np.array([row["accidents"] for row in rows], dtype=float)
    if len(rows) <= x.shape[1] or y.sum() <= 0:
        raise ValueError("not enough observations or no accidents")
    initial = np.linalg.lstsq(x, np.log(y + 0.5), rcond=None)[0]

    def loss(params):
        eta = x @ params[:-1]
        if np.any(eta > 30) or np.any(eta < -30):
            return 1e100
        mu = np.exp(eta)
        alpha = np.exp(params[-1])
        size = 1 / alpha
        ll = (
            gammaln(y + size) - gammaln(size) - gammaln(y + 1)
            + size * (np.log(size) - np.log(size + mu))
            + y * (np.log(mu) - np.log(size + mu))
        )
        return float(-ll.sum())

    initial = np.r_[initial, math.log(0.5)]
    fit = minimize(
        loss, initial, method="L-BFGS-B",
        bounds=[(None, None)] * x.shape[1] + [(-10, 3)],
        options={"maxiter": 2000, "ftol": 1e-11},
    )
    if not fit.success or not math.isfinite(fit.fun):
        raise RuntimeError(f"NB2 fit failed: {fit.message}")
    mu = np.exp(x @ fit.x[:-1])
    return {
        "coefficients": [float(v) for v in fit.x[:-1]],
        "alpha": float(np.exp(fit.x[-1])),
        "log_likelihood": float(-fit.fun),
        "expected": [float(v) for v in mu],
    }


def fit_poisson(rows):
    import numpy as np
    from scipy.optimize import minimize
    from scipy.special import gammaln
    x = design_matrix(rows)
    y = np.array([row["accidents"] for row in rows], dtype=float)
    initial = np.linalg.lstsq(x, np.log(y + 0.5), rcond=None)[0]

    def loss(beta):
        eta = x @ beta
        if np.any(eta > 30) or np.any(eta < -30):
            return 1e100
        return float(np.sum(np.exp(eta) - y * eta + gammaln(y + 1)))

    fit = minimize(loss, initial, method="BFGS", options={"maxiter": 1000})
    if not fit.success and float(np.max(np.abs(fit.jac))) > 0.01:
        raise RuntimeError(f"Poisson fit failed: {fit.message}")
    return [float(v) for v in np.exp(x @ fit.x)]


def ranked_with_model(rows, *, road=True):
    model = fit_nb(rows, road=road)
    scored = []
    for row, mu in zip(rows, model["expected"]):
        scored.append(row | {
            "expected": mu,
            "observed_expected": row["accidents"] / mu,
            "upper_tail_p": predictive_tail(row["accidents"], mu, model["alpha"]),
        })
    qvalues = bh_qvalues([row["upper_tail_p"] for row in scored])
    for row, q in zip(scored, qvalues):
        row["bh_q"] = q
        row["upper_tail_p_display"] = f"{row['upper_tail_p']:.7f}"
    return sorted(scored, key=lambda row: (row["upper_tail_p"], row["mesh"])), model


def write_csv(rows, path):
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main():
    import duckdb
    from scipy.stats import poisson

    TMP.mkdir(exist_ok=True)
    OUTPUT.mkdir(exist_ok=True)
    con = duckdb.connect()
    con.sql("set memory_limit='5GB'; set threads=4; install spatial; load spatial; install httpfs; load httpfs")
    wards_file = cached(con, TMP / "wards.parquet", f"select code5, name, geometry from '{ADMIN}' where code5 between '13101' and '13123'")
    accidents_file = cached(con, TMP / "accidents.parquet", f"select \"警察署等コード\" as police_station, \"本票番号\" as form_number, \"市区町村コード\" as ward_code, longitude, latitude, geometry from '{NPA}' where \"都道府県コード\"='30' and \"発生日時　　年\"='2025'")
    population_file = cached(con, TMP / "population-parts.parquet", f"select prefecture, KEY_CODE, T001140001 from '{CENSUS}' where prefecture in ('11','12','13','14')")
    con.sql(f"create view wards as select * from '{wards_file}'")
    con.sql(f"create view accidents as select * from '{accidents_file}'")
    if con.sql("select count(*) from wards").fetchone()[0] != 23:
        raise ValueError("not all 23 ward polygons found")
    accident_counts = con.sql("select count(*), count(geometry), count(distinct police_station || ':' || form_number) from accidents").fetchone()
    if accident_counts[0] != accident_counts[2]:
        raise ValueError("duplicate accident key")
    matches = con.sql("""
        select a.police_station, a.form_number, a.ward_code, a.longitude, a.latitude,
               count(w.code5) as n_wards
        from accidents a left join wards w on a.geometry is not null and
          ST_Intersects(w.geometry, ST_SetCRS(a.geometry, 'EPSG:4612'))
        group by all
    """).fetchall()
    if len(matches) != accident_counts[0]:
        raise ValueError("accident/ward join lost or duplicated rows")
    in_wards = [row for row in matches if row[-1] > 0]
    accidents_by_mesh = Counter(mesh_code(row[3], row[4]) for row in in_wards)
    pop_parts = con.sql(f"select KEY_CODE, prefecture, T001140001 from '{population_file}'").fetchall()
    population = aggregate_population(pop_parts)
    bounds = con.sql("select min(ST_XMin(geometry)), min(ST_YMin(geometry)), max(ST_XMax(geometry)), max(ST_YMax(geometry)) from wards").fetchone()
    centers = []
    for code, amount in population.items():
        west, south, east, north = mesh_bounds(code)
        lon, lat = (west + east) / 2, (south + north) / 2
        if bounds[0] <= lon <= bounds[2] and bounds[1] <= lat <= bounds[3]:
            centers.append((code, amount, lon, lat))
    con.sql("create temp table centers (mesh varchar, population bigint, lon double, lat double)")
    con.executemany("insert into centers values (?, ?, ?, ?)", centers)
    mesh_rows = con.sql("""
        select c.mesh, c.population, count(w.code5) as n_wards from centers c
        left join wards w on ST_Intersects(w.geometry,
          ST_SetCRS(ST_Point(c.lon,c.lat), 'EPSG:4612'))
        group by c.mesh, c.population
    """).fetchall()
    inside = [(mesh, pop) for mesh, pop, n in mesh_rows if n > 0]
    all_codes = {mesh for mesh, _ in inside}
    missing_accidents = sum(n for code, n in accidents_by_mesh.items() if code not in all_codes)
    if sum(accidents_by_mesh.get(code, 0) for code in all_codes) + missing_accidents != len(in_wards):
        raise ValueError("accident count not conserved")

    # Geometry of each census mesh, cut to the 23-ward union in the source CRS.
    con.sql("create temp table ward_union as select ST_Union_Agg(ST_Transform(geometry, 'EPSG:4612', 'EPSG:3857', always_xy := true)) as geometry from wards")
    con.sql("create temp table cells (mesh varchar, geometry geometry)")
    cell_data = []
    for code, _ in inside:
        west, south, east, north = mesh_bounds(code)
        cell_data.append((code, f"POLYGON(({west} {south},{east} {south},{east} {north},{west} {north},{west} {south}))"))
    con.sql("create temp table cell_wkt (mesh varchar, wkt varchar)")
    con.executemany("insert into cell_wkt values (?, ?)", cell_data)
    con.sql("""
        insert into cells select m.mesh,
          ST_Intersection(ST_Transform(ST_SetCRS(ST_GeomFromText(m.wkt), 'EPSG:4612'),
            'EPSG:3857', always_xy := true), u.geometry)
        from cell_wkt m cross join ward_union u
    """)
    if con.sql("select count(*) filter (where ST_IsEmpty(geometry)) from cells").fetchone()[0]:
        raise ValueError("a center-inside mesh has no ward overlap")
    xmin, ymin, xmax, ymax = con.sql("select ST_XMin(geometry), ST_YMin(geometry), ST_XMax(geometry), ST_YMax(geometry) from ward_union").fetchone()
    candidates = cached(con, TMP / "osm-road-candidates.parquet", f"select osm_id, highway, way from '{OSM}' where bbox.xmin <= {xmax} and bbox.xmax >= {xmin} and bbox.ymin <= {ymax} and bbox.ymax >= {ymin} and highway is not null")
    con.sql(f"create view roads_bbox as select * from '{candidates}'")
    class_sql = ",".join("'" + road + "'" for road in ROAD_CLASSES)
    con.sql(f"create temp table roads as select * from roads_bbox where highway in ({class_sql}) and way is not null")
    invalid = con.sql("select count(*) filter (where not ST_IsValid(way)), count(*) from roads").fetchone()
    if invalid[0]:
        raise ValueError(f"{invalid[0]} invalid road geometries")
    road_lengths = clip_road_lengths(con, "roads", "cells")
    excluded = ",".join("'" + road + "'" for road in SENSITIVITY_EXCLUDE)
    road_lengths_sensitivity = clip_road_lengths(con, "roads", "cells", where=f"l.highway not in ({excluded})")
    rows = [
        {"mesh": code, "population": pop, "accidents": accidents_by_mesh.get(code, 0),
         "road_km": road_lengths.get(code, 0) / 1000,
         "road_km_without_service_motorway": road_lengths_sensitivity.get(code, 0) / 1000}
        for code, pop in sorted(inside)
    ]
    primary = [row for row in rows if row["population"] >= 1000 and row["road_km"] >= 0.5]
    ranked, model = ranked_with_model(primary)
    by_count = sorted(primary, key=lambda row: (-row["accidents"], row["mesh"]))
    by_population, population_model = ranked_with_model(primary, road=False)
    cutoff_one, cutoff_one_model = ranked_with_model([row for row in rows if row["population"] >= 1000 and row["road_km"] >= 1.0])
    no_service_rows = [row | {"road_km": row["road_km_without_service_motorway"]} for row in primary]
    no_service_ranked, no_service_model = ranked_with_model(no_service_rows)
    poisson_expected = fit_poisson(primary)
    poisson_ranked = sorted(zip(primary, poisson_expected), key=lambda pair: (float(poisson.sf(pair[0]["accidents"] - 1, pair[1])), pair[0]["mesh"]))
    write_csv(ranked, OUTPUT / "mesh-results.csv")
    accounting = {
        "tokyo_2025_accident_rows": accident_counts[0],
        "with_geometry": accident_counts[1],
        "in_23_ward_polygons": len(in_wards),
        "multiple_ward_matches": sum(row[-1] > 1 for row in matches),
        "accidents_in_center_inside_meshes": len(in_wards) - missing_accidents,
        "accidents_outside_center_inside_meshes": missing_accidents,
        "census_rows": len(pop_parts),
        "census_unique_meshes": len(population),
        "center_inside_ward_meshes": len(rows),
        "road_bbox_highway_candidates": con.sql("select count(*) from roads_bbox").fetchone()[0],
        "road_selected_segments": invalid[1],
        "road_intersecting_center_inside_meshes": con.sql("select count(*) from roads l where exists (select 1 from cells c where ST_Intersects(l.way,c.geometry))").fetchone()[0],
        "road_length_km_in_meshes": sum(road_lengths.values()) / 1000,
        "primary_meshes": len(primary),
        "primary_accidents": sum(row["accidents"] for row in primary),
        "excluded_population_below_1000": sum(row["population"] < 1000 for row in rows),
        "excluded_road_below_0_5km_with_population": sum(row["population"] >= 1000 and row["road_km"] < 0.5 for row in rows),
        "minimum_primary_road_km": min(row["road_km"] for row in primary),
    }
    primary_top10 = {row["mesh"] for row in ranked[:10]}
    # Diagnostic only: fitted-on-the-same-data residuals may look less structured
    # than predictions for unseen meshes, so do not treat this as validation.
    centers_projected = con.sql("""
        select mesh, ST_X(ST_Transform(ST_SetCRS(ST_Point(lon,lat), 'EPSG:4612'),
          'EPSG:6677', always_xy := true)),
          ST_Y(ST_Transform(ST_SetCRS(ST_Point(lon,lat), 'EPSG:4612'),
          'EPSG:6677', always_xy := true)) from centers
    """).fetchall()
    center_xy = {mesh: (x, y) for mesh, x, y in centers_projected}
    residuals = [(row["accidents"] - row["expected"]) /
                 math.sqrt(row["expected"] + model["alpha"] * row["expected"] ** 2)
                 for row in ranked]
    moran = {str(k): moran_knn(residuals, [center_xy[row["mesh"]] for row in ranked], k=k)
             for k in (4, 8, 12)}
    result = {
        "question": "2025年東京23区の道路延長と2020年夜間人口を考慮しても人身事故が多い1kmメッシュ",
        "made": date.today().isoformat(),
        "sources": {"npa": NPA, "osm": OSM, "census": CENSUS, "admin": ADMIN},
        "osm_snapshot_year": 2026,
        "crs": {"accident": "OGC:CRS84", "osm": "EPSG:3857", "length": "EPSG:6677", "ward": "EPSG:4612", "mesh": "JGD2011 third-level mesh"},
        "method": "NB2 MLE on log(road_km+0.25), log(population+1000); rank by predictive upper-tail p; BH q exploratory",
        "accounting": accounting,
        "model": {k: v for k, v in model.items() if k != "expected"},
        "population_only_model": {k: v for k, v in population_model.items() if k != "expected"},
        "residual_moran_knn_in_sample": moran,
        "top10": ranked[:10],
        "top10_by_count": [r["mesh"] for r in by_count[:10]],
        "top10_population_only": [r["mesh"] for r in by_population[:10]],
        "top10_road_at_least_1km": [r["mesh"] for r in cutoff_one[:10]],
        "top10_without_service_motorway": [r["mesh"] for r in no_service_ranked[:10]],
        "top10_poisson": [r["mesh"] for r, _ in poisson_ranked[:10]],
        "top10_overlap": {
            "count": len(primary_top10 & {r["mesh"] for r in by_count[:10]}),
            "population_only": len(primary_top10 & {r["mesh"] for r in by_population[:10]}),
            "without_service_motorway": len(primary_top10 & {r["mesh"] for r in no_service_ranked[:10]}),
        },
        "sensitivity_models": {"road_at_least_1km": {k: v for k, v in cutoff_one_model.items() if k != "expected"}, "without_service_motorway": {k: v for k, v in no_service_model.items() if k != "expected"}},
    }
    (OUTPUT / "analysis.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    con.sql("create temp table map_rows (mesh varchar, population bigint, accidents bigint, road_km double, surprise double, wkt varchar)")
    by_mesh = {row["mesh"]: row for row in ranked}
    map_rows = []
    for row in rows:
        west, south, east, north = mesh_bounds(row["mesh"])
        polygon = f"POLYGON(({west} {south},{east} {south},{east} {north},{west} {north},{west} {south}))"
        score = by_mesh.get(row["mesh"])
        surprise = -math.log10(max(score["upper_tail_p"], 1e-300)) if score else None
        map_rows.append((row["mesh"], row["population"], row["accidents"], row["road_km"], surprise, polygon))
    con.executemany("insert into map_rows values (?,?,?,?,?,?)", map_rows)
    con.sql(f"copy (select mesh, population, accidents, road_km, surprise, ST_GeomFromText(wkt) as geometry from map_rows) to '{TMP / 'map-units.parquet'}' (format parquet)")
    print(json.dumps({key: result[key] for key in ("accounting", "model", "top10", "top10_by_count", "top10_population_only", "top10_road_at_least_1km", "top10_without_service_motorway", "top10_poisson")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
