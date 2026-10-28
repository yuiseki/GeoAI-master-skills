"""MODIS (Terra, collection 6.1, Planetary Computer) at the 98 Tohoku beech sites, and the satellite cues of B5
(EXPERIMENT_PLAN.md, the details fixed on 2026-10-28 before any value was read):

    S1 MOD11A2 LST_Day_1km, composites starting 1 July to 31 August; QC_Day bits 0-1 in {0, 1}, value != 0;
       scale 0.02 K. A site-year needs 4 valid composites.
    S2 MOD17A3HGF Npp_500m; values above 32,700 are fill; scale 0.0001 kgC/m2/yr.
    S3 MOD13A1 EVI (exploratory); pixel_reliability 0 or 1; composite date = start + 8 days; March-July; a
       site-year needs 6 valid composites; green-up = first date with EVI >= (min + max) / 2.

A prefecture-year is the mean over its valid sites. S1 and S2 become anomalies from the prefecture's 2001-2010
mean.

From repository root:
    env -u GDAL_DATA -u GDAL_DRIVER_PATH -u PROJ_DATA -u PROJ_NETWORK \
      uvx --with rasterio --with pystac-client --with planetary-computer --with pandas --with pyarrow python \
      projects/beech-masting-triggers/scripts/satellite.py projects/beech-masting-triggers/outputs \
      artifacts/beech-masting-triggers
"""

import argparse
import datetime as dt
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

STAC = "https://planetarycomputer.microsoft.com/api/stac/v1"
BBOX = [139.4, 37.5, 142.2, 41.6]
YEARS = range(2001, 2026)
BASE = (2001, 2010)
PRODUCTS = {
    "S1": {"collection": "modis-11A2-061", "assets": ["LST_Day_1km", "QC_Day"], "window": ("07-01", "08-31")},
    "S2": {"collection": "modis-17A3HGF-061", "assets": ["Npp_500m"], "window": ("01-01", "12-31")},
    "S3": {"collection": "modis-13A1-061", "assets": ["500m_16_days_EVI", "500m_16_days_pixel_reliability"],
           "window": ("02-24", "07-31")},
}


def lst_c(value, qc):
    """LST in °C, or NaN when the pixel is not a produced value."""
    value, qc = np.asarray(value, float), np.asarray(qc, int)
    ok = ((qc & 0b11) <= 1) & (value != 0)
    return np.where(ok, value * 0.02 - 273.15, np.nan)


def npp(value):
    value = np.asarray(value, float)
    return np.where(value <= 32700, value * 0.0001, np.nan)


def evi(value, reliability):
    value, reliability = np.asarray(value, float), np.asarray(reliability, int)
    return np.where((reliability == 0) | (reliability == 1), value * 0.0001, np.nan)


def greenup(days, values, need=6):
    """First day whose EVI reaches the midpoint of the year's valid minimum and maximum; NaN with too few."""
    days, values = np.asarray(days, float), np.asarray(values, float)
    ok = np.isfinite(values)
    if ok.sum() < need:
        return np.nan
    d, v = days[ok], values[ok]
    order = np.argsort(d)
    d, v = d[order], v[order]
    mid = (v.min() + v.max()) / 2
    return float(d[np.argmax(v >= mid)])


def site_years(raw, cue):
    """raw: site, pref, year, date, value (one row per composite). One value per site and year."""
    if cue == "S1":
        g = raw.dropna(subset=["value"]).groupby(["ID", "pref", "year"])["value"].agg(["mean", "count"]).reset_index()
        return g[g["count"] >= 4].rename(columns={"mean": "value"})[["ID", "pref", "year", "value"]]
    if cue == "S2":
        return raw.dropna(subset=["value"])[["ID", "pref", "year", "value"]]
    rows = []
    for (sid, pref, year), g in raw[raw.date.dt.month.between(3, 7)].groupby(["ID", "pref", "year"]):
        rows.append({"ID": sid, "pref": pref, "year": year, "value": greenup(g.date.dt.day_of_year, g.value)})
    return pd.DataFrame(rows).dropna(subset=["value"])


def prefecture_cue(sy, cue, anomaly=True):
    p = sy.groupby(["pref", "year"])["value"].agg(["mean", "count"]).reset_index()
    p = p.rename(columns={"mean": cue + "_raw", "count": cue + "_sites"})
    if anomaly:
        base = p[p.year.between(*BASE)].groupby("pref")[cue + "_raw"].mean().rename("base")
        p = p.join(base, on="pref")
        p[cue] = p[cue + "_raw"] - p["base"]
        p = p.drop(columns="base")
    else:
        p[cue] = p[cue + "_raw"]
    return p


