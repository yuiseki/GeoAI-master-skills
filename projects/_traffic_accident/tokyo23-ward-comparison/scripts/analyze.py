"""Compare the injury accidents of the 23 wards (2019-2025 file years), every ward by the same formulas.

Run from the repository root after prepare.py:
env -u PYTHONPATH uvx --from 'duckdb>=1.5.5' --with numpy python projects/_traffic_accident/tokyo23-ward-comparison/scripts/analyze.py

The classification of an accident (生活道路, pedestrian, cyclist, ...) and the hotspot picking are the functions
of the Taito template (taito-accident-trends-by-role/scripts/analyze.py), imported, so that a ward's numbers here
are the numbers of its own report when its report used the same template version.
Writes outputs/wards.csv (one row per ward), outputs/features_z.csv, outputs/yearly.csv, outputs/analysis.json,
and artifacts/.../features.parquet for the clustering skill.
"""

import csv
import importlib.util
import json
import math
from collections import Counter
from datetime import date
from pathlib import Path

import duckdb
import numpy as np

PROJECT = Path(__file__).resolve().parents[1]
ROOT = PROJECT.parents[2]
ART = ROOT / "artifacts/_traffic_accident" / PROJECT.name
OUT = PROJECT / "outputs"
# The template's constants and functions (its main() is not run), loaded under its own name: this file is also
# analyze.py, and `import analyze` from here would return this module, not the template.
_spec = importlib.util.spec_from_file_location(
    "taito_analyze", PROJECT.parent / "taito-accident-trends-by-role/scripts/analyze.py")
taito = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(taito)

WARD_CODES = taito.WARD_CODES
YEARS = taito.YEARS
TOP = taito.TOP
RADIUS = taito.RADIUS
# The known division the clusters are compared with, fixed before clustering (EXPERIMENT_PLAN).
KNOWN = {
    "都心・副都心": ["101", "102", "103", "104", "113", "116"],
    "東部": ["106", "107", "108", "118", "121", "122", "123"],
    "その他": ["105", "109", "110", "111", "112", "114", "115", "117", "119", "120"],
}
# The 12 features of the ward types (EXPERIMENT_PLAN), all shares of the ward's accidents.
FEATURES = ["share_ped", "share_bike", "share_old_ped", "share_young_pb", "share_strict", "share_night",
            "share_intersection", "share_bike_single", "share_business_car_A", "share_truck_A", "share_weekend",
            "share_expressway"]
TOWN_TOP = 0.1  # the top 10% of a ward's census units by accidents


def trend_class(before, after):
    """増えた / 減った / 区別できない: the rule of the ward projects, on the Poisson 95% intervals of two counts."""
    lo0, hi0 = taito.poisson_interval(before)
    lo1, hi1 = taito.poisson_interval(after)
    if lo1 > hi0:
        return "増えた"
    if hi1 < lo0:
        return "減った"
    return "区別できない"


def standardised(values):
    """(value - mean) / sd over the wards, the sample sd (n - 1); all zeros when every ward has the same value."""
    x = np.asarray(values, dtype=float)
    sd = x.std(ddof=1) if len(x) > 1 else 0.0
    return [0.0] * len(x) if sd == 0 else [float(v) for v in (x - x.mean()) / sd]


def top_share(counts, fraction):
    """Share of the accidents in the ceil(fraction x units) units with most accidents; nan when there are none."""
    c = np.sort(np.asarray(counts, dtype=float))[::-1]
    if c.sum() == 0:
        return float("nan")
    return float(c[:math.ceil(fraction * len(c))].sum() / c.sum())


def write_csv(name, rows):
    path = OUT / name
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return str(path.relative_to(ROOT))


