"""報告の表と図。数字はここで数えて outputs/ に書く。使い方: python 07_tables_figures.py"""
import json, numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
R="/work/artifacts/nyc-arterial-reliability/"; O="/work/projects/nyc-arterial-reliability/outputs/"; F="/work/projects/nyc-arterial-reliability/figures/"
m=pd.read_csv(O+"metrics_main.csv"); c=pd.read_csv(O+"compare_main.csv"); L=pd.read_csv(O+"link_length_mi.csv",dtype={"link_id":str}).rename(columns={"link_id":"link"})
m["link"]=m.link.astype(str); c["link"]=c.link.astype(str)
m=m.merge(L,on="link",how="left")
# 路線の長さ = 構成区間の長さの和
import importlib.util
sp=importlib.util.spec_from_file_location("an","/work/projects/nyc-arterial-reliability/scripts/05_analysis.py"); an=importlib.util.module_from_spec(sp); sp.loader.exec_module(an)
for name,ids in an.ROUTES.items():
    m.loc[m.link=="R:"+name,"length_mi"]=sum(L.set_index("link").length_mi.get(i,np.nan) for i in ids)
m["ff_speed_mph"]=m.length_mi/(m.free_flow_s/3600); m["mean_speed_mph"]=m.length_mi/(m["mean"]/3600)
m["ff_doubtful"]=m.ff_speed_mph<30
am=m[m.period=="AM"].set_index("link"); pm=m[m.period=="PM"].set_index("link")
ok=lambda df:df[df.days>=10]
out={}
# ---- 路線 ----
rt=pd.DataFrame({"name":pm.name,"length_mi":pm.length_mi,"days_AM":am.days,"days_PM":pm.days,
 "ff_speed_mph":pm.ff_speed_mph,"AM_mean_min":am["mean"]/60,"PM_mean_min":pm["mean"]/60,"AM_delay_min":am.delay_s/60,"PM_delay_min":pm.delay_s/60,
 "AM_tti":am.tti,"PM_tti":pm.tti,"AM_lottr":am.lottr,"AM_lottr_lo":am.lottr_lo,"AM_lottr_hi":am.lottr_hi,"PM_lottr":pm.lottr,"PM_lottr_lo":pm.lottr_lo,"PM_lottr_hi":pm.lottr_hi,
 "AM_pti":am.pti,"PM_pti":pm.pti})[pm.kind=="route"]
rc=c[c.kind=="route"].set_index("link")[["days","diff_s","lo","hi","lo_wk","hi_wk","ratio","ratio_lo","ratio_hi","q_bh","pm_slower_days"]]
rt=rt.join(rc).sort_values("PM_delay_min",ascending=False); rt.to_csv(O+"table_routes.csv",float_format="%.3f")
# ---- 区間 ----
lk=pd.DataFrame({"name":pm.name,"borough":pm.borough,"length_mi":pm.length_mi,"days_AM":am.days,"days_PM":pm.days,"ff_speed_mph":pm.ff_speed_mph,"ff_doubtful":pm.ff_doubtful,
 "AM_mean_s":am["mean"],"PM_mean_s":pm["mean"],"AM_delay_s":am.delay_s,"PM_delay_s":pm.delay_s,"AM_tti":am.tti,"PM_tti":pm.tti,
 "AM_lottr":am.lottr,"AM_lottr_lo":am.lottr_lo,"AM_lottr_hi":am.lottr_hi,"PM_lottr":pm.lottr,"PM_lottr_lo":pm.lottr_lo,"PM_lottr_hi":pm.lottr_hi,
 "AM_pti":am.pti,"PM_pti":pm.pti,"AM_d2d_lottr":am.d2d_lottr_median,"PM_d2d_lottr":pm.d2d_lottr_median,"PM_mean_speed_mph":pm.mean_speed_mph})[pm.kind=="link"]
