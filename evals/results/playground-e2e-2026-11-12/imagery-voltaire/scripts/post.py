"""poles.csv -> per-picture table, map PNG, summary. usage: post.py INSP_DIR MANIFEST OUT_DIR"""
import sys, csv, json
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
insp, man, out = sys.argv[1:4]
p = pd.read_csv(f"{insp}/poles.csv"); m = pd.read_csv(man)
TH = 0.15  # fixed before looking at the distribution
p["branch"] = p.veg_share >= TH
sites = p.groupby("site").agg(n=("picture","size"), pics=("picture","nunique"), lat=("lat","mean"), lon=("lon","mean"),
                              veg_max=("veg_share","max"), veg_med=("veg_share","median"), lean_med=("lean_deg", lambda s: s.abs().median())).reset_index()
sites["branch"] = sites.veg_max >= TH
sites.to_csv(f"{out}/sites.csv", index=False, encoding="utf-8")
pp = p.groupby("picture").agg(poles=("site","size"), branch=("branch","sum"), veg_max=("veg_share","max")).reset_index()
pp = m[["id","lon","lat","producer","camera","datetime"]].merge(pp, left_on="id", right_on="picture", how="left").drop(columns="picture")
pp[["poles","branch"]] = pp[["poles","branch"]].fillna(0).astype(int)
pp.to_csv(f"{out}/pictures.csv", index=False, encoding="utf-8")
p.to_csv(f"{out}/detections.csv", index=False, encoding="utf-8")
s = dict(pictures=len(m), pictures_with_detection=int((pp.poles>0).sum()), detections=len(p), detections_with_position=int(p.lat.notna().sum()),
         sites=len(sites), sites_branch=int(sites.branch.sum()), threshold=TH,
         veg_quantiles=p.veg_share.quantile([.1,.25,.5,.75,.9,.95]).round(3).to_dict())
json.dump(s, open(f"{out}/summary.json","w",encoding="utf-8"), indent=1)
print(json.dumps(s, indent=1))
fig, ax = plt.subplots(figsize=(8,6))
ax.scatter(m.lon, m.lat, s=40, c="lightgray", marker="s", label="panorama (30)")
q = sites.dropna(subset=["lat"])
ax.scatter(q.lon[~q.branch], q.lat[~q.branch], s=25, c="#1b7837", label="pole, no branch signal")
ax.scatter(q.lon[q.branch], q.lat[q.branch], s=60, c="#d6604d", edgecolor="k", label=f"pole, veg share >= {TH}")
ax.set_aspect(1/np.cos(np.radians(48.857))); ax.set_xlabel("lon (WGS84)"); ax.set_ylabel("lat"); ax.legend(fontsize=8)
ax.set_title("Boulevard Voltaire: pole sites (estimated positions)")
fig.savefig(f"{out}/map.png", dpi=130, bbox_inches="tight")
