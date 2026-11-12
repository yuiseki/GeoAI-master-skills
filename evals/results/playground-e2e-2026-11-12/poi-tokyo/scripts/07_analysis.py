"""Top-10 cells, clusters, ward table, robustness, OSM cross-check, uncertainty. Writes outputs/*.csv."""
import sys, json, numpy as np, pandas as pd, h3, duckdb
sys.path.insert(0,"scripts")
from scipy.stats import spearmanr
A="/work/artifacts/tokyo23-convenience-stores/"; O="outputs/"
rng=np.random.default_rng(20261112)
c=duckdb.connect(); c.sql("install spatial; load spatial; install httpfs; load httpfs")
roma=dict(c.execute("select code5,name_roma from read_parquet('hf://datasets/yuiseki/jp-admin-2026-09@e6c87b1d7095c17422147962185071a986e13135/municipalities.parquet') where code5 between '13101' and '13123'").fetchall())
pts=pd.read_parquet(A+"pts_primary.parquet")
pts["c9"]=[h3.latlng_to_cell(y,x,9) for x,y in zip(pts.lon,pts.lat)]
cells=pd.read_csv(O+"cells_res9.csv")
st=pd.read_parquet(A+"osm_stations.parquet")
lat0=np.radians(35.68)
def xy(lon,lat): return np.radians(lon)*6371008.8*np.cos(lat0), np.radians(lat)*6371008.8
sx,sy=xy(st.lon.values,st.lat.values)
# ---- top 10 cells (res 9)
top=cells.sort_values(["count","z"],ascending=[False,False]).head(12)  # look at ties
kth=top["count"].iloc[9]; print("10th count",kth,"cells with count>=kth:",(cells["count"]>=kth).sum())
top=cells[cells["count"]>=kth].sort_values(["count","z"],ascending=[False,False])
rows=[]
for i,r in enumerate(top.itertuples(),1):
    lat,lon=h3.cell_to_latlng(r.cell); x,y=xy(lon,lat); d=np.hypot(sx-x,sy-y); j=d.argmin()
    sub=pts[pts.c9==r.cell]
    wd=sub.region_name.value_counts()
    ch=sub.chain.fillna("(other/unmatched)").value_counts()
    rows.append(dict(rank=i,cell=r.cell,stores=r.count,gi_z=round(r.z,2),gi_hot_BH=bool(r.hot),lat=round(lat,5),lon=round(lon,5),
      ward=wd.index[0],nearest_station=st.name[j],station_m=int(d[j]),chains="; ".join(f"{k} {v}" for k,v in ch.items())))
t10=pd.DataFrame(rows); t10.to_csv(O+"top10_cells_res9.csv",index=False,encoding="utf-8"); print(t10.to_string())
# ---- top 10 clusters res 9 and res 8
for res in (8,9):
    cl=pd.read_csv(O+f"clusters_res{res}.csv").head(10); mem=json.load(open(O+f"cluster_members_res{res}.json"))
    out=[]
    for r in cl.itertuples():
        x,y=xy(r.lon,r.lat); d=np.hypot(sx-x,sy-y); j=d.argmin()
        cs=[h3.latlng_to_cell(a,b,res) for a,b in zip(pts.lat,pts.lon)] if False else None
        out.append(dict(rank=r.rank,cells=r.cells,stores=r.points,lat=round(r.lat,5),lon=round(r.lon,5),nearest_station=st.name[j],station_m=int(d[j]),
                        area_km2=round(r.cells*h3.average_hexagon_area(res,unit="km^2"),2)))
    pd.DataFrame(out).to_csv(O+f"top10_clusters_res{res}.csv",index=False,encoding="utf-8")
    print(res); print(pd.DataFrame(out).to_string())
# ---- ward table
cmp_={s:pd.read_csv(O+f"compare_{s}.csv",dtype={"region_id":str}) for s in ["primary","rawbrand","all"]}
w=duckdb.connect().execute(f"select region_id, population, households from read_parquet('{A}wards.parquet')").df()
w["region_id"]=w.region_id.astype(str)
P=cmp_["primary"].drop(columns=["population","poi_per_10k","pop_share_within_m"]).merge(w,on="region_id")
P["name_roma"]=P.region_id.map(roma)
P["per_10k"]=P.poi/P.population*1e4
P["per_household_100"]=P.poi/P.households*100
for s,tag in [("rawbrand","raw"),("all","all")]:
    q=cmp_[s].set_index("region_id")
    P["hhi_"+tag]=P.region_id.map(q.hhi); P["poi_"+tag]=P.region_id.map(q.poi)
    P["per_10k_"+tag]=P["poi_"+tag]/P.population*1e4
# chain-only HHI (unmatched stores dropped) and CR3, from primary points
g=pts.groupby("region_id")
def chain_stats(df):
    n=len(df); cc=df.chain.value_counts()
    big3=cc.head(3).sum()/n
    s_ch=cc/ cc.sum()
    return pd.Series(dict(unmatched_share=df.chain.isna().mean(),hhi_chain_only=(s_ch**2).sum(),cr3=big3,
        share_7=cc.get("7-Eleven",0)/n,share_fm=cc.get("FamilyMart",0)/n,share_lw=cc.get("Lawson",0)/n,n_chains=len(cc)))
