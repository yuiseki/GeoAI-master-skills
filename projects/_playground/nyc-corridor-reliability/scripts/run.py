"""NYC corridor travel time reliability from open data: the Roads Management Insights example "compare morning and
evening rush-hour delays across corridors", with route-level TTI and LOTTR, on the NYC DOT Traffic Speeds feed.

    uvx --python 3.12 --with pandas --with numpy --with pyarrow --with matplotlib python scripts/run.py STEP

Steps: fetch, prepare, quality, metrics, corridors, maps (or all). Raw pages and Parquet go to
artifacts/_playground/nyc-corridor-reliability/, the tables the report cites to outputs/.
"""

import json
import math
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
ROOT = HERE.parents[2]
ART = ROOT / "artifacts" / "_playground" / "nyc-corridor-reliability"
OUT = HERE / "outputs"
SKILL = ROOT / ".agents" / "skills" / "travel-time-reliability" / "scripts"
API = "https://data.cityofnewyork.us/resource/i4gi-tjb9.json"
START, END = "2026-10-01", "2026-11-01"          # October 2026, end exclusive
HOLIDAYS = ["2026-10-12"]                         # Columbus Day / Indigenous Peoples' Day (federal holiday)
COLS = "id,speed,travel_time,status,data_as_of,link_id,link_name,borough,owner,link_points"


def get(params):
    url = API + "?" + urllib.parse.urlencode(params)
    for attempt in range(5):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "GeoAI-master-skills"})
            with urllib.request.urlopen(req, timeout=300) as r:
                return json.load(r)
        except Exception as e:                      # retried, then raised
            print("retry", attempt, e, flush=True)
            time.sleep(10 * (attempt + 1))
    raise SystemExit(f"failed: {url}")


def fetch_day(day):
    import pandas as pd
    f = ART / "raw" / f"{day.date()}.json"
    if f.exists():
        return
    rows, off = [], 0
    a, b = day.strftime("%Y-%m-%dT00:00:00"), (day + pd.Timedelta(days=1)).strftime("%Y-%m-%dT00:00:00")
    while True:
        page = get({"$select": COLS, "$where": f"data_as_of >= '{a}' and data_as_of < '{b}'",
                    "$order": "data_as_of, id", "$limit": 50000, "$offset": off})
        rows += page
        off += len(page)
        if len(page) < 50000:
            break
    tmp = f.with_suffix(".part")
    tmp.write_text(json.dumps(rows), encoding="utf-8")
    tmp.rename(f)
    print(day.date(), len(rows), flush=True)


def fetch():
    """One JSON file per day, every row of the day, paged by 50,000. Four days at a time (the API takes minutes
    per day)."""
    import pandas as pd
    from concurrent.futures import ThreadPoolExecutor
    (ART / "raw").mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(4) as ex:
        list(ex.map(fetch_day, pd.date_range(START, END, inclusive="left")))


def prepare():
    """Observations (link, time, travel_time_s, speed_mph, status) and links (id, name, borough, length, geometry)."""
    import pandas as pd
    frames = [pd.DataFrame(json.loads(f.read_text(encoding="utf-8"))) for f in sorted((ART / "raw").glob("*.json"))]
    d = pd.concat(frames, ignore_index=True)
    n_raw = len(d)
    d["time"] = pd.to_datetime(d["data_as_of"])
    d["travel_time_s"] = pd.to_numeric(d["travel_time"], errors="coerce")
    d["speed_mph"] = pd.to_numeric(d["speed"], errors="coerce")
    d["status"] = pd.to_numeric(d["status"], errors="coerce")
    d = d.drop_duplicates(["link_id", "data_as_of"])
    d.rename(columns={"link_id": "link"})[["link", "time", "travel_time_s", "speed_mph", "status"]].to_parquet(
        ART / "obs_all.parquet", index=False)
    links = d.sort_values("time").groupby("link_id").tail(1)[["link_id", "link_name", "borough", "owner", "link_points"]]
    links.to_parquet(ART / "links.parquet", index=False)
    json.dump({"rows_fetched": n_raw, "rows_after_dedup": len(d), "links": int(d["link_id"].nunique()),
               "first": str(d["time"].min()), "last": str(d["time"].max()), "days": int(d["time"].dt.date.nunique())},
              open(OUT / "prepare.json", "w", encoding="utf-8"), indent=1)


