import pandas as pd, numpy as np
R="/work/artifacts/nyc-arterial-reliability/raw/"
d=pd.read_parquet(R+"raw_2026-09.parquet")
for c in ["speed","travel_time","status"]: d[c]=pd.to_numeric(d[c])
d["t"]=pd.to_datetime(d["data_as_of"])
print(d.dtypes); print(d.link_id.nunique(), d.id.nunique())
print(d.groupby("status").agg(n=("speed","size"),med_speed=("speed","median"),tt0=("travel_time",lambda x:(x<=0).sum())))
print(d.groupby(d.t.dt.date).size().to_string())
print(d.groupby(d.t.dt.hour).speed.median().round(1).to_string())
l=pd.read_parquet(R+"links_latest.parquet"); print(len(l)); 
print(d.drop_duplicates("link_id")[["link_id","link_name","borough","owner"]].head(40).to_string())
print(d.borough.value_counts()); print(d.owner.value_counts())
print(d.groupby("link_id").link_name.nunique().max())
