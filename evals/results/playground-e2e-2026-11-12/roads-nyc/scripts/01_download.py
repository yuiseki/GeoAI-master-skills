"""NYC DOT Traffic Speeds (Socrata i4gi-tjb9) の 2026-09 を日ごとに取得し、Parquet にする。
使い方: python 01_download.py OUTDIR"""
import sys, json, time, urllib.parse, urllib.request, datetime as dt
import pandas as pd
out = sys.argv[1]
BASE = "https://data.cityofnewyork.us/resource/i4gi-tjb9.json"
COLS = "id,speed,travel_time,status,data_as_of,link_id,link_name,borough,owner"
def get(params):
    url = BASE + "?" + urllib.parse.urlencode(params)
    for k in range(5):
        try:
            with urllib.request.urlopen(url, timeout=120) as r:
                return json.load(r)
        except Exception as e:
            print("retry", e, file=sys.stderr); time.sleep(3 * (k + 1))
    raise SystemExit("download failed " + url)
import os
os.makedirs(out + "/days", exist_ok=True)
d = dt.date(2026, 9, 1)
while d < dt.date(2026, 10, 1):
    n = d + dt.timedelta(days=1)
    f = f"{out}/days/{d}.parquet"
    if os.path.exists(f):
        d = n; continue
    rows, off = [], 0
    while True:
        r = get({"$select": COLS, "$where": f"data_as_of>='{d}T00:00:00' AND data_as_of<'{n}T00:00:00'",
                 "$order": "data_as_of,link_id", "$limit": 50000, "$offset": off})
        rows += r
        if len(r) < 50000: break
        off += 50000
    print(d, len(rows), flush=True)
    pd.DataFrame(rows).to_parquet(f); d = n
df = pd.concat([pd.read_parquet(f"{out}/days/{x}") for x in sorted(os.listdir(out + "/days"))], ignore_index=True)
df.to_parquet(out + "/raw_2026-09.parquet")
# 区間の形 (最新の 1 回分)
l = get({"$select": "link_id,link_name,borough,owner,link_points,encoded_poly_line", "$limit": 2000,
         "$where": "data_as_of>='2026-11-11T12:00:00'", "$order": "data_as_of DESC"})
pd.DataFrame(l).drop_duplicates("link_id").to_parquet(out + "/links_latest.parquet")
print(len(df), "rows;", len(l), "link rows")
