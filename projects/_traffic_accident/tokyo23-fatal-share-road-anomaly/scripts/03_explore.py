"""Exploratory follow-ups after B2-B6 (EXPERIMENT_TRACKER.md D2): not part of the pre-run decision rules.

systemd-run --user --scope -q -p MemoryMax=8G -p MemorySwapMax=0 -p CPUQuota=400% -- \
  uvx --from 'duckdb>=1.5.5' --with numpy --with scipy --with pandas --with pyarrow python -u scripts/03_explore.py

1. B3's overdispersion test with the motorway and the pedestrian-or-cyclist flag added to the strata.
2. The 1 km meshes: persistence early -> late as in B5, and the fatal records of the one 1 km mesh with q < 0.05.
3. 2020 census night population of the 1 km meshes against their accident count and P (Spearman).
4. OSM road names (2026-08-31) by length inside the top 10 500 m meshes and the 1 km mesh with q < 0.05.
Writes outputs/explore.json, outputs/top_mesh_roads.csv, outputs/m1000_hit_fatal.csv.
"""
import importlib
import json
import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
an = importlib.import_module("02_anomaly")
import fatalshare as fs  # noqa: E402

OUT, ART = an.OUT, an.ART
CENSUS = "hf://datasets/yuiseki/estat-census-mesh-2020@6c486c8649484e09e549c0c99b5fa89b4f416edb/parquet/T001140.parquet"
OSM = "hf://datasets/yuiseki/osm-japan-src-2026-08@9a9b4a77e89e28a66bf15781644a16b63501f622/parquet/planet_osm_line.parquet"
CAR = ("motorway", "trunk", "primary", "secondary", "tertiary", "unclassified", "residential", "living_street",
       "motorway_link", "trunk_link", "primary_link", "secondary_link", "tertiary_link")


