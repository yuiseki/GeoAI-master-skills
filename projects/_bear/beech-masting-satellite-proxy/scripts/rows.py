"""Site x target-year rows (EXPERIMENT_PLAN.md), Tohoku only.

    load(outputs, max_rank_year) -> rows, ranks, sites, raw, provenance

rows: ID, t, y, lag_own, dT, x, y_m for t = 1990-2008 with a valid rank at t (ranks up to max_rank_year only).
ranks: ID, year, rank (0-3; -1 and NULL dropped). sites: ID, lat, lon, x, y_m (EPSG:6691).
raw: outputs/satellite_seasonal.csv for the Tohoku sites. dT = Ts(t - 1) - Ts(t - 2) from
projects/_bear/beech-masting-spatial-proxy/outputs/site_year_climate.csv (the same file and definition as there).
"""

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

DRYAD = "hf://datasets/yuiseki/fagus-crenata-masting-jp-2026-06@db40a09e24cbc02d6f19a7180bafe5f04962f8f8/parquet/"
TARGETS = range(1990, 2009)
TOHOKU = "Tohoku region in Honshu"
CLIMATE = Path(__file__).resolve().parents[2] / "beech-masting-spatial-proxy/outputs/site_year_climate.csv"


def delta_t(climate):
    ts = climate.set_index(["ID", "year"]).Ts
    out = [{"ID": i, "t": t, "dT": ts[(i, t - 1)] - ts[(i, t - 2)]} for i in sorted(climate.ID.unique()) for t in TARGETS]
    return pd.DataFrame(out)


def build(ranks, climate, sites, max_rank_year=2008):
    ranks = ranks[ranks.year <= max_rank_year]
    r = ranks.set_index(["ID", "year"])["rank"]
    rows = ranks[ranks.year.isin(TARGETS)].rename(columns={"year": "t", "rank": "y"}).copy()
    rows["lag_own"] = [r.get((i, t - 1), np.nan) for i, t in zip(rows.ID, rows.t)]
    n0 = len(rows)
    rows = rows.merge(delta_t(climate), on=["ID", "t"], how="left").merge(sites[["ID", "x", "y_m"]], on="ID", how="left")
    if len(rows) != n0 or rows.drop(columns="lag_own").isna().any().any():
        raise ValueError("a row lost its dT or position")
    return rows.sort_values(["t", "ID"]).reset_index(drop=True), ranks


def load_sites(con, region=TOHOKU):
    from pyproj import Transformer

    s = con.sql(f"""select ID, Latitude lat, Longitude lon from '{DRYAD}study_sites.parquet'
                    where Location = '{region}' order by ID""").df()
    x, y = Transformer.from_crs("EPSG:4326", "EPSG:6691", always_xy=True).transform(s.lon.to_numpy(), s.lat.to_numpy())
    return s.assign(x=x, y_m=y)


def load(outputs, max_rank_year=2008):
    import duckdb

    outputs = Path(outputs)
    con = duckdb.connect()
    con.sql("install httpfs; load httpfs")
    sites = load_sites(con)
    if len(sites) != 98:
        raise ValueError("expected 98 Tohoku sites")
    v = con.sql(f"""unpivot (select ID, columns('Obs.seed.rnk.*') from '{DRYAD}seed_rank_and_cues.parquet'
                    where ID in (select ID from '{DRYAD}study_sites.parquet' where Location = '{TOHOKU}'))
                    on columns('Obs.*') into name k value rank""").df()
    v["year"] = v.k.str[-4:].astype(int)
    ranks = v[v["rank"].between(0, 3)][["ID", "year", "rank"]].astype({"rank": float}).reset_index(drop=True)
    climate = pd.read_csv(CLIMATE)
    rows, ranks = build(ranks, climate, sites, max_rank_year)
    raw = pd.read_csv(outputs / "satellite_seasonal.csv")
    raw = raw[raw.ID.isin(sites.ID)].reset_index(drop=True)
    prov = {"climate_csv": str(CLIMATE.relative_to(CLIMATE.parents[4])),
            "climate_sha256": hashlib.sha256(CLIMATE.read_bytes()).hexdigest(),
            "satellite_seasonal_sha256": hashlib.sha256((outputs / "satellite_seasonal.csv").read_bytes()).hexdigest()}
    return rows, ranks, sites, raw, prov
