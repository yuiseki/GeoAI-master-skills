"""観測を区間 × 15 分の区切りの表にする。祝日 (2026-09-07 Labor Day) は週末扱い。
使い方: python 04_prepare_bins.py"""
import importlib.util, pandas as pd, numpy as np
S="/work/.agents/skills/travel-time-reliability/scripts/ttr_metrics.py"
sp=importlib.util.spec_from_file_location("ttr",S); ttr=importlib.util.module_from_spec(sp); sp.loader.exec_module(ttr)
R="/work/artifacts/nyc-arterial-reliability/"; O="/work/projects/nyc-arterial-reliability/outputs/"
d=pd.read_parquet(R+"raw/raw_2026-09.parquet")
for c in ["speed","travel_time","status"]: d[c]=pd.to_numeric(d[c])
d["time"]=pd.to_datetime(d["data_as_of"]); d=d.rename(columns={"link_id":"link","travel_time":"travel_time_s"})
d=d.sort_values(["link","time"])
d["repeat"]=d.groupby(["link","status"]).travel_time_s.diff().eq(0)
variants={"main":d[d.status==0],
          "with_m101":d,   # 状態 -101 でも旅行時間が正の行を含む
          "no_repeat":d[(d.status==0)&~d.repeat]}
for k,v in variants.items():
    b,a=ttr.bin15(v[["link","time","travel_time_s"]]); print(k,a)
    b.to_parquet(R+f"bins_{k}.parquet"); pd.Series(a).to_json(O+f"bins_audit_{k}.json")
