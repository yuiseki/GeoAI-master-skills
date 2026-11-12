"""Gi* on H3 cells with two study areas: (bbox) the skill's default, every cell centre in the bbox; (wards) only cells
whose centre is in the 23 wards, or that hold a store. Resolutions 8, 9, 10; points = pts_primary (+ sensitivity sets)."""
import sys, json, numpy as np, pandas as pd, h3, duckdb
sys.path.insert(0,"/work/.agents/skills/poi-insights/scripts")
from grid_hotspots import assign, gi_star, bh_reject, clusters
from scipy.stats import norm
from shapely import wkt
from shapely.ops import unary_union
A="/work/artifacts/tokyo23-convenience-stores/"; O="outputs/"
c=duckdb.connect(); c.sql("install spatial; load spatial")
geoms=[wkt.loads(r[0]) for r in c.execute(f"select st_astext(geometry) from read_parquet('{A}wards.parquet')").fetchall()]
U=unary_union(geoms); polys=list(U.geoms) if U.geom_type=="MultiPolygon" else [U]
BBOX=(139.55,35.50,139.93,35.84)
def area_cells(res,kind):
    if kind=="bbox":
        w,s,e,n=BBOX; return set(h3.h3shape_to_cells(h3.LatLngPoly([(s,w),(s,e),(n,e),(n,w)]),res))
    out=set()
    for p in polys:
        out|=set(h3.h3shape_to_cells(h3.LatLngPoly([(y,x) for x,y in p.exterior.coords],*[[(y,x) for x,y in r.coords] for r in p.interiors]),res))
    return out
def run(df,res,kind,alpha=0.05):
    cells=assign(df.lon.values,df.lat.values,"h3",res)
    counts=pd.Series(cells).value_counts().to_dict()
    area=sorted(area_cells(res,kind)|set(counts)); idx={x:i for i,x in enumerate(area)}
    x=np.array([counts.get(a,0) for a in area],float)
    nb=[[idx[v] for v in h3.grid_disk(a,1) if v in idx] for a in area]
    z=gi_star(x,nb); p=norm.sf(z); rej=bh_reject(p,alpha)
    hot={a for a,r,xi in zip(area,rej,x) if r and xi>0}
    return dict(counts=counts,area=area,z=dict(zip(area,z)),p=dict(zip(area,p)),hot=hot,clusters=clusters(hot,counts,"h3"),n=len(area),npts=len(cells))
if __name__=="__main__":
    summ=[]
    sets={"primary":"pts_primary","all":"pts_all","noatm_nodedup":"pts_noatm_nodedup"}
    for sname,f in sets.items():
        df=pd.read_parquet(A+f+".parquet")
        for kind in ["wards","bbox"]:
            for res in [8,9,10]:
                if sname!="primary" and not(kind=="wards" and res==9): continue
                r=run(df,res,kind); cl=r["clusters"]
                top=cl[0] if cl else None
                summ.append(dict(set=sname,area=kind,res=res,points=r["npts"],cells=r["n"],nonempty=len(r["counts"]),hot_cells=len(r["hot"]),
                   clusters=len(cl),top_cluster_points=top["points"] if top else 0,top_cluster_cells=top["cells"] if top else 0,
                   max_cell=max(r["counts"].values()),
                   top10_cells_overlap_primary=None))
                if sname=="primary" and kind=="wards":
                    rows=[dict(cell=a,count=r["counts"].get(a,0),z=r["z"][a],p=r["p"][a],hot=int(a in r["hot"])) for a in r["area"]]
                    pd.DataFrame(rows).to_csv(f"{O}cells_res{res}.csv",index=False,encoding="utf-8")
                    pd.DataFrame([{k:v for k,v in cc.items() if k!="members"}|{"rank":i+1} for i,cc in enumerate(cl)]).to_csv(f"{O}clusters_res{res}.csv",index=False,encoding="utf-8")
                    json.dump({str(i+1):cc["members"] for i,cc in enumerate(cl[:15])},open(f"{O}cluster_members_res{res}.json","w"))
    pd.DataFrame(summ).to_csv(O+"resolution_sweep.csv",index=False,encoding="utf-8")
    print(pd.DataFrame(summ).to_string())
