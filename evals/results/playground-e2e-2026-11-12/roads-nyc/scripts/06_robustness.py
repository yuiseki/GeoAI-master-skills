"""頑健性 (設定を変えた場合)、前半と後半の順位の再現、基準 (平均速度の順位)、自由流の信頼性。
使い方: python 06_robustness.py"""
import importlib.util, json, numpy as np, pandas as pd
P="/work/projects/nyc-arterial-reliability/scripts/05_analysis.py"
sp=importlib.util.spec_from_file_location("an",P); an=importlib.util.module_from_spec(sp); sp.loader.exec_module(an)
ttr=an.ttr; R=an.R; O=an.O
raw=pd.read_parquet(R+"raw/raw_2026-09.parquet"); 
for c in ["speed","travel_time","status"]: raw[c]=pd.to_numeric(raw[c])
g=raw[raw.status==0]; length=(g.speed*g.travel_time/3600).groupby(g.link_id).median().rename("length_mi")
length.to_csv(O+"link_length_mi.csv")
def spear(a,b): 
    j=pd.concat([a,b],axis=1,join="inner").dropna(); return float(j.corr(method="spearman").iloc[0,1]) if len(j)>2 else np.nan
def topk(a,b,k=10):
    a=a.dropna().nlargest(k).index; b=b.dropna().nlargest(k).index; return len(set(a)&set(b))

def scen(b,name,reps=300,days=None,min_bins=0,periods=None,ff=None):
    orig=(dict(ttr.PERIODS),ttr.free_flow)
    try:
        if periods: ttr.PERIODS.clear(); ttr.PERIODS.update(periods)
        if ff: ttr.free_flow=ff
        b=b.copy(); b["day"]=pd.DatetimeIndex(b.bin).date
        if days is not None: b=b[~b.day.isin(days)]
        if min_bins:
            bb=an.with_periods(b); n=bb.groupby(["link","day","period"]).travel_time_s.transform("size")
            b=b[(n>=min_bins)|bb.period.isna()]
        b=b.drop(columns="day")
        b=pd.concat([b,an.add_routes(b)],ignore_index=True)
        m=ttr.metrics(b,an.HOL); m["few_days"]=m.days<10
        c=an.compare_full(b,reps)
    finally:
        ttr.PERIODS.clear(); ttr.PERIODS.update(orig[0]); ttr.free_flow=orig[1]
    m["scenario"]=name; c["scenario"]=name; return m,c

def allday_ff(b):
    return b.groupby("link")["travel_time_s"].quantile(0.15).to_dict()

import datetime as dt
D=lambda *a:dt.date(*a)
b_main=pd.read_parquet(R+"bins_main.parquet")
runs={"S0_main":dict(b=b_main),
 "S1_include_status_-101_positive_tt":dict(b=pd.read_parquet(R+"bins_with_m101.parquet")),
 "S2_drop_repeated_values":dict(b=pd.read_parquet(R+"bins_no_repeat.parquet")),
 "S3_drop_2026-09-21_(Yom_Kippur)":dict(b=b_main,days=[D(2026,9,21)]),
 "S4_drop_2026-09-01..04":dict(b=b_main,days=[D(2026,9,i) for i in range(1,5)]),
 "S5_free_flow_all_hours_p15":dict(b=b_main,ff=allday_ff),
 "S6_windows_AM7-10_PM16-19":dict(b=b_main,periods={"AM":(7,10),"MIDD":(10,16),"PM":(16,19)}),
 "S7_min_8_bins_per_day_period":dict(b=b_main,min_bins=8)}
res={}
for k,v in runs.items():
    b=v.pop("b"); res[k]=scen(b,k,**v); print(k,flush=True)
M=pd.concat([r[0] for r in res.values()]); C=pd.concat([r[1] for r in res.values()])
M.to_csv(O+"robust_metrics_all.csv",index=False,float_format="%.4f"); C.to_csv(O+"robust_compare_all.csv",index=False,float_format="%.4f")

def vec(m,per,col,minday=10):
    x=m[(m.period==per)&(m.days>=minday)].set_index("link")[col]; return x
rows=[]
m0,c0=res["S0_main"]
for k,(m,c) in res.items():
    r={"scenario":k}
    for per,col in [("PM","delay_s"),("PM","tti"),("PM","pti"),("AM","tti")]:
        a,b=vec(m0,per,col),vec(m,per,col); r[f"spearman_{per}_{col}"]=spear(a,b); r[f"top10_overlap_{per}_{col}"]=topk(a,b)
    lt=m[m.period.isin(["AM","PM"])&(m.days>=10)&~m.link.str.startswith("R:")].groupby("link").lottr.max()
    lt0=m0[m0.period.isin(["AM","PM"])&(m0.days>=10)&~m0.link.str.startswith("R:")].groupby("link").lottr.max()
    r["spearman_max_lottr"]=spear(lt0,lt); r["n_links_lottr_ge_1.5"]=int((lt>=1.5).sum()); r["n_links"]=len(lt)
    r["same_set_unreliable_as_S0"]=int(((lt>=1.5)&(lt0.reindex(lt.index)>=1.5)).sum())
    cc=c[(c.days>=10)].set_index("link"); c00=c0[c0.days>=10].set_index("link")
    j=cc.join(c00[["diff_s","q_bh"]],rsuffix="0",how="inner")
    r["spearman_diff_s"]=float(j[["diff_s","diff_s0"]].corr(method="spearman").iloc[0,1])
    r["n_diff_excl0_bh"]=int((cc.q_bh<0.05).sum()); r["n_pairs"]=len(cc)
    r["sign_agree_diff_with_S0"]=float((np.sign(j.diff_s)==np.sign(j.diff_s0)).mean())
    rows.append(r)
pd.DataFrame(rows).to_csv(O+"robustness_summary.csv",index=False,float_format="%.3f"); print(pd.DataFrame(rows).T.to_string())

# ---- 前半と後半 (日付の前半と後半、奇数日と偶数日) の順位の再現 ----
bm=b_main.copy(); bm["day"]=pd.DatetimeIndex(bm.bin).date; days=sorted(bm.day.unique())
splits={"first_vs_second_half":(lambda d:d<=D(2026,9,16)),"odd_vs_even_day":(lambda d:d.day%2==1)}
sr=[]
for nm,f in splits.items():
    ma,ca=scen(bm[bm.day.map(f)].drop(columns="day"),"A",reps=200); mb,cb=scen(bm[~bm.day.map(f)].drop(columns="day"),"B",reps=200)
    for per,col in [("PM","delay_s"),("PM","tti"),("PM","pti"),("AM","delay_s"),("AM","tti"),("PM","lottr"),("AM","lottr")]:
        a,b=vec(ma,per,col,5),vec(mb,per,col,5)
        sr.append(dict(split=nm,period=per,metric=col,n=len(pd.concat([a,b],axis=1).dropna()),spearman=spear(a,b),top10_overlap=topk(a,b)))
    a,b=ca[ca.days>=5].set_index("link"),cb[cb.days>=5].set_index("link"); j=a.join(b,lsuffix="_A",rsuffix="_B",how="inner")
    sr.append(dict(split=nm,period="PM-AM",metric="diff_s",n=len(j),spearman=float(j[["diff_s_A","diff_s_B"]].corr(method="spearman").iloc[0,1]),
                   top10_overlap=float((np.sign(j.diff_s_A)==np.sign(j.diff_s_B)).mean())))  # 最後は符号の一致率
pd.DataFrame(sr).to_csv(O+"split_half_stability.csv",index=False,float_format="%.3f"); print(pd.DataFrame(sr).to_string())
