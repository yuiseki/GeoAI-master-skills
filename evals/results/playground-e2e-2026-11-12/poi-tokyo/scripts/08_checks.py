"""Top-10 stability across point sets, permutation baseline for ward HHI, simple baseline numbers."""
import sys, json, numpy as np, pandas as pd, h3
sys.path.insert(0,"scripts")
A="/work/artifacts/tokyo23-convenience-stores/"; O="outputs/"
rng=np.random.default_rng(20261112)
res={}
def topcells(f,r=9,k=10):
    d=pd.read_parquet(A+f+".parquet"); c=pd.Series([h3.latlng_to_cell(y,x,r) for y,x in zip(d.lat,d.lon)]).value_counts()
    kth=c.iloc[k-1]; return set(c[c>=kth].index), c
base,cb=topcells("pts_primary"); res["top_primary_n"]=len(base)
for f in ["pts_noatm_nodedup","pts_all"]:
    s,_=topcells(f); res[f"overlap_{f}"]=len(base&s); res[f"n_{f}"]=len(s)
# top-10 under res 8 and res 10 containing the res 9 top cells' parents
for r in (8,10):
    s,c=topcells("pts_primary",r); res[f"top10_res{r}_cells"]=len(s)
    res[f"res9_top_parents_in_res{r}_top"]= len({h3.cell_to_parent(x,8) for x in base} & s) if r==8 else None
cells=pd.read_csv(O+"cells_res9.csv"); res["cells_area"]=len(cells); res["mean_per_cell"]=float(cells["count"].mean()); res["share_cells_empty"]=float((cells["count"]==0).mean())
res["max_cell"]=int(cells["count"].max()); res["share_stores_in_top11_cells"]=float(cb[list(base)].sum()/cb.sum())
# top-decile cells share
cs=cells["count"].sort_values(ascending=False); res["share_stores_in_top_1pct_cells"]=float(cs.head(int(len(cs)*0.01)).sum()/cs.sum())
# permutation baseline for ward HHI: shuffle chain labels across all stores
p=pd.read_parquet(A+"pts_primary.parquet"); ch=p.chain.values.astype(object); reg=p.region_id.values
def hhi(labels):
    n=len(labels); s=pd.Series(labels); un=s.isna().sum(); v=s.value_counts(); return ((v/n)**2).sum()+un/n**2
obs={r:hhi(ch[reg==r]) for r in np.unique(reg)}
perm={r:[] for r in obs}
for _ in range(1000):
    sh=rng.permutation(ch)
    for r in obs: perm[r].append(hhi(sh[reg==r]))
rows=[]
for r in obs:
    a=np.array(perm[r]); rows.append(dict(region_id=r,hhi=obs[r],null_mean=a.mean(),null_lo=np.percentile(a,2.5),null_hi=np.percentile(a,97.5),p_greater=float((a>=obs[r]).mean()),p_less=float((a<=obs[r]).mean())))
pd.DataFrame(rows).to_csv(O+"hhi_permutation.csv",index=False,encoding="utf-8")
df=pd.DataFrame(rows); res["hhi_perm_outside_95"]=int(((df.hhi<df.null_lo)|(df.hhi>df.null_hi)).sum()); res["hhi_citywide"]=float(hhi(ch))
# between-ward variance of observed HHI vs null
res["hhi_obs_sd"]=float(df.hhi.std()); res["hhi_null_sd_mean"]=float(np.mean([np.std(perm[r]) for r in perm]))
# chain shares citywide
res["chain_share_citywide"]=p.chain.fillna("(unmatched)").value_counts(normalize=True).round(4).to_dict()
json.dump(res,open(O+"checks.json","w"),indent=1,ensure_ascii=False); print(json.dumps(res,indent=1,ensure_ascii=False)); print(df.round(3).to_string())