lk["max_lottr"]=lk[["AM_lottr","PM_lottr"]].max(axis=1); lk["max_lottr_lo"]=np.where(lk.AM_lottr>=lk.PM_lottr,lk.AM_lottr_lo,lk.PM_lottr_lo)
lk=lk.join(c[c.kind=="link"].set_index("link")[["days","diff_s","lo","hi","lo_wk","hi_wk","ratio","ratio_lo","ratio_hi","q_bh","pm_slower_days"]].rename(columns={"days":"days_both"}))
lk.to_csv(O+"table_links_all.csv",float_format="%.3f")
u=lk[(lk.days_AM>=10)&(lk.days_PM>=10)].copy(); thin=lk[~lk.index.isin(u.index)]
out["links_with_any_metric"]=int(len(lk)); out["links_days_ge10_both"]=int(len(u)); out["links_days_lt10"]=int(len(thin))
out["links_with_no_status0"]=int(125-len(lk))
u.sort_values("PM_delay_s",ascending=False).head(15).to_csv(O+"table_top_delay_PM.csv",float_format="%.3f")
u.sort_values("AM_delay_s",ascending=False).head(15).to_csv(O+"table_top_delay_AM.csv",float_format="%.3f")
un=u[u.max_lottr>=1.5].sort_values("max_lottr",ascending=False); un.to_csv(O+"table_unreliable_links.csv",float_format="%.3f")
out["n_unreliable_lottr_ge_1.5"]=int(len(un)); out["n_unreliable_ci_lower_ge_1.5"]=int((un.max_lottr_lo>=1.5).sum())
out["n_unreliable_AM"]=int((u.AM_lottr>=1.5).sum()); out["n_unreliable_PM"]=int((u.PM_lottr>=1.5).sum()); out["n_unreliable_both"]=int(((u.AM_lottr>=1.5)&(u.PM_lottr>=1.5)).sum())
u.sort_values("PM_pti",ascending=False).head(15).to_csv(O+"table_top_pti_PM.csv",float_format="%.3f")
u.sort_values("PM_d2d_lottr",ascending=False).head(10)[["name","PM_d2d_lottr","AM_d2d_lottr","PM_lottr"]].to_csv(O+"table_top_day_to_day_PM.csv",float_format="%.3f")
out["d2d_lottr_PM_median_over_links"]=float(u.PM_d2d_lottr.median()); out["lottr_pooled_PM_median_over_links"]=float(u.PM_lottr.median())
out["n_unreliable_d2d_ge_1.5_PM"]=int((u.PM_d2d_lottr>=1.5).sum()); out["n_unreliable_d2d_ge_1.5_AM"]=int((u.AM_d2d_lottr>=1.5).sum())
# 朝と夕の差
out["n_diff_pm_slower_ci"]=int((u.lo>0).sum()); out["n_diff_am_slower_ci"]=int((u.hi<0).sum()); out["n_diff_ci_includes0"]=int(((u.lo<=0)&(u.hi>=0)).sum())
out["n_diff_bh_sig"]=int((u.q_bh<0.05).sum())
out["n_diff_wk_ci_pm_slower"]=int((u.lo_wk>0).sum()); out["n_diff_wk_ci_am_slower"]=int((u.hi_wk<0).sum())
out["median_ci_width_day_s"]=float((u.hi-u.lo).median()); out["median_ci_width_week_s"]=float((u.hi_wk-u.lo_wk).median())
d=u.sort_values("diff_s"); d.head(8).to_csv(O+"table_diff_am_slower.csv",float_format="%.3f"); d.tail(12).iloc[::-1].to_csv(O+"table_diff_pm_slower.csv",float_format="%.3f")
rr=rt[(rt.days_AM>=10)&(rt.days_PM>=10)]; out["routes_total"]=int(len(rt)); out["routes_days_ge10"]=int(len(rr))
out["routes_pm_slower_ci"]=int((rr.lo>0).sum()); out["routes_am_slower_ci"]=int((rr.hi<0).sum()); out["routes_ci_incl0"]=int(((rr.lo<=0)&(rr.hi>=0)).sum())
# ---- 基準: 平均速度の順位 ----
from itertools import product
sp_=lambda a,b:float(pd.concat([a,b],axis=1).dropna().corr(method="spearman").iloc[0,1])
out["base_spearman_PMmeanspeed_vs_PMlottr"]=sp_(-u.PM_mean_speed_mph,u.PM_lottr)
out["base_spearman_PMmeanspeed_vs_PMpti"]=sp_(-u.PM_mean_speed_mph,u.PM_pti)
out["base_spearman_PMtti_vs_PMlottr"]=sp_(u.PM_tti,u.PM_lottr)
out["base_spearman_PMdelay_vs_PMlottr"]=sp_(u.PM_delay_s,u.PM_lottr)
slow20=set(u.PM_mean_speed_mph.nsmallest(20).index); un_top20=set(u.PM_lottr.nlargest(20).index)
out["base_top20_slowest_vs_top20_lottr_overlap"]=len(slow20&un_top20)
out["unreliable_but_not_in_20_slowest"]=int(len(set(un.index)-slow20))
# 夜の自由流が怪しい (自由流の速度 < 30 mph)
out["n_ff_doubtful_links"]=int(u.ff_doubtful.sum()); dd=u[u.ff_doubtful]
dd[["name","length_mi","ff_speed_mph","PM_mean_speed_mph","PM_tti","PM_delay_s","PM_lottr"]].to_csv(O+"table_ff_doubtful.csv",float_format="%.3f")
out["top10_PM_delay_in_ff_doubtful"]=int(u.nlargest(10,"PM_delay_s").ff_doubtful.sum())
out["n_ff_doubtful_routes"]=int((rr.ff_speed_mph<30).sum())
# 基準 2: 朝と夕が同じ (差 0)
out["baseline_zero_diff_pm_slower_days_share_median"]=float((u.pm_slower_days/u.days_both).median())
# 件数の確認
out["bins_rows_main"]=json.load(open(O+"bins_audit_main.json",encoding="utf-8"))
json.dump(out,open(O+"summary_numbers.json","w",encoding="utf-8"),indent=1,ensure_ascii=False); print(json.dumps(out,indent=1,ensure_ascii=False))

