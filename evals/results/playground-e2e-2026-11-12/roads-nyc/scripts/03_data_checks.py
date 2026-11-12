"""データの確かめ (data-checks.md の各項目)。使い方: python 03_data_checks.py"""
import pandas as pd, numpy as np, json
R="/work/artifacts/nyc-arterial-reliability/raw/"; O="/work/projects/nyc-arterial-reliability/outputs/"
d=pd.read_parquet(R+"raw_2026-09.parquet")
for c in ["speed","travel_time","status"]: d[c]=pd.to_numeric(d[c])
d["time"]=pd.to_datetime(d["data_as_of"]); d=d.sort_values(["link_id","time"])
out={}
out["rows"]=len(d); out["links"]=int(d.link_id.nunique())
out["dup_rows_link_time"]=int(d.duplicated(["link_id","time"]).sum())
s=d.groupby("status").agg(rows=("speed","size"),median_speed=("speed","median"),tt_le0=("travel_time",lambda x:int((x<=0).sum())))
s.to_csv(O+"check_status.csv"); print(s)
ok=d[d.status==0]
out["links_with_status0"]=int(ok.link_id.nunique())
dt_=d.groupby("link_id").time.diff().dt.total_seconds()
out["report_interval_median_s"]=float(dt_.median())
rep=ok.groupby("link_id").travel_time.apply(lambda x:(x.diff()==0).mean())
out["repeat_share_median"]=float(rep.median()); out["repeat_share_max"]=float(rep.max())
rep.sort_values().tail(8).to_csv(O+"check_repeat_top.csv")
h=ok.groupby(ok.time.dt.hour).speed.median().round(2); h.to_csv(O+"check_hourly_speed_status0.csv")
wk=ok[(ok.time.dt.dayofweek<5)]; hw=wk.groupby(wk.time.dt.hour).speed.median().round(2)
print("weekday hourly median speed (status 0)\n",hw.to_string())
out["weekday_slowest_hour"]=int(hw.idxmin()); out["weekday_fastest_hour"]=int(hw.idxmax())
# 状態 0 の割合を時間帯ごとに (観測なしが混雑時に偏るか)
d["wk"]=d.time.dt.dayofweek<5; w=d[d.wk]
share=w.groupby(w.time.dt.hour).status.apply(lambda x:(x==0).mean()).round(3); share.to_csv(O+"check_status0_share_by_hour.csv")
print("status0 share weekday by hour\n",share.to_string())
# 日ごとの行数・状態 0 の行数
day=d.groupby(d.time.dt.date).agg(rows=("status","size"),status0=("status",lambda x:int((x==0).sum()))); day.to_csv(O+"check_rows_by_day.csv")
# 区間 × 時間帯の状態 0 の割合 (平日 AM / PM)
w=w.assign(p=np.where(w.time.dt.hour.between(6,9),"AM",np.where(w.time.dt.hour.between(16,19),"PM","other")))
cov=w[w.p!="other"].groupby(["link_id","p"]).status.apply(lambda x:(x==0).mean()).unstack(); cov.to_csv(O+"check_status0_coverage_link.csv")
out["links_status0_share_ge_0.5_both"]=int(((cov.AM>=.5)&(cov.PM>=.5)).sum())
out["links_status0_share_lt_0.5_either"]=int(((cov.AM<.5)|(cov.PM<.5)).sum())
# 同じ値の繰り返し (status 0 の連続行) の上位
json.dump(out,open(O+"data_checks.json","w",encoding="utf-8"),indent=1); print(json.dumps(out,indent=1))