CS=g.apply(chain_stats,include_groups=False).reset_index(); P=P.merge(CS,on="region_id")
# bootstrap CI of hhi (primary definition: unmatched = own firm) and of per_10k not applicable (census denominator)
def hhi_of(ch):
    n=len(ch); s=pd.Series(ch).fillna("").value_counts(); un=(pd.Series(ch).isna()).sum()
    named=s.drop("",errors="ignore"); return ((named/n)**2).sum()+un*(1/n)**2
lo=[];hi=[]
for rid,sub in g:
    ch=sub.chain.values; b=[hhi_of(ch[rng.integers(0,len(ch),len(ch))]) for _ in range(1000)]
    lo.append((rid,np.percentile(b,2.5),np.percentile(b,97.5)))
ci=pd.DataFrame(lo,columns=["region_id","hhi_lo","hhi_hi"]); P=P.merge(ci,on="region_id")
# OSM cross-check
osm=pd.read_parquet(A+"osm_cvs.parquet"); oc=osm.groupby("region_id").size().rename("osm_poi").reset_index()
P=P.merge(oc,on="region_id"); P["osm_per_10k"]=P.osm_poi/P.population*1e4
P["name"]=P.region_name
cols=["region_id","region_name","name_roma","population","poi","per_km2","per_10k","per_10k_all","per_10k_raw","osm_poi","osm_per_10k","hhi","hhi_lo","hhi_hi","hhi_raw","hhi_all","hhi_chain_only","cr3","top_brand","top_brand_share","share_7","share_fm","share_lw","unmatched_share","n_chains","area_km2","median_m_to_other_brand"]
P=P[cols].sort_values("per_10k",ascending=False); P.to_csv(O+"ward_table.csv",index=False,encoding="utf-8")
print(P[["region_name","population","poi","per_km2","per_10k","osm_per_10k","hhi","hhi_lo","hhi_hi","hhi_raw","hhi_chain_only","cr3","unmatched_share"]].round(3).to_string())
rk=lambda a,b: round(spearmanr(P[a],P[b]).statistic,3)
rob=dict(per10k_primary_vs_all=rk("per_10k","per_10k_all"),per10k_primary_vs_rawbrandset=rk("per_10k","per_10k_raw"),per10k_overture_vs_osm=rk("per_10k","osm_per_10k"),
 count_overture_vs_osm=round(spearmanr(P.poi,P.osm_poi).statistic,3),hhi_primary_vs_raw=rk("hhi","hhi_raw"),hhi_primary_vs_all=rk("hhi","hhi_all"),hhi_primary_vs_chainonly=rk("hhi","hhi_chain_only"),hhi_vs_cr3=rk("hhi","cr3"),
 per10k_vs_population_spearman=rk("per_10k","population"),hhi_vs_per10k=rk("hhi","per_10k"),per_km2_vs_per_10k=rk("per_km2","per_10k"),
 total_overture=int(P.poi.sum()),total_osm=int(P.osm_poi.sum()),total_pop=int(P.population.sum()),city_per_10k=float(P.poi.sum()/P.population.sum()*1e4),
 hhi_raw_median=float(P.hhi_raw.median()),hhi_median=float(P.hhi.median()),hhi_chainonly_median=float(P.hhi_chain_only.median()))
# cell-level OSM cross check
osm["c8"]=[h3.latlng_to_cell(y,x,8) for y,x in zip(osm.lat,osm.lon)]; pts["c8"]=[h3.latlng_to_cell(y,x,8) for y,x in zip(pts.lat,pts.lon)]
for res,col in [(8,"c8"),(9,"c9")]:
    osm["cc"]=[h3.latlng_to_cell(y,x,res) for y,x in zip(osm.lat,osm.lon)]
    a=pts[col].value_counts(); b=osm.cc.value_counts(); u=a.index.union(b.index)
    A_=a.reindex(u,fill_value=0); B_=b.reindex(u,fill_value=0)
    rob[f"cell_res{res}_spearman_union_nonempty"]=round(spearmanr(A_,B_).statistic,3); rob[f"cell_res{res}_only_overture"]=int(((A_>0)&(B_==0)).sum()); rob[f"cell_res{res}_only_osm"]=int(((A_==0)&(B_>0)).sum()); rob[f"cell_res{res}_union"]=int(len(u))
    t=set(A_.sort_values(ascending=False).head(10).index); rob[f"top10_res{res}_in_osm_top20"]=len(t & set(B_.sort_values(ascending=False).head(20).index))
# OSM top-10 cells at res9 vs ours
oc9=osm.assign(cc=[h3.latlng_to_cell(y,x,9) for y,x in zip(osm.lat,osm.lon)]).cc.value_counts()
rob["top10_cells_osm_counts"]=[int(oc9.get(r,0)) for r in t10.cell]
json.dump(rob,open(O+"robustness.json","w"),indent=1,ensure_ascii=False); print(json.dumps(rob,indent=1,ensure_ascii=False))
