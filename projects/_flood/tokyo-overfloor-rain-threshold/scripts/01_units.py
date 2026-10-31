"""Build the survey units of the Tokyo flood record and the gauge events with their nearest JMA station.

uvx --from 'duckdb>=1.5.5' --with numpy --with pandas --with pyarrow python scripts/01_units.py

Inputs are the pinned copies fetched by projects/_flood/tokyo23-flood-record-vs-a31a/scripts/01_fetch.py
(tokyo-flood-record-jp@354b0d9, jma-rain-tokyo@4391f76). Writes, under artifacts/_flood/tokyo-overfloor-rain-threshold/:
- units.parquet: one row per survey unit (the 7 columns of the plan), with rain, utf, otf, ward, reason class, period;
- gauge_events.parquet: one row per (dis_date_s, nro_name, rain) of units with nro_flag 0, with the nearest JMA station;
and outputs/units_summary.json.
"""
import json
from pathlib import Path

import duckdb
import pandas as pd

from overfloor import count, nearest_station, rain60

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
RAW = ROOT / "artifacts/_flood/tokyo23-flood-record-vs-a31a/raw"
ART = ROOT / "artifacts/_flood/tokyo-overfloor-rain-threshold"
# spelling variants of ward names in the record (counting only; a unit keeps its own spelling)
SPELLING = {"世田ヶ谷区": "世田谷区", "太田区": "大田区"}
KEY = ["layer", "munic", "dis_name", "dis_date_s", "district_k", "area", "tot_bldg"]


def load_rows():
    con = duckdb.connect()
    con.execute("load spatial")
    return con.sql(f"""select layer, munic, dis_name, dis_date_s, dis_date_e, coalesce(district, district0) district_k,
        area, tot_bldg, reason, nro_name, nro_60min, nro_flag, utf_bldg, otf_bldg,
        st_x(st_centroid(geometry)) lon, st_y(st_centroid(geometry)) lat
        from '{RAW / 'flood_record_area.parquet'}'""").df()


def reason_class(r):
    if r == "内水":
        return "naisui"
    if r and "溢水" in r:
        return "issui"
    return "other"


def to_units(rows):
    rows = rows.copy()
    rows["rain"] = rows["nro_60min"].map(rain60)
    rows["utf"] = rows["utf_bldg"].map(count)
    rows["otf"] = rows["otf_bldg"].map(count)
    g = rows.groupby(KEY, dropna=False)
    u = g.agg(rain=("rain", "max"), utf=("utf", "max"), otf=("otf", "max"), reason=("reason", "first"),
              nro_name=("nro_name", "first"), nro_flag=("nro_flag", "min"), dis_date_e=("dis_date_e", "max"),
              lon=("lon", "mean"), lat=("lat", "mean"), n_rows=("lon", "size")).reset_index()
    u = u[u["dis_date_s"].notna()].copy()
    u["day"] = pd.to_datetime(u["dis_date_s"])
    u["ward"] = u["munic"].str.endswith("区")
    u["cls"] = u["reason"].map(reason_class)
    u["period"] = (u["day"].dt.year <= 1996).map({True: "first", False: "second"})
    return u


def gauge_events(u):
    con = duckdb.connect()
    st = con.sql(f"select station_id, station_name, lon, lat from '{RAW / 'rain_stations.parquet'}' where lat >= 35.5").df()
    daily = con.sql(f"""select station_id, date, max1h_mm from '{RAW / 'rain_daily.parquet'}'
        where station_id in (select station_id from '{RAW / 'rain_stations.parquet'}' where lat >= 35.5)""").df()
    daily["date"] = pd.to_datetime(daily["date"])
    e = u[(u["nro_flag"] == 0) & u["rain"].notna()]
    e = e.groupby(["day", "nro_name", "rain"], dropna=False).agg(
        end=("dis_date_e", "max"), lon=("lon", "mean"), lat=("lat", "mean"), units=("lon", "size")).reset_index()
    out = []
    for r in e.itertuples():
        end = pd.to_datetime(r.end) if pd.notna(r.end) else r.day
        w = daily[(daily["date"] >= r.day) & (daily["date"] <= end)].groupby("station_id")["max1h_mm"].max()
        s = st.assign(max1h=st["station_id"].map(w))
        sid, dist, v = nearest_station(r.lon, r.lat, s)
        out.append({"station_id": sid, "km": dist, "jma_max1h": v, "jma_any_max1h": float(s["max1h"].max())})
    return pd.concat([e, pd.DataFrame(out, index=e.index)], axis=1)


def main():
    ART.mkdir(parents=True, exist_ok=True)
    rows = load_rows()
    u = to_units(rows)
    u.to_parquet(ART / "units.parquet")
    ge = gauge_events(u)
    ge.to_parquet(ART / "gauge_events.parquet")
    wards = u.loc[u["ward"], "munic"].replace(SPELLING).nunique()
    summary = {"first_period": [1974, 1996], "second_period": [1997, 2019], "wards_scope": 23, "wards_with_records": wards,
               "rows": len(rows), "units_with_date": len(u),
               "units_without_date": int(rows.groupby(KEY, dropna=False).ngroups - len(u)),
               "units_with_rain": int(u["rain"].notna().sum()), "disaster_days": int(u["day"].nunique()),
               "ward_naisui_by_period": u[u["ward"] & (u["cls"] == "naisui")].groupby("period").size().to_dict(),
               "gauge_events_flag0": len(ge), "gauge_events_ge50": int((ge["rain"] >= 50).sum())}
    (HERE.parent / "outputs/units_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n")
    print(summary)


if __name__ == "__main__":
    main()
