"""Build point sets: primary (no ATM annex rows, same-chain records within 25 m merged, brand = normalised chain),
rawbrand (same rows, brand = Overture brand as is), all (every row in wards, normalised chain)."""
import pandas as pd, numpy as np, json
from scipy.spatial import cKDTree
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
A="/work/artifacts/tokyo23-convenience-stores/"
d=pd.read_parquet(A+"cvs_wards.parquet")
n0=len(d); e=d[~d.atm_like].reset_index(drop=True); n1=len(e)
lat0=np.radians(35.68); x=np.radians(e.lon.values)*6371008.8*np.cos(lat0); y=np.radians(e.lat.values)*6371008.8
ch=e.chain.fillna("?").values
pr=[(i,j) for i,j in cKDTree(np.c_[x,y]).query_pairs(25) if ch[i]==ch[j]!="?"]
m=coo_matrix((np.ones(len(pr)),([a for a,b in pr],[b for a,b in pr])),shape=(n1,n1))
nc,lab=connected_components(m,directed=False)
e["comp"]=lab
# keep the record with the longest name (store-specific name), highest confidence next
e["nl"]=e.name.fillna("").str.len()
keep=e.sort_values(["comp","nl","confidence"],ascending=[True,False,False]).drop_duplicates("comp")
sizes=pd.Series(lab).value_counts()
print("components with >2 records:",int((sizes>2).sum()),"max size",int(sizes.max()))
def out(df,name,brand):
    o=df[["id","name","lon","lat","operating_status","confidence","region_id","region_name","chain"]].copy()
    o["brand"]=brand; o.to_parquet(A+name+".parquet")
out(keep,"pts_primary",keep.chain)
out(keep,"pts_rawbrand",keep.brand)
out(e,"pts_noatm_nodedup",e.chain)
out(d,"pts_all",d.chain)
aud={"in_wards":n0,"after_atm_removed":n1,"after_dedup25_same_chain":len(keep),"removed_atm":n0-n1,"removed_dups":n1-len(keep)}
json.dump(aud,open("outputs/point_sets.json","w"),indent=1); print(aud)