def quality():
    """What the status codes mean in practice, how often a link reports, and runs of a repeated value."""
    import pandas as pd
    d = pd.read_parquet(ART / "obs_all.parquet")
    s = d.groupby("status").agg(rows=("link", "size"), median_speed=("speed_mph", "median"),
                                zero_tt=("travel_time_s", lambda x: int((x <= 0).sum()))).reset_index()
    s.to_csv(OUT / "status_codes.csv", index=False)
    d = d.sort_values(["link", "time"])
    d["gap_s"] = d.groupby("link")["time"].diff().dt.total_seconds()
    d["same_as_prev"] = d.groupby("link")["travel_time_s"].diff().eq(0)
    per = d.groupby("link").agg(rows=("time", "size"), median_gap_s=("gap_s", "median"),
                                share_status0=("status", lambda x: float((x == 0).mean())),
                                share_repeat=("same_as_prev", "mean")).reset_index()
    per.to_csv(OUT / "link_quality.csv", index=False, float_format="%.4f")
    # Hourly profile of speed (status 0) to check that the clock is local New York time: the PM rush must slow.
    ok = d[d["status"] == 0]
    prof = ok.groupby(ok["time"].dt.hour)["speed_mph"].median().rename("median_speed_mph")
    prof.to_csv(OUT / "hourly_speed.csv")
    # Rows per day, at the source: a day with few rows is an outage of the feed, not a quiet road.
    days = {f.stem: len(json.loads(f.read_text(encoding="utf-8"))) for f in sorted((ART / "raw").glob("*.json"))}
    with open(OUT / "rows_per_day.csv", "w", encoding="utf-8") as f:
        f.write("day,rows\n" + "".join(f"{k},{v}\n" for k, v in days.items()))


def metrics():
    import pandas as pd
    d = pd.read_parquet(ART / "obs_all.parquet")
    for name, keep in [("status0", d["status"] == 0), ("all", pd.Series(True, index=d.index))]:
        d.loc[keep, ["link", "time", "travel_time_s"]].to_parquet(ART / f"obs_{name}.parquet", index=False)
        out = ART / f"metrics_{name}"
        subprocess.run([sys.executable, str(SKILL / "ttr_metrics.py"), str(ART / f"obs_{name}.parquet"), str(out),
                        "--compare", "AM", "PM", "--holidays", *HOLIDAYS], check=True)
        for f in ("metrics.csv", "compare.csv", "audit.json"):
            (OUT / f"{name}_{f}").write_bytes((out / f).read_bytes())


def corridor_of(name):
    """The road and its direction from a link name: 'BQE S LEONARD STREET - ATLANTIC AVENUE' -> 'BQE S',
    'CVE NB GCP - WILLETS PT BLVD' -> 'CVE N'. Names without a direction word keep their first word."""
    import re
    m = re.match(r"^(.+?)\s+(NB|SB|EB|WB|N|S|E|W)\b", str(name))
    if m and len(m.group(1).split()) <= 3:
        return f"{m.group(1)} {m.group(2)[0]}"
    return str(name).split()[0]


