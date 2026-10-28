"""Site x target-year rows for the models (EXPERIMENT_PLAN.md).

    build(ranks, climate, terrain, sites, radius) -> rows for t = 1990-2008 with a valid rank at t

ranks: ID, year, rank (0-3 only; -1 and NULL already dropped). climate: outputs/site_year_climate.csv.
terrain: outputs/terrain_sites.csv. sites: ID, x, y_m (EPSG:6691). radius picks relief_/tpi_ (300 or 1000).

    load(outputs) -> ranks, climate, terrain, sites   (reads Dryad at the fixed revision; Tohoku only)
"""

from pathlib import Path

import numpy as np
import pandas as pd

DRYAD = "hf://datasets/yuiseki/fagus-crenata-masting-jp-2026-06@db40a09e24cbc02d6f19a7180bafe5f04962f8f8/parquet/"
TARGETS = range(1990, 2009)
CLIMATE_COLS = ["dT", "Ts1", "Ts2", "Tsp", "P", "PET", "WB"]


def climate_by_t(climate):
    """Per site and target year t: dT, Ts(t-1), Ts(t-2), Tsp(t), P(t-1), PET(t-1), WB(t-1)."""
    c = climate.set_index(["ID", "year"])
    out = []
    for (i, t) in [(i, t) for i in sorted(climate.ID.unique()) for t in TARGETS]:
        ts1, ts2 = c.at[(i, t - 1), "Ts"], c.at[(i, t - 2), "Ts"]
        p, pet = c.at[(i, t - 1), "P"], c.at[(i, t - 1), "PET"]
        out.append({"ID": i, "t": t, "dT": ts1 - ts2, "Ts1": ts1, "Ts2": ts2, "Tsp": c.at[(i, t), "Tsp"],
                    "P": p, "PET": pet, "WB": p - pet})
    return pd.DataFrame(out)


def build(ranks, climate, terrain, sites, radius):
    r = ranks.set_index(["ID", "year"])["rank"]
    rows = ranks[ranks.year.isin(TARGETS)].rename(columns={"year": "t", "rank": "y"}).copy()
    rows["lag_own"] = [r.get((i, t - 1), np.nan) for i, t in zip(rows.ID, rows.t)]
    n0 = len(rows)
    rows = rows.merge(climate_by_t(climate), on=["ID", "t"], how="left")
    ter = terrain[["ID", "alt", "slope", "northness", "eastness", f"relief_{radius}", f"tpi_{radius}"]].rename(
        columns={"alt": "elev", f"relief_{radius}": "relief", f"tpi_{radius}": "tpi"})
    rows = rows.merge(ter, on="ID", how="left").merge(sites[["ID", "x", "y_m"]], on="ID", how="left")
    if len(rows) != n0 or rows.drop(columns="lag_own").isna().any().any():
        raise ValueError("a row lost its climate, terrain or position")
    return rows.sort_values(["t", "ID"]).reset_index(drop=True)


def load(outputs):
    import duckdb
    from pyproj import Transformer

    outputs = Path(outputs)
    con = duckdb.connect()
    con.sql("install httpfs; load httpfs")
    s = con.sql(f"""select ID, Latitude lat, Longitude lon from '{DRYAD}study_sites.parquet'
                    where Location = 'Tohoku region in Honshu' order by ID""").df()
    v = con.sql(f"""unpivot (select ID, columns('Obs.seed.rnk.*') from '{DRYAD}seed_rank_and_cues.parquet'
                    where ID in (select ID from '{DRYAD}study_sites.parquet' where Location = 'Tohoku region in Honshu'))
                    on columns('Obs.*') into name k value rank""").df()
    if len(s) != 98:
        raise ValueError("expected 98 Tohoku sites")
    v["year"] = v.k.str[-4:].astype(int)
    ranks = v[v["rank"].between(0, 3)][["ID", "year", "rank"]].astype({"rank": float}).reset_index(drop=True)
    x, y = Transformer.from_crs("EPSG:4326", "EPSG:6691", always_xy=True).transform(s.lon.to_numpy(), s.lat.to_numpy())
    sites = s.assign(x=x, y_m=y)
    climate = pd.read_csv(outputs / "site_year_climate.csv")
    terrain = pd.read_csv(outputs / "terrain_sites.csv")
    return ranks, climate, terrain, sites
