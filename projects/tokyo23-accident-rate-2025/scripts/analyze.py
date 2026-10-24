"""Reproduce task 30 from three pinned Hugging Face datasets.

Run from the repository root with:
uv run --no-project --with 'duckdb==1.5.5' --with scipy --with numpy \
  python projects/tokyo23-accident-rate-2025/scripts/analyze.py
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
CENSUS_REV = "6c486c8649484e09e549c0c99b5fa89b4f416edb"
ADMIN_REV = "e6c87b1d7095c17422147962185071a986e13135"
NPA = (
    f"hf://datasets/yuiseki/npa-traffic-accidents@{NPA_REV}/parquet/2025/honhyo.parquet"
)
CENSUS = (
    f"hf://datasets/yuiseki/estat-census-mesh-2020@{CENSUS_REV}/parquet/T001140.parquet"
)
ADMIN = f"hf://datasets/yuiseki/jp-admin-2026-09@{ADMIN_REV}/municipalities.parquet"


def mesh_code(lon, lat):
    if not (120 <= lon < 160 and 20 <= lat < 50):
        raise ValueError("point outside expected Japanese mesh-code range")
    a = math.floor(lat * 1.5)
    b = math.floor(lon) - 100
    lat8 = (lat * 1.5 - a) * 8
    lon8 = (lon - math.floor(lon)) * 8
    e, f = math.floor(lat8), math.floor(lon8)
    g, h = math.floor((lat8 - e) * 10), math.floor((lon8 - f) * 10)
    return f"{a:02d}{b:02d}{e}{f}{g}{h}"


def mesh_bounds(code):
    if len(code) != 8 or not code.isdigit():
        raise ValueError("mesh code must contain eight digits")
    south = int(code[:2]) / 1.5 + int(code[4]) / 12 + int(code[6]) / 120
    west = 100 + int(code[2:4]) + int(code[5]) / 8 + int(code[7]) / 80
    return west, south, west + 1 / 80, south + 1 / 120


def edge_distance_m(lon, lat):
    """Approximate distance to the nearest 3rd-mesh edge (diagnostic only)."""
    west, south, east, north = mesh_bounds(mesh_code(lon, lat))
    east_west = min(lon - west, east - lon) * 111_320 * math.cos(math.radians(lat))
    north_south = min(lat - south, north - lat) * 111_132
    return max(0.0, min(east_west, north_south))


def aggregate_population(rows):
    result = Counter()
    seen = set()
    for code, pref, value in rows:
        if len(code) != 8 or not code.isdigit():
            raise ValueError(f"invalid mesh code {code}")
        if (pref, code) in seen:
            raise ValueError(f"duplicate prefecture-mesh key {pref}/{code}")
        seen.add((pref, code))
        try:
            amount = int(value)
        except (ValueError, TypeError) as error:
            raise ValueError(
                f"population is not an integer for {pref}/{code}: {value}"
            ) from error
        if amount < 0:
            raise ValueError(f"negative population for {pref}/{code}")
        result[code] += amount
    return dict(result)


def posterior_rate(accidents, population, alpha, beta):
    """Annual accidents per 10,000 residents; 5% and 95% gamma quantiles."""
    from scipy.stats import gamma

    if accidents < 0 or population <= 0 or alpha <= 0 or beta <= 0:
        raise ValueError("negative count, nonpositive population or invalid prior")
    shape, rate = alpha + accidents, beta + population / 10_000
    return (
        shape / rate,
        float(gamma.ppf(0.05, shape, scale=1 / rate)),
        float(gamma.ppf(0.95, shape, scale=1 / rate)),
    )


def fit_prior(rows):
    """Pooled rate for the prior mean; NB marginal MLE for the Gamma shape."""
    import numpy as np
    from scipy.optimize import minimize_scalar
    from scipy.special import gammaln

    y = np.array([row["accidents"] for row in rows], dtype=float)
    exposure = np.array([row["population"] / 10_000 for row in rows], dtype=float)
    mu = float(y.sum() / exposure.sum())
    if mu <= 0:
        raise ValueError("no accidents for the eligible meshes")

    def loss(log_alpha):
        alpha = math.exp(log_alpha)
        expected = mu * exposure
        ll = (
            gammaln(y + alpha)
            - gammaln(alpha)
            - gammaln(y + 1)
            + alpha * np.log(alpha / (alpha + expected))
            + y * np.log(expected / (alpha + expected))
        )
        return float(-ll.sum())

    fit = minimize_scalar(loss, bounds=(-8, 12), method="bounded")
    if not fit.success:
        raise RuntimeError(f"Gamma-Poisson prior did not converge: {fit.message}")
    alpha = float(math.exp(fit.x))
    return alpha, alpha / mu, mu


def rank_candidates(rows, min_population, alpha, beta):
    ranked = []
    for row in rows:
        if row["population"] < min_population:
            continue
        mean, low, high = posterior_rate(
            row["accidents"], row["population"], alpha, beta
        )
        ranked.append(
            row
            | {
                "raw_rate": 10_000 * row["accidents"] / row["population"],
                "posterior_rate": mean,
                "posterior_low": low,
                "posterior_high": high,
            }
        )
    return sorted(ranked, key=lambda row: (-row["posterior_low"], row["mesh"]))


def map_class_change_share(values, classes):
    """Share switching class between quantile and equal breaks, as classify_map does."""
    import numpy as np

    x = np.asarray(values, dtype=float)
    quantile = np.quantile(x, np.linspace(0, 1, classes + 1))
    equal = np.linspace(x.min(), x.max(), classes + 1)
    qclass = np.searchsorted(quantile[1:-1], x, side="left")
    eclass = np.searchsorted(equal[1:-1], x, side="left")
    return float(np.mean(qclass != eclass))


def cached(con, path, query):
    if not path.exists():
        con.sql(f"copy ({query}) to '{path}' (format parquet)")
    return path


def write_results_csv(rows, path):
    if not rows:
        raise ValueError("no results to write")
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main():
    import duckdb

    TMP.mkdir(exist_ok=True)
    OUTPUT.mkdir(exist_ok=True)
    con = duckdb.connect()
    con.sql(
        "set memory_limit='4GB'; set threads=4; install spatial; load spatial; install httpfs; load httpfs"
    )
    wards_file = cached(
        con,
        TMP / "wards-pinned.parquet",
        f"select code5, name, geometry from '{ADMIN}' "
        "where code5 between '13101' and '13123'",
    )
    accident_file = cached(
        con,
        TMP / "tokyo-2025-accidents.parquet",
        f'select "警察署等コード" as police_station, "本票番号" as form_number, '
        f'"市区町村コード" as ward_code, longitude, latitude, geometry '
        f"from '{NPA}' where \"都道府県コード\"='30' "
        f"and \"発生日時　　年\"='2025'",
    )
    population_file = cached(
        con,
        TMP / "census-population-parts.parquet",
        f"select prefecture, KEY_CODE, T001140001 from '{CENSUS}' "
        "where prefecture in ('11','12','13','14')",
    )
    con.sql(f"create view wards as select * from '{wards_file}'")
    con.sql(f"create view accidents as select * from '{accident_file}'")
    if con.sql("select count(*) from wards").fetchone()[0] != 23:
        raise ValueError("the 23 ward polygons were not all found")
    source_file_rows, occurred_2025 = con.sql(
        f"select count(*), count(*) filter (where \"発生日時　　年\"='2025') from '{NPA}'"
    ).fetchone()
    accident_summary = con.sql(
        "select count(*) as all_rows, count(geometry) as with_geometry, "
        "count(distinct police_station || ':' || form_number) as unique_ids "
        "from accidents"
    ).fetchone()
    if accident_summary[0] != accident_summary[2]:
        raise ValueError(
            "duplicate police-station/form number among Tokyo 2025 accidents"
        )
    matches = con.sql("""
        select a.police_station, a.form_number, a.ward_code, a.longitude, a.latitude,
               count(w.code5) as n_wards
        from accidents a left join wards w on a.geometry is not null and
             ST_Intersects(w.geometry, ST_SetCRS(a.geometry, 'EPSG:4612'))
        group by all
    """).fetchall()
    if len(matches) != accident_summary[0]:
        raise ValueError("accident-ward join lost or duplicated rows")
    in_wards = [row for row in matches if row[-1] > 0]
    in_mesh = Counter(mesh_code(row[3], row[4]) for row in in_wards)
    near_edge_50m = sum(edge_distance_m(row[3], row[4]) < 50 for row in in_wards)
    population_parts = con.sql(
        f"select KEY_CODE, prefecture, T001140001 from '{population_file}'"
    ).fetchall()
    population = aggregate_population(population_parts)
    bounds = con.sql(
        "select min(ST_XMin(geometry)), min(ST_YMin(geometry)), "
        "max(ST_XMax(geometry)), max(ST_YMax(geometry)) from wards"
    ).fetchone()
    centers = []
    for code, amount in population.items():
        west, south, east, north = mesh_bounds(code)
        lon, lat = (west + east) / 2, (south + north) / 2
        if bounds[0] <= lon <= bounds[2] and bounds[1] <= lat <= bounds[3]:
            centers.append((code, amount, lon, lat))
    con.sql(
        "create temp table mesh_centers (mesh varchar, population bigint, lon double, lat double)"
    )
    con.executemany("insert into mesh_centers values (?, ?, ?, ?)", centers)
    mesh_rows = con.sql("""
        select c.mesh, c.population, count(w.code5) as n_wards
        from mesh_centers c left join wards w on
          ST_Intersects(w.geometry, ST_SetCRS(ST_Point(c.lon,c.lat), 'EPSG:4612'))
        group by c.mesh, c.population
    """).fetchall()
    inside = [(code, amount) for code, amount, n in mesh_rows if n > 0]
    all_rows = [
        {"mesh": code, "population": amount, "accidents": in_mesh.get(code, 0)}
        for code, amount in sorted(inside)
    ]
    all_codes = {row["mesh"] for row in all_rows}
    unmatched_mesh_accidents = sum(
        n for code, n in in_mesh.items() if code not in all_codes
    )
    no_census_mesh_accidents = sum(
        n for code, n in in_mesh.items() if code not in population
    )
    center_outside_accidents = sum(
        n for code, n in in_mesh.items() if code in population and code not in all_codes
    )
    if no_census_mesh_accidents + center_outside_accidents != unmatched_mesh_accidents:
        raise ValueError("unmatched accidents are not fully accounted for")
    if sum(row["accidents"] for row in all_rows) + unmatched_mesh_accidents != len(
        in_wards
    ):
        raise ValueError("accident-mesh join does not conserve rows")
    primary = [row for row in all_rows if row["population"] >= 1000]
    alpha, beta, pooled = fit_prior(primary)
    ranked = rank_candidates(all_rows, 1000, alpha, beta)
    sensitivity = {}
    for minimum in (500, 2000):
        eligible = [row for row in all_rows if row["population"] >= minimum]
        a, b, _ = fit_prior(eligible)
        sensitivity[str(minimum)] = {
            "eligible_meshes": len(eligible),
            "top10": [
                row["mesh"] for row in rank_candidates(all_rows, minimum, a, b)[:10]
            ],
            "prior_alpha": a,
            "prior_beta": b,
        }
    by_count = sorted(primary, key=lambda row: (-row["accidents"], row["mesh"]))[:10]
    by_raw_rate = sorted(
        primary, key=lambda row: (-row["accidents"] / row["population"], row["mesh"])
    )[:10]
    for row in ranked:
        row["in_primary_top10"] = row["mesh"] in {x["mesh"] for x in ranked[:10]}
    write_results_csv(ranked, OUTPUT / "mesh-results.csv")
    results = {
        "question": "2025年の東京23区で2020年夜間人口を考えても人身事故が多い1kmメッシュ",
        "made": date.today().isoformat(),
        "sources": {"npa": NPA, "census": CENSUS, "admin": ADMIN},
        "crs": {
            "accident": "OGC:CRS84",
            "ward": "EPSG:4612",
            "mesh": "JGD2011 third-level mesh",
        },
        "method": "Gamma-Poisson empirical Bayes; pooled prior mean, NB marginal MLE for shape; one-sided 95% lower posterior rate",
        "posterior_interval_level": 0.9,
        "unit": "annual police-recorded injury accidents per 10,000 2020 night-time residents",
        "prior": {"alpha": alpha, "beta": beta, "pooled_rate": pooled},
        "accounting": {
            "npa_2025_file_rows": source_file_rows,
            "occurred_2025_in_file": occurred_2025,
            "tokyo_police_occurrence_2025": accident_summary[0],
            "geometry_present": accident_summary[1],
            "within_23_ward_polygons": len(in_wards),
            "within_50m_of_mesh_edge_approx": near_edge_50m,
            "multiple_ward_matches": sum(row[-1] > 1 for row in matches),
            "ward_code_101_to_123": sum(
                row[2] in {f"{i:03d}" for i in range(101, 124)} for row in in_wards
            ),
            "census_prefecture_rows": len(population_parts),
            "census_unique_meshes": len(population),
            "center_inside_23_wards": len(all_rows),
            "center_inside_zero_accidents": sum(
                row["accidents"] == 0 for row in all_rows
            ),
            "accidents_in_center_inside_meshes": len(in_wards)
            - unmatched_mesh_accidents,
            "accidents_in_other_or_no_population_meshes": unmatched_mesh_accidents,
            "accidents_without_census_mesh": no_census_mesh_accidents,
            "accidents_in_mesh_with_center_outside_23_wards": center_outside_accidents,
            "primary_population_at_least_1000": len(primary),
            "primary_accidents": sum(row["accidents"] for row in primary),
            "below_1000_population_meshes": len(all_rows) - len(primary),
            "below_1000_population_accidents": sum(
                row["accidents"] for row in all_rows if row["population"] < 1000
            ),
        },
        "top10": ranked[:10],
        "top10_by_count": [row["mesh"] for row in by_count],
        "top10_by_raw_rate": [row["mesh"] for row in by_raw_rate],
        "sensitivity": sensitivity,
        "map_class_change_share_quantile_vs_equal": map_class_change_share(
            [row["posterior_low"] for row in ranked], 5
        ),
    }
    (OUTPUT / "analysis.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2) + "\n"
    )
    con.sql(
        "create temp table map_rows (mesh varchar, population bigint, accidents bigint, "
        "posterior_low double, wkt varchar)"
    )
    map_data = []
    ranked_by_code = {row["mesh"]: row for row in ranked}
    for row in all_rows:
        west, south, east, north = mesh_bounds(row["mesh"])
        polygon = f"POLYGON(({west} {south},{east} {south},{east} {north},{west} {north},{west} {south}))"
        score = ranked_by_code.get(row["mesh"])
        map_data.append(
            (
                row["mesh"],
                row["population"],
                row["accidents"],
                score["posterior_low"] if score else None,
                polygon,
            )
        )
    con.executemany("insert into map_rows values (?, ?, ?, ?, ?)", map_data)
    con.sql(
        f"copy (select mesh, population, accidents, posterior_low, ST_GeomFromText(wkt) as geometry "
        f"from map_rows) to '{TMP / 'map-units.parquet'}' (format parquet)"
    )
    print(
        json.dumps(
            {
                "accounting": results["accounting"],
                "prior": results["prior"],
                "top10": results["top10"],
                "top10_by_count": results["top10_by_count"],
                "top10_by_raw_rate": results["top10_by_raw_rate"],
                "sensitivity": results["sensitivity"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