def corridors():
    """Links grouped into corridors by road and direction (corridor_of), with corridor TTI and LOTTR from the sum of
    the link travel times bin by bin (bins where every link of the corridor reported), and the bottleneck links.
    The links of a corridor are not checked to be consecutive: the sum is the time to drive the observed pieces."""
    import numpy as np
    import pandas as pd
    sys.path.insert(0, str(SKILL))
    from ttr_metrics import bin15, metrics as m_
    links = pd.read_parquet(ART / "links.parquet")
    links["corridor"] = links["link_name"].map(corridor_of)
    d = pd.read_parquet(ART / "obs_status0.parquet")
    b, _ = bin15(d)
    b = b.merge(links[["link_id", "corridor"]], left_on="link", right_on="link_id")
    # A route bin needs every link of the corridor in that bin; corridors with one link are kept as they are.
    n = links.groupby("corridor")["link_id"].nunique()
    r = b.groupby(["corridor", "bin"]).agg(travel_time_s=("travel_time_s", "sum"), links=("link", "nunique")).reset_index()
    r = r[r["links"] == r["corridor"].map(n)]
    rm = m_(r.rename(columns={"corridor": "link"})[["link", "bin", "travel_time_s"]],
            [pd.Timestamp(h).date() for h in HOLIDAYS])
    rm = rm.rename(columns={"link": "corridor"})
    rm["links"] = rm["corridor"].map(n)
    rm.to_csv(OUT / "corridor_metrics.csv", index=False, float_format="%.4f")
    w = rm.pivot(index="corridor", columns="period", values=["tti", "lottr", "days", "delay_s"])
    t = pd.DataFrame({"links": n.reindex(w.index), "days_am": w["days"]["AM"], "days_pm": w["days"]["PM"],
                      "tti_am": w["tti"]["AM"], "tti_pm": w["tti"]["PM"], "lottr_am": w["lottr"]["AM"],
                      "lottr_pm": w["lottr"]["PM"], "delay_s_am": w["delay_s"]["AM"], "delay_s_pm": w["delay_s"]["PM"]})
    t = t[(t["days_am"] >= 10) & (t["days_pm"] >= 10)].sort_values("tti_pm", ascending=False)
    t.to_csv(OUT / "corridor_am_pm.csv", float_format="%.3f")
    m = pd.read_csv(OUT / "status0_metrics.csv", dtype={"link": str}).merge(links[["link_id", "link_name", "borough"]],
                                                      left_on="link", right_on="link_id")
    pm = m[(m["period"] == "PM") & ~m["few_days"]].sort_values("tti", ascending=False)
    pm.head(15)[["link", "link_name", "borough", "days", "tti", "lottr", "pti", "delay_s"]].to_csv(
        OUT / "bottlenecks_pm_tti.csv", index=False, float_format="%.3f")
    worst = m[~m["few_days"]].groupby(["link", "link_name", "borough"])["lottr"].max().reset_index()
    worst.sort_values("lottr", ascending=False).head(15).to_csv(OUT / "unreliable_links.csv", index=False,
                                                                 float_format="%.3f")
    c = pd.read_csv(OUT / "status0_compare.csv", dtype={"link": str}).merge(links[["link_id", "link_name", "borough"]],
                                                      left_on="link", right_on="link_id")
    c["significant"] = (c["lo"] > 0) | (c["hi"] < 0)
    c.sort_values("diff_s", ascending=False).to_csv(OUT / "am_pm_links.csv", index=False, float_format="%.1f")
    summ = {"links_compared": len(c), "pm_slower_significant": int(((c["lo"] > 0)).sum()),
            "am_slower_significant": int(((c["hi"] < 0)).sum()),
            "reliable_links": int((worst["lottr"] < 1.5).sum()), "links_with_lottr": len(worst)}
    json.dump(summ, open(OUT / "corridor_summary.json", "w", encoding="utf-8"), indent=1)
    print(summ)


def maps():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import pandas as pd
    links = pd.read_parquet(ART / "links.parquet")
    m = pd.read_csv(OUT / "status0_metrics.csv", dtype={"link": str})
    fig, axes = plt.subplots(1, 2, figsize=(14, 8), dpi=120)
    cmap = plt.get_cmap("magma_r")
    for ax, per in zip(axes, ["AM", "PM"]):
        mm = m[m["period"] == per].set_index("link")["tti"]
        for _, r in links.iterrows():
            pts = []
            # The last pair can be a fragment cut by the feed's length limit ("40.70,-74"): drop it.
            for p in str(r["link_points"]).split()[:-1]:
                try:
                    la, lo = map(float, p.split(","))
                except ValueError:
                    continue
                # link_points is cut at a fixed length in the feed, so its last point can be a fragment
                # ("40.77273,-7"): keep points inside New York only.
                if 40.4 <= la <= 41.0 and -74.3 <= lo <= -73.6:
                    pts.append((lo, la))
            if len(pts) < 2:
                continue
            v = mm.get(str(r["link_id"]), float("nan"))
            col = "#cccccc" if pd.isna(v) else cmap(min(max((v - 1) / 2, 0), 1))
            ax.plot(*zip(*pts), color=col, lw=2)
        ax.set_aspect(1 / math.cos(math.radians(40.7)))
        ax.set_title(f"TTI, weekday {per} peak")
    fig.suptitle("NYC DOT Traffic Speeds, October 2026 (grey: no TTI)")
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(1, 3))
    fig.colorbar(sm, ax=axes, label="TTI (mean / free-flow travel time)", shrink=0.6)
    fig.savefig(OUT / "tti_am_pm.png", bbox_inches="tight")


STEPS = {"fetch": fetch, "prepare": prepare, "quality": quality, "metrics": metrics, "corridors": corridors,
         "maps": maps}

if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    ART.mkdir(parents=True, exist_ok=True)
    for s in (STEPS if sys.argv[1] == "all" else sys.argv[1:]):
        STEPS[s]()