def main():
    OUT.mkdir(exist_ok=True)
    con = duckdb.connect()
    taito.ART = ART  # the template's load() reads tokyo_honhyo.parquet from ART
    rows = taito.load(con)
    for row in rows:
        row.update(taito.flags(row))
        row["bike_single"] = row["type_A"] in taito.BIKE and row["type_B"] in {"75", "76"}
        row["business_car_A"] = taito.party_group(row["type_A"], row["use_A"]) == "乗用車 (事業用)"
        row["truck_A"] = taito.party_group(row["type_A"], row["use_A"]) == "貨物車"
        row["weekend"] = row["weekday"] in (1, 7)  # 曜日: 1 = 日, 7 = 土
        row["expressway"] = 5000 <= int(row["route"]) < 5500
    con.sql("load spatial")
    con.sql("set geometry_always_xy = true")
    wards_geo = {c: (n, p, a, lon, lat) for c, n, p, a, lon, lat in con.execute(f"""select substr(code5, 3), name,
        population, ST_Area(ST_Transform(ST_GeomFromWKB(geometry), 'EPSG:4612', 'EPSG:6677')) / 1e6,
        ST_X(ST_Centroid(ST_GeomFromWKB(geometry))), ST_Y(ST_Centroid(ST_GeomFromWKB(geometry)))
        from '{ART / 'wards.parquet'}' order by code5""").fetchall()}
    with (ART / "ward_roads.csv").open(encoding="utf-8") as f:
        road_km = {r["code"]: float(r["road_km"]) for r in csv.DictReader(f)}
    known = {c: g for g, cs in KNOWN.items() for c in cs}

    # Points in EPSG:6677 for the hotspots, and census units merged by KEY_CODE for the town concentration.
    con.sql("""create table p as select ward, file_year, route,
        ST_X(ST_Transform(ST_Point(longitude, latitude), 'OGC:CRS84', 'EPSG:6677')) as x,
        ST_Y(ST_Transform(ST_Point(longitude, latitude), 'OGC:CRS84', 'EPSG:6677')) as y
        from acc where longitude is not null""")
    con.sql(f"""create table t as select CITY, KEY_CODE, any_value(HCODE) as HCODE,
        ST_Transform(ST_Union_Agg(ST_GeomFromWKB(geometry)), 'EPSG:4612', 'EPSG:6677') as g
        from '{ART / 'towns.parquet'}' group by CITY, KEY_CODE""")
    town_counts = {}
    for city, key, n in con.execute(f"""select t.CITY, t.KEY_CODE, count(p.x) from t left join p
            on p.ward = t.CITY and ST_Contains(t.g, ST_Point(p.x, p.y))
            where t.HCODE <> '{taito.WATER}' group by t.CITY, t.KEY_CODE""").fetchall():
        town_counts.setdefault(city, []).append(n)
    # The alternative reading of a ward's accidents: the point inside the ward polygon.
    inside = dict(con.execute(f"""with w as (select substr(code5, 3) code, ST_GeomFromWKB(geometry) g
            from '{ART / 'wards.parquet'}')
        select w.code, count(*) from acc, w where acc.longitude is not null
            and ST_Contains(w.g, ST_Point(acc.longitude, acc.latitude)) group by w.code""").fetchall())

    wards, yearly = [], []
    for code in WARD_CODES:
        ws = [r for r in rows if r["ward"] == code]
        name, pop, area, lon, lat = wards_geo[code]
        by_year = Counter(r["file_year"] for r in ws)
        n0, n1 = by_year["2019"], by_year["2025"]
        late = sum(by_year[y] for y in ("2022", "2023", "2024", "2025")) / 4
        xy = np.array([(x, y) for x, y in con.execute(
            "select x, y from p where ward = ?", [code]).fetchall()])  # the order of acc, as the ward projects
        hot = taito.greedy_hotspots(xy, RADIUS, TOP)
        n = len(ws)
        died = sum(r["died"] for r in ws)
        wards.append({
            "code": code, "name": name, "known_division": known[code], "lon": round(lon, 5), "lat": round(lat, 5),
            "accidents": n, "accidents_inside_polygon": inside.get(code, 0), "died": died,
            "population_2020": pop, "road_km": road_km[code], "area_km2": round(area, 3),
            "per_1000_residents_per_year": round(1000 * n / 7 / pop, 3),
            "per_road_km_per_year": round(n / 7 / road_km[code], 3),
            "per_km2_per_year": round(n / 7 / area, 2),
            "died_per_100k_residents_per_year": round(1e5 * died / 7 / pop, 3),
            "n_2019": n0, "n_2025": n1, "ratio_2025_2019": round(n1 / n0, 3),
            "ratio_2022_2025_mean_2019": round(late / n0, 3), "trend_2025": trend_class(n0, n1),
            **{f"share_{k}": round(sum(r[k] for r in ws) / n, 4) for k in
               ("ped", "bike", "old_ped", "young_pb", "strict", "night", "intersection", "bike_single",
                "business_car_A", "truck_A", "weekend", "expressway", "escooter")},
            "share_top15_hotspots": round(sum(len(m) for _, m in hot) / n, 4),
            "share_top10pct_towns": round(top_share(town_counts[code], TOWN_TOP), 4),
            "towns": len(town_counts[code]),
        })
        for y in YEARS:
            lo, hi = taito.poisson_interval(by_year[y])
            yearly.append({"code": code, "name": name, "year": y, "accidents": by_year[y], "lo95": round(lo, 1),
                           "hi95": round(hi, 1), "index_2019": round(100 * by_year[y] / n0, 1)})
    files = {"wards": write_csv("wards.csv", wards), "yearly": write_csv("yearly.csv", yearly)}

    zs = {k: standardised([w[k] for w in wards]) for k in FEATURES + ["share_top15_hotspots", "share_top10pct_towns"]}
    files["features_z"] = write_csv("features_z.csv", [
        {"code": w["code"], "name": w["name"], **{k: round(zs[k][i], 3) for k in zs}} for i, w in enumerate(wards)])
    con.execute("create table f as select * from read_csv(?)", [str(OUT / "wards.csv")])
    con.sql(f"copy (select code, name, known_division, lon, lat, {', '.join(FEATURES)} from f order by code) "
            f"to '{ART / 'features.parquet'}' (format parquet)")

    def ranks(key):
        order = sorted(wards, key=lambda w: -w[key])
        return {w["code"]: order.index(w) + 1 for w in wards}

    def spearman(a, b):
        ra, rb = ranks(a), ranks(b)
        x = np.array([ra[c] for c in WARD_CODES], float)
        y = np.array([rb[c] for c in WARD_CODES], float)
        return round(float(np.corrcoef(x, y)[0, 1]), 3)

    rates = ["per_1000_residents_per_year", "per_road_km_per_year", "per_km2_per_year"]
    total = {y: sum(1 for r in rows if r["file_year"] == y) for y in YEARS}
    audit = {
        "rows_23_wards": len(rows), "by_year_23_wards": total,
        "trend_23_wards_2025": trend_class(total["2019"], total["2025"]),
        "ratio_23_wards_2025_2019": round(total["2025"] / total["2019"], 3),
        "spearman_of_rates": {f"{a} vs {b}": spearman(a, b) for i, a in enumerate(rates) for b in rates[i + 1:]},
        "rank_of_rates": {k: ranks(k) for k in rates},
        "trend_classes": dict(Counter(w["trend_2025"] for w in wards)),
        "coded_vs_inside": {w["code"]: [w["accidents"], w["accidents_inside_polygon"]] for w in wards},
        "z_abs_1_or_more": {w["name"]: [k for k in FEATURES if abs(zs[k][i]) >= 1] for i, w in enumerate(wards)},
    }
    (OUT / "analysis.json").write_text(json.dumps({
        "run_date": str(date.today()), "commit": taito.git_head(ROOT), "duckdb": duckdb.__version__,
        "inputs": {"npa": "yuiseki/npa-traffic-accidents@389500aae5cec45f1311163f70db6a5f05867838",
                   "admin": "yuiseki/jp-admin-2026-09@e6c87b1d7095c17422147962185071a986e13135",
                   "towns": "yuiseki/estat-boundary-2020@823195c40e1055e2c1b3c0a635369f8c82b6c3fb",
                   "osm": "yuiseki/osm-tokyo23-src-2026-08@38f7a5f961b6e33343d82a11152e768c37d22664"},
        "settings": {"features": FEATURES, "known_division": KNOWN, "radius_m": RADIUS, "top_hotspots": TOP,
                     "town_top": TOWN_TOP, "template": "taito-accident-trends-by-role/scripts/analyze.py"},
        "audit": audit, "files": files}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(audit["spearman_of_rates"], ensure_ascii=False), audit["trend_classes"])


if __name__ == "__main__":
    main()