# ---- 図 ----
plt.rcParams.update({"font.size":9,"axes.spines.top":False,"axes.spines.right":False})
# 図 1: 路線の朝と夕の差
r=rr.sort_values("diff_s"); fig,ax=plt.subplots(figsize=(8,5.6))
y=np.arange(len(r)); lab=[n.split(" (")[0] for n in r.name]
ax.errorbar(r.diff_s/60,y,xerr=[(r.diff_s-r.lo)/60,(r.hi-r.diff_s)/60],fmt="o",color="#1f6fb4",capsize=3,label="95% CI, resampling days")
ax.errorbar(r.diff_s/60,y+0.22,xerr=[(r.diff_s-r.lo_wk)/60,(r.hi_wk-r.diff_s)/60],fmt="none",ecolor="#999999",capsize=2,label="95% CI, resampling weeks (5 blocks)")
ax.axvline(0,color="k",lw=.8); ax.set_yticks(y); ax.set_yticklabels(lab); ax.set_xlabel("PM minus AM, mean route travel time (minutes)\n<- AM slower | PM slower ->")
ax.set_title("Route travel time: PM rush minus AM rush, weekdays Sep 2026 (n=days, 12-21)"); ax.legend(frameon=False,loc="lower right")
fig.tight_layout(); fig.savefig(F+"fig1_route_pm_minus_am.png",dpi=150); plt.close(fig)
# 図 2: 遅さ (PM delay) と読めなさ (LOTTR)
fig,axs=plt.subplots(1,2,figsize=(10,4.2),sharey=False)
for ax,per in zip(axs,["AM","PM"]):
    x=u[f"{per}_delay_s"]/60; y=u[f"{per}_lottr"]
    ax.errorbar(x,y,yerr=[y-u[f"{per}_lottr_lo"],u[f"{per}_lottr_hi"]-y],fmt="o",ms=3.5,color="#1f6fb4",alpha=.6,elinewidth=.6)
    ax.axhline(1.5,color="#c0392b",lw=1,ls="--"); ax.set_xlabel(f"{per} mean delay per trip (min)"); ax.set_ylabel("LOTTR (p80/p50)"); ax.set_title(f"{per}, links with >=10 days (n={len(u)})")
fig.tight_layout(); fig.savefig(F+"fig2_delay_vs_lottr.png",dpi=150); plt.close(fig)
# 図 3: 地図 (経緯度のまま。表示だけで、距離や面積は測らない)
lp=pd.read_parquet(R+"raw/links_latest.parquet").set_index("link_id")
def pts(s):
    p=[tuple(map(float,q.split(","))) for q in s.split()[:-1] if q.count(",")==1]; xy=np.array([(b,a) for a,b in p])
    if len(xy)>2:  # 途中に飛ぶ点 (欠けた桁) があれば、最初の連続部分だけ使う
        j=np.where(np.abs(np.diff(xy,axis=0)).max(axis=1)>0.03)[0]
        if len(j): xy=xy[:j[0]+1]
    return xy
fig,axs=plt.subplots(1,2,figsize=(11,5.6))
for ax,(col,title,cmap,vmax) in zip(axs,[("PM_delay_s","PM mean delay per trip (s)","YlOrRd",None),("max_lottr","max LOTTR (AM or PM)","PuBu",None)]):
    for lid,row in lp.iterrows():
        xy=pts(row.link_points)
        if len(xy)>1: ax.plot(xy[:,0],xy[:,1],color="#d0d0d0",lw=.8,zorder=1)
    v=u[col]; norm=plt.Normalize(v.min(),v.quantile(.95)); cm=plt.get_cmap(cmap)
    for lid in u.index:
        if lid in lp.index:
            xy=pts(lp.loc[lid,"link_points"])
            if len(xy)>1: ax.plot(xy[:,0],xy[:,1],color=cm(norm(u.loc[lid,col])),lw=3,zorder=2)
    ax.set_aspect(1/np.cos(np.radians(40.7))); ax.set_title(title); ax.set_xlabel("lon"); ax.set_ylabel("lat")
    sm=plt.cm.ScalarMappable(norm=norm,cmap=cm); fig.colorbar(sm,ax=ax,shrink=.7,extend="max")
ax.figure.suptitle("Grey: links without usable data (display only, lon/lat shown unprojected; last vertex of each link is truncated in source)",fontsize=8)
fig.tight_layout(); fig.savefig(F+"fig3_map.png",dpi=150); plt.close(fig)
