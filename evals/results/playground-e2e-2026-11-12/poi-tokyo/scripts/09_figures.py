import json, numpy as np, pandas as pd, h3, duckdb, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MP
from matplotlib.collections import PatchCollection
from shapely import wkt
A="/work/artifacts/tokyo23-convenience-stores/"; O="outputs/"
c=duckdb.connect(); c.sql("install spatial; load spatial")
W=[wkt.loads(r[0]) for r in c.execute(f"select st_astext(geometry) from read_parquet('{A}wards.parquet')").fetchall()]
k=1/np.cos(np.radians(35.68))
def draw_wards(ax):
    for g in W:
        for p in (g.geoms if g.geom_type=="MultiPolygon" else [g]):
            ax.plot(*p.exterior.xy,color="#555",lw=.6)
def hexpoly(cell):
    return [(lon,lat) for lat,lon in h3.cell_to_boundary(cell)]
cells=pd.read_csv(O+"cells_res9.csv"); top=pd.read_csv(O+"top10_cells_res9.csv")
ne=cells[cells["count"]>0]
fig,axs=plt.subplots(1,2,figsize=(15,7.2),gridspec_kw=dict(width_ratios=[1.35,1]))
ax=axs[0]; draw_wards(ax)
pc=PatchCollection([MP(hexpoly(x)) for x in ne.cell],cmap="YlOrRd",linewidths=0)
pc.set_array(ne["count"].values); pc.set_clim(1,12); ax.add_collection(pc)
hot=ne[ne.hot==1]
ax.add_collection(PatchCollection([MP(hexpoly(x)) for x in hot.cell],facecolor="none",edgecolor="#1f4e9c",linewidths=.5))
for r in top.itertuples():
    ax.add_patch(MP(hexpoly(r.cell),facecolor="none",edgecolor="k",lw=1.6))
    ax.annotate(str(r.rank),(r.lon,r.lat),xytext=(r.lon+.006,r.lat+.004),fontsize=10,fontweight="bold",
       bbox=dict(boxstyle="circle,pad=.15",fc="white",ec="k",lw=.8))
ax.set_aspect(k); ax.set_xlim(139.56,139.93); ax.set_ylim(35.52,35.82)
cb=plt.colorbar(pc,ax=ax,shrink=.7,pad=.01); cb.set_label("stores per H3 res-9 cell (colour clipped at 12)")
ax.set_title("Convenience stores per H3 res-9 cell, 23 wards\nblue outline = Gi* hot (BH q<0.05); black = top 10 (11 with a tie) by count",fontsize=10)
ax.set_xlabel("longitude (EPSG:4326, plotted with 1/cos(lat) aspect)"); ax.set_ylabel("latitude")
# zoom on centre
ax=axs[1]; draw_wards(ax)
pc2=PatchCollection([MP(hexpoly(x)) for x in ne.cell],cmap="YlOrRd",linewidths=.2,edgecolor="#bbb"); pc2.set_array(ne["count"].values); pc2.set_clim(1,12); ax.add_collection(pc2)
for r in top.itertuples():
    ax.add_patch(MP(hexpoly(r.cell),facecolor="none",edgecolor="k",lw=1.6))
    ax.annotate(str(r.rank),(r.lon,r.lat),xytext=(r.lon+.002,r.lat+.0015),fontsize=10,fontweight="bold",bbox=dict(boxstyle="circle,pad=.15",fc="white",ec="k",lw=.8))
ax.set_aspect(k); ax.set_xlim(139.68,139.80); ax.set_ylim(35.64,35.74); ax.set_title("Zoom: central wards (same colour scale)",fontsize=10)
ax.set_xlabel("longitude")
plt.tight_layout(); plt.savefig("figures/map_top10_res9.png",dpi=140); plt.close()
# res comparison: hot clusters at 8,9,10
fig,axs=plt.subplots(1,3,figsize=(16,5.5))
for ax,res in zip(axs,(8,9,10)):
    d=pd.read_csv(O+f"cells_res{res}.csv"); draw_wards(ax); h=d[d.hot==1]; n=d[d["count"]>0]
    ax.add_collection(PatchCollection([MP(hexpoly(x)) for x in n.cell],facecolor="#ddd",linewidths=0))
    ax.add_collection(PatchCollection([MP(hexpoly(x)) for x in h.cell],facecolor="#d95f02",alpha=.8,linewidths=0))
    ax.set_aspect(k); ax.set_xlim(139.56,139.93); ax.set_ylim(35.52,35.82)
    ax.set_title(f"res {res}: {len(h)} hot cells of {len(n)} non-empty (grey)",fontsize=10)
plt.tight_layout(); plt.savefig("figures/hot_cells_by_resolution.png",dpi=120); plt.close()
# ward bars
P=pd.read_csv(O+"ward_table.csv"); P=P.sort_values("per_10k")
fig,axs=plt.subplots(1,2,figsize=(13,7))
axs[0].barh(P.name_roma,P.per_10k,color="#4c78a8"); axs[0].axvline(6.88,color="k",ls="--",lw=1); axs[0].set_xlabel("stores per 10,000 residents (2020 census); dashed = 23-ward 6.88")
axs[0].set_title("Stores per 10,000 residents (Overture 2026-10-21.0)")
Q=pd.read_csv(O+"ward_table.csv").sort_values("hhi")
perm=pd.read_csv(O+"hhi_permutation.csv",dtype={"region_id":str}).set_index("region_id")
Q["rid"]=Q.region_id.astype(str); y=np.arange(len(Q))
axs[1].errorbar(Q.hhi,y,xerr=[Q.hhi-Q.hhi_lo,Q.hhi_hi-Q.hhi],fmt="o",color="#e45756",capsize=2,label="HHI, bootstrap 95%")
axs[1].scatter(Q.rid.map(perm.null_mean),y,marker="|",s=120,color="k",label="mean if chains were shuffled across wards")
axs[1].hlines(y,Q.rid.map(perm.null_lo),Q.rid.map(perm.null_hi),color="#bbb",lw=4,zorder=0,label="shuffle 95% range")
axs[1].set_yticks(y); axs[1].set_yticklabels(Q.name_roma); axs[1].set_xlabel("HHI of store counts (unmatched = own firm)"); axs[1].legend(fontsize=8,loc="lower right")
axs[1].set_title("Chain concentration (HHI)")
plt.tight_layout(); plt.savefig("figures/ward_comparison.png",dpi=130); plt.close()