def mesh_bounds(code):
    lat = int(code[:2]) / 1.5 + int(code[4]) / 12 + int(code[6]) / 120
    lon = int(code[2:4]) + 100 + int(code[5]) / 8 + int(code[7]) / 80
    dlat, dlon = 1 / 120, 1 / 80
    for ch in code[8:]:
        dlat, dlon = dlat / 2, dlon / 2
        lat += dlat * ((int(ch) - 1) // 2)
        lon += dlon * ((int(ch) - 1) % 2)
    return lon, lat, lon + dlon, lat + dlat


def perm_T(d, lab, rng):
    share = pd.Series(d.fatal.values).groupby(lab).transform("mean").values
    t_obs = fs.overdispersion(d.m500.values, d.fatal.values, share)
    null = np.array([fs.overdispersion(d.m500.values, fs.permute_within(lab, d.fatal.values, rng), share)
                     for _ in range(an.N_PERM)])
    return dict(T_obs=round(t_obs, 2), null_p95=round(float(np.quantile(null, 0.95)), 2),
                p_perm=round(float(((null >= t_obs).sum() + 1) / (an.N_PERM + 1)), 4), strata=int(len(set(lab))))


def main():
    d = an.load()
    res = {}
    # 1
    for extra in ("motorway", "vulnerable"):
        lab, _ = an.strata(d, (extra,))
        res[f"T_plus_{extra}"] = perm_T(d, lab, np.random.default_rng(an.SEED))
        print(extra, res[f"T_plus_{extra}"], flush=True)

    # 2
    m1 = pd.read_csv(OUT / "meshes_m1000.csv", dtype={"unit": str, "city": str})
    hit = m1[m1.q < 0.05].unit.tolist()
    early, late = d[d.occ_year <= 2022].reset_index(drop=True), d[d.occ_year >= 2023].reset_index(drop=True)
    me, _, _ = an.score(early, "m1000")
    lab_l, _ = an.strata(late)
    p_l = fs.leave_unit_out_p(lab_l, late.m1000.values, late.fatal.values, {})
    pers = {}
    for name, sel in (("anomaly_top20", me.unit.head(20).tolist()), ("hit", hit)):
        mask = late.m1000.isin(set(sel)).values
        o, pp = int(late.fatal.values[mask].sum()), p_l[mask]
        e_rows = me.set_index("unit").reindex(sel)
        pers[name] = dict(units=" ".join(sel), early_O=int(e_rows.O.sum()), early_E=round(float(e_rows.E.sum()), 3),
                          late_O=o, late_E=round(float(pp.sum()), 3), late_P=float(fs.poibin_sf(pp, o)))
    res["m1000_persistence"] = pers
    print(pers, flush=True)
    f = d[d.m1000.isin(hit) & (d.fatal == 1)]
    f[["m1000", "m500", "occ_year", "shape_g", "width_g", "median_g", "motorway", "vulnerable", "accident_type",
       "party_a", "party_b", "route", "latitude", "longitude"]].sort_values("occ_year").to_csv(
        OUT / "m1000_hit_fatal.csv", index=False, encoding="utf-8")

    # 3
    pop = duckdb.sql(f"""select KEY_CODE unit, sum(cast(T001140001 as bigint)) pop from '{CENSUS}'
                         where KEY_CODE in ({",".join(f"'{u}'" for u in m1.unit)}) group by 1""").df()
    j = m1.merge(pop, on="unit", how="left")
    j["pop"] = j["pop"].fillna(0)
    res["census_1km"] = dict(meshes=int(len(j)), meshes_without_census_row=int((j["pop"] == 0).sum()),
                             spearman_pop_n=round(float(spearmanr(j["pop"], j.n).statistic), 4),
                             spearman_pop_minus_log10_P=round(float(-spearmanr(j["pop"], j.P).statistic), 4))
    print(res["census_1km"], flush=True)

    # 4
    cache = ART / "osm_car_roads_23.parquet"
    c = duckdb.connect()
    c.execute("load spatial")
    c.execute("set geometry_always_xy = true")
    if not cache.exists():
        lon0, lat0, lon1, lat1 = d.longitude.min(), d.latitude.min(), d.longitude.max(), d.latitude.max()
        x0, y0 = c.execute(f"select st_x(p), st_y(p) from (select st_transform(st_point({lon0}, {lat0}), 'EPSG:4326', 'EPSG:3857') p)").fetchone()
        x1, y1 = c.execute(f"select st_x(p), st_y(p) from (select st_transform(st_point({lon1}, {lat1}), 'EPSG:4326', 'EPSG:3857') p)").fetchone()
        c.execute(f"""copy (select osm_id, highway, name, ref, st_aswkb(st_transform(way, 'EPSG:3857', 'EPSG:6677')) wkb
            from '{OSM}' where highway in {CAR} and bbox.xmax >= {x0} and bbox.xmin <= {x1}
            and bbox.ymax >= {y0} and bbox.ymin <= {y1}) to '{cache}' (format parquet)""")
    tops = pd.read_csv(OUT / "meshes_main.csv", dtype={"unit": str}).head(10).unit.tolist() + hit
    rows = []
    for u in tops:
        lo0, la0, lo1, la1 = mesh_bounds(u)
        q = c.execute(f"""with m as (select st_transform(st_makeenvelope({lo0}, {la0}, {lo1}, {la1}), 'EPSG:4326', 'EPSG:6677') g)
            select coalesce(name, '(名前なし)') name, highway, sum(st_length(st_intersection(st_geomfromwkb(wkb), m.g))) len_m
            from '{cache}', m where st_intersects(st_geomfromwkb(wkb), m.g) group by all order by len_m desc limit 6""").df()
        for r in q.itertuples():
            rows.append(dict(unit=u, name=r.name, highway=r.highway, length_m=round(r.len_m, 1)))
    rr = pd.DataFrame(rows)
    rr.to_csv(OUT / "top_mesh_roads.csv", index=False, encoding="utf-8")
    print(rr.to_string(), flush=True)
    (OUT / "explore.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
