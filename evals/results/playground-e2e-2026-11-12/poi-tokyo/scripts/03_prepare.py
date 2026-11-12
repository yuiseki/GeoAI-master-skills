"""Join the points to wards, normalise chains from brand then name, flag ATM rows and near duplicates."""
import re, json, duckdb, numpy as np
A="/work/artifacts/tokyo23-convenience-stores/"
c=duckdb.connect(); c.sql("install spatial; load spatial")
c.sql(f"""create table p as select * from read_parquet('{A}cvs_all.parquet')""")
c.sql(f"""create table w as select region_id, region_name, geometry g from read_parquet('{A}wards.parquet')""")
c.sql("""create table pj as select p.*, w.region_id, w.region_name from p left join w on st_contains(w.g, st_point(lon,lat))""")
n_all=c.sql("select count(*) from p").fetchall()[0][0]; n_j=c.sql("select count(*) from pj").fetchall()[0][0]
assert n_all==n_j, (n_all,n_j)
RULES=[("7-Eleven",r"セブン[-ー‐‑ ]?イレブン|7[-‐ ]?eleven|セブンイレブン|seven[- ]?eleven|セブン銀行"),
 ("FamilyMart",r"ファミリーマート|ファミマ|family ?mart|ファミリマ|ファミマ"),
 ("Lawson",r"ローソン|lawson|ナチュラルローソン"),
 ("Ministop",r"ミニストップ|ministop"),
 ("NewDays",r"newdays|ニューデイズ|new days"),
 ("Daily Yamazaki",r"デイリーヤマザキ|daily ?yamazaki|ヤマザキデイリー"),
 ("Maibasket",r"まいばすけっと"),
 ("Three F",r"スリーエフ|3f"),
 ("Seikatsu Saika",r"生活彩家"),
 ("Poplar",r"ポプラ|poplar"),
 ("Circle K Sunkus",r"サークルk|サンクス|circle ?k"),
 ("Seicomart",r"セイコーマート"),
 ("Yamazaki other",r"ヤマザキ"),]
def chain(brand,name):
    for src in (brand,name):
        if not isinstance(src,str) or not src: continue
        s=src.lower()
        for k,pat in RULES:
            if re.search(pat,s,re.I): return k,("brand" if src is brand and isinstance(brand,str) else "name")
    return None,None
rows=c.sql("select id,brand,name from pj").fetchall()
out={r[0]:chain(r[1],r[2]) for r in rows}
import pandas as pd
df=c.sql("select * from pj").df()
df["chain"]=[out[i][0] for i in df.id]; df["chain_src"]=[out[i][1] for i in df.id]
df["atm_like"]=df.name.fillna("").str.contains("ATM|共同出張所|銀行")
# chain_brand: brand column only (raw), chain_name: after normalising
df["brand_norm_only"]=[chain(b,None)[0] for b in df.brand]
# near duplicates: same chain within 25 m
lat0=np.radians(35.68); x=np.radians(df.lon.values)*6371008.8*np.cos(lat0); y=np.radians(df.lat.values)*6371008.8
from scipy.spatial import cKDTree
t=cKDTree(np.c_[x,y]); pairs=t.query_pairs(25)
dup=np.zeros(len(df),bool)
ch=df.chain.fillna("?").values
for i,j in pairs:
    if ch[i]==ch[j]!="?" : dup[max(i,j)]=True
df["near_dup25"]=dup
inw=df[df.region_id.notna()].copy()
inw.to_parquet(A+"cvs_wards.parquet")
audit={"in_bbox":int(n_all),"in_wards":int(len(inw)),"outside_wards":int(n_all-len(inw)),
 "brand_missing":int(inw.brand.isna().sum()),"chain_from_brand":int((inw.chain_src=="brand").sum()),
 "chain_from_name":int((inw.chain_src=="name").sum()),"chain_unmatched":int(inw.chain.isna().sum()),
 "atm_like":int(inw.atm_like.sum()),"near_dup25_same_chain":int(inw.near_dup25.sum()),
 "status_unknown":int((inw.operating_status=="unknown").sum())}
json.dump(audit,open("outputs/prepare_audit.json","w",encoding="utf-8"),ensure_ascii=False,indent=1); print(audit)
print(inw.chain.value_counts(dropna=False).to_string())
print(inw[inw.chain.isna()].name.value_counts().head(40).to_string())
print(inw[inw.atm_like].name.head(10).to_string())