def latest_versions(jobs):
    """One item per tile and start date: MODIS ids end in the production time (MOD17A3HGF.A2013001.h28v04.061.
    2021324233025); reprocessed copies of the same granule are dropped, keeping the latest."""
    best = {}
    for job in jobs:
        parts = job[0].split(".")
        key = (parts[0], parts[1], parts[2])
        if key not in best or parts[4] > best[key][0].split(".")[4]:
            best[key] = job
    return sorted(best.values(), key=lambda j: j[0])


def sample(item_assets, sites):
    """Values of each asset at the sites inside the raster: {asset: array over sites (NaN outside)}."""
    import planetary_computer as pc
    import rasterio
    from rasterio.warp import transform

    out = {}
    for name, href in item_assets.items():
        with rasterio.open(pc.sign(href)) as src:
            xs, ys = transform("EPSG:4326", src.crs, sites.lon.tolist(), sites.lat.tolist())
            inside = [(src.bounds.left <= x < src.bounds.right) and (src.bounds.bottom < y <= src.bounds.top)
                      for x, y in zip(xs, ys)]
            vals = np.full(len(sites), np.nan)
            pts = [(x, y) for (x, y), i in zip(zip(xs, ys), inside) if i]
            if pts:
                vals[np.array(inside)] = [v[0] for v in src.sample(pts)]
            out[name] = vals
    return out


def collect(cue, sites, art):
    import pystac_client

    spec = PRODUCTS[cue]
    cat = pystac_client.Client.open(STAC)
    jobs = []
    for y in YEARS:
        a, b = spec["window"]
        items = cat.search(collections=[spec["collection"]], bbox=BBOX, datetime=f"{y}-{a}/{y}-{b}").items()
        for it in items:
            if not it.id.startswith("MOD"):  # Terra; the platform property is missing on some items
                continue
            start = dt.date.fromisoformat((it.properties.get("start_datetime") or it.datetime.isoformat())[:10])
            jobs.append((it.id, start, {k: it.assets[k].href for k in spec["assets"]}))

    n_found = len(jobs)
    jobs = latest_versions(jobs)

    def run(job):
        iid, start, assets = job
        v = sample(assets, sites)
        return iid, start, v

    rows = []
    with ThreadPoolExecutor(8) as ex:
        for iid, start, v in ex.map(run, jobs):
            if cue == "S1":
                value = lst_c(np.nan_to_num(v["LST_Day_1km"]), np.nan_to_num(v["QC_Day"], nan=3).astype(int))
                inside = np.isfinite(v["LST_Day_1km"])
            elif cue == "S2":
                value = npp(np.nan_to_num(v["Npp_500m"], nan=32767))
                inside = np.isfinite(v["Npp_500m"])
            else:
                value = evi(np.nan_to_num(v["500m_16_days_EVI"]),
                            np.nan_to_num(v["500m_16_days_pixel_reliability"], nan=-1).astype(int))
                inside = np.isfinite(v["500m_16_days_EVI"])
            date = start + dt.timedelta(days=8) if cue == "S3" else start
            for i in np.flatnonzero(inside):
                rows.append({"item": iid, "ID": int(sites.ID.iloc[i]), "pref": sites.pref.iloc[i],
                             "year": start.year, "date": pd.Timestamp(date), "value": float(value[i])})
    raw = pd.DataFrame(rows)
    raw.to_parquet(art / f"modis_{cue}_sites.parquet", index=False)
    if raw.duplicated(["ID", "date"]).any():
        raise ValueError(f"{cue}: a site has two values for one composite")
    return raw, {"found": n_found, "used": len(jobs)}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("outputs", type=Path)
    ap.add_argument("art", type=Path)
    ap.add_argument("--cues", default="S1,S2,S3")
    a = ap.parse_args()
    sites = pd.read_csv(a.outputs / "dryad_sites.csv")
    sites = sites[sites.pref != "北海道"].reset_index(drop=True)
    merged, audit = None, {}
    for cue in a.cues.split(","):
        raw, n_items = collect(cue, sites, a.art)
        per_year = raw.groupby("year").ID.nunique()
        sy = site_years(raw, cue)
        p = prefecture_cue(sy, cue, anomaly=cue != "S3")
        audit[cue] = {"items": n_items, "rows": len(raw), "valid_rows": int(raw.value.notna().sum()),
                      "sites_seen": int(raw.ID.nunique()), "site_years": len(sy), "pref_years": len(p),
                      "years": [int(p.year.min()), int(p.year.max())],
                      "years_with_fewer_than_98_sites": {int(k): int(v) for k, v in per_year[per_year < 98].items()}}
        print(cue, audit[cue], flush=True)
        merged = p if merged is None else merged.merge(p, on=["pref", "year"], how="outer")
    merged.sort_values(["pref", "year"]).to_csv(a.outputs / "cues_satellite.csv", index=False, float_format="%.5f")
    pd.Series(audit).to_json(a.outputs / "cues_satellite_audit.json", force_ascii=False, indent=2)


if __name__ == "__main__":
    main()
