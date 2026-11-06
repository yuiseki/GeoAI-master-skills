"""B7 (exploratory): the same stratified fatal-share score with OSM road links as the unit.

systemd-run --user --scope -q -p MemoryMax=8G -p MemorySwapMax=0 -p CPUQuota=400% -- \
  uvx --from 'duckdb>=1.5.5' --with numpy --with scipy --with pandas --with pyarrow --with shapely --with pyproj \
  python -u scripts/06_links.py

Links: the car roads of artifacts/.../osm_car_roads_23.parquet (03_explore.py), noded where they meet or cross
and merged at degree-2 points (fatalshare.build_links). Each accident goes to the nearest link within 30 m.
Strata, leave-unit-out shares, P and BH as in 02_anomaly.py, on the accidents that got a link.
Writes artifacts/.../links.parquet (every link, its counts and geometry, EPSG:6677), outputs/links_top20.csv,
outputs/links_summary.json.
"""
import importlib
import json
import sys
import time
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import shapely
from pyproj import Transformer

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
an = importlib.import_module("02_anomaly")
import fatalshare as fs  # noqa: E402

MAX_M = 30.0


def main():
    t0 = time.time()
    c = duckdb.connect()
    w = c.execute(f"select highway, name, wkb from '{an.ART / 'osm_car_roads_23.parquet'}'").df()
    ways = shapely.from_wkb(w.wkb.map(bytes))
    links = fs.build_links(ways)
    print(f"{len(ways)} ways -> {len(links)} links, {time.time() - t0:.0f} s", flush=True)

    d = an.load()
    x, y = Transformer.from_crs("EPSG:4326", "EPSG:6677", always_xy=True).transform(d.longitude.values, d.latitude.values)
    d["link"] = fs.assign_nearest(links, np.c_[x, y], MAX_M)
    unassigned = int((d.link < 0).sum())
    unassigned_fatal = int(((d.link < 0) & (d.fatal == 1)).sum())
    dl = d[d.link >= 0].reset_index(drop=True)
    m, lab, min_n = an.score(dl, "link")
    tv = an.turnover(m)

    # names of the links: the nearest original way to the link's midpoint
    geo = np.asarray(links, dtype=object)
    mid = shapely.line_interpolate_point(geo, 0.5, normalized=True)
    tree = shapely.STRtree(ways)
    near = tree.nearest(mid)
    names = w.name.fillna("(名前なし)").values[near]
    hw = w.highway.values[near]
    m["name"] = m.unit.map(lambda i: names[i])
    m["highway"] = m.unit.map(lambda i: hw[i])
    m["length_m"] = m.unit.map(lambda i: round(geo[i].length, 1))
    m500 = dl.groupby("link").m500.agg(lambda s: s.mode().iloc[0])
    m["m500"] = m.unit.map(m500)
    m["ward"] = m.city.map(dict(zip(*[duckdb.sql(f"select substr(code5, 3), name from '{an.ADMIN}' "
                                                 "where code5 like '131%'").df()[k] for k in ("substr(code5, 3)", "name")])))
    top = m.head(20)
    top.to_csv(an.OUT / "links_top20.csv", index=False, encoding="utf-8")

    main_top10 = set(pd.read_csv(an.OUT / "meshes_main.csv", dtype={"unit": str}).unit.head(10))
    s = dict(ways=int(len(ways)), links=int(len(links)), max_m=MAX_M, accidents=int(len(d)),
             unassigned=unassigned, unassigned_fatal=unassigned_fatal, assigned=int(len(dl)),
             assigned_fatal=int(dl.fatal.sum()), links_with_accident=int(len(m)),
             links_with_fatal=int((m.O > 0).sum()), strata=int(len(set(lab))), min_n_stratum=min_n,
             q_lt_005=int((m.q < 0.05).sum()), q_lt_010=int((m.q < 0.10).sum()), min_P=float(m.P.min()),
             min_q=float(m.q.min()), P_zero=int((m.P == 0).sum()),
             min_P_nonzero=float(m.P[m.P > 0].min()),
             P_needed_first=0.05 / len(m), q_lt_005_nonzero_P=int(((m.q < 0.05) & (m.P > 0)).sum()), k_needed_median=float(m.k_needed.median()),
             accidents_per_link_median=float(m.n.median()), max_O=int(m.O.max()),
             top10_in_main_top10_meshes=int(top.head(10).m500.isin(main_top10).sum()), turnover=tv,
             seconds=round(time.time() - t0, 1))
    (an.OUT / "links_summary.json").write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(s, ensure_ascii=False, indent=1))
    print(top[["anomaly_rank", "unit", "name", "highway", "length_m", "ward", "m500", "n", "O", "E", "P", "q",
               "count_rank"]].to_string())

    allm = pd.DataFrame({"link": np.arange(len(links))}).merge(
        m[["unit", "n", "O", "E", "P", "anomaly_rank"]].rename(columns={"unit": "link"}), on="link", how="left")
    allm["n"] = allm.n.fillna(0).astype(int)
    allm["O"] = allm.O.fillna(0).astype(int)
    allm["name"] = names
    allm["wkb"] = shapely.to_wkb(geo)
    c.execute("load spatial")
    c.register("a", allm)
    c.execute(f"copy (select * exclude (wkb), st_geomfromwkb(wkb) geometry from a) "
              f"to '{an.ART / 'links.parquet'}' (format parquet)")


if __name__ == "__main__":
    main()
