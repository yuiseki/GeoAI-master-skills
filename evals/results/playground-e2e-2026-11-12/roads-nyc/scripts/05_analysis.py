"""区間と路線の遅れ (TTI、遅延)、読めなさ (LOTTR、PTI)、朝と夕の差と不確かさ、頑健性。
使い方: python 05_analysis.py  (入力は 04 の bins_*.parquet)"""
import importlib.util, json, numpy as np, pandas as pd
S="/work/.agents/skills/travel-time-reliability/scripts/ttr_metrics.py"
sp=importlib.util.spec_from_file_location("ttr",S); ttr=importlib.util.module_from_spec(sp); sp.loader.exec_module(ttr)
R="/work/artifacts/nyc-arterial-reliability/"; O="/work/projects/nyc-arterial-reliability/outputs/"
HOL=[pd.Timestamp("2026-09-07").date()]
rng=np.random.default_rng(20261112)
raw=pd.read_parquet(R+"raw/raw_2026-09.parquet")[["link_id","link_name","borough","owner"]].drop_duplicates("link_id")
raw=raw.rename(columns={"link_id":"link"}).set_index("link")

# ---- 路線 (連続する区間の鎖。全区間に観測がある区切りだけ使う) ----
ROUTES={
 "GOW N (92nd St-Atlantic Av)":["4616220","4616318","4616223"],
 "GOW S (Atlantic Av-92nd St)":["4616229","4616319","4616226"],
 "FDR N (Catherine Slip-63rd St)":["4616328","4616329"],
 "FDR S (63rd St-Brooklyn Br)":["4616332","4616333","4616341"],
 "VWE S (Northern Blvd-Belt Pkwy)":["4616241","4616259","4616272","4616276"],
 "VWE N (Jewel Av-Linden Pl)":["4616299","4616300"],
 "SIE E (South Av-Wooley Av)":["4616197","4616195"],
 "SIE W (Bradley Av-South Av)":["4616208","4616209","4616211"],
 "WSE N (Bloomingdale Rd-South Av)":["4616214","4616213","4616212"],
 "WSE S (South Av-Bloomingdale Rd)":["4616200","4616201","4616202"],
 "CIP N (Laurelton Pkwy-LIE)":["4616353","4616351"],
 "CIP S (LIE-Laurelton Pkwy)":["4616350","4616352"],
 "Belt/Laurelton W (SSP-VWE)":["4616354","4616356","4616357"],
 "CBE E (Taylor Av-Waterbury Av)":["4616253","4616297"],
 "BE N (Stratford Av-Griswold Av)":["4616246","4616247"],
 "BE S (Griswold Av-Stratford Av)":["4616261","4616260"],
 "HRP S-BWB S (Lafayette Av-Queens)":["4456498","4456496"],
}
def add_routes(b):
    w=b.pivot(index="bin",columns="link",values="travel_time_s")
    parts=[]
    for name,ids in ROUTES.items():
        if not all(i in w.columns for i in ids): continue
        s=w[ids].dropna().sum(axis=1)
        # dropna で全区間そろった区切りだけ残る
        x=w[ids].dropna().sum(axis=1).rename("travel_time_s").reset_index(); x["link"]="R:"+name; parts.append(x)
    return pd.concat(parts)[["link","bin","travel_time_s"]]

def prep(b,min_bins=0,drop_days=(),periods=None):
    b=b.copy()
    b["day"]=pd.DatetimeIndex(b["bin"]).date
    if drop_days: b=b[~b.day.isin(drop_days)]
    if periods:  # 時間帯の既定を差し替える (感度確認用)
        pass
    return b.drop(columns="day")

def with_periods(b):
    b=b.copy(); b["period"]=ttr.period_of(b["bin"],HOL).values; b["day"]=pd.DatetimeIndex(b["bin"]).date; return b

def boot_ci(b,reps=1000):
    """区間 × 時間帯ごとに日を復元抽出して LOTTR、TTI、PTI の 95% 区間を作る"""
    ff=ttr.free_flow(b); bb=with_periods(b); rows=[]
    for (link,per),g in bb[bb.period.isin(["AM","PM"])].groupby(["link","period"]):
        arrs=[x.to_numpy() for _,x in g.groupby("day").travel_time_s]; n=len(arrs)
        f=ff.get(link,np.nan); L=[];T=[];P=[]
        for _ in range(reps):
            tt=np.concatenate([arrs[i] for i in rng.integers(0,n,n)])
            p50,p80,p95=np.percentile(tt,[50,80,95]); L.append(p80/p50); T.append(tt.mean()/f); P.append(p95/f)
        q=lambda v:np.percentile(v,[2.5,97.5])
        rows.append(dict(link=link,period=per,lottr_lo=q(L)[0],lottr_hi=q(L)[1],tti_lo=q(T)[0],tti_hi=q(T)[1],pti_lo=q(P)[0],pti_hi=q(P)[1]))
    return pd.DataFrame(rows)

def day_to_day(b):
    """同じ時刻の区切りで日ごとに比べた読めなさ: 時刻ごとの p80/p50 (日をまたぐ) の中央値と最大"""
    bb=with_periods(b); bb=bb[bb.period.isin(["AM","PM"])].copy(); bb["clock"]=pd.DatetimeIndex(bb.bin).time
    g=bb.groupby(["link","period","clock"]).travel_time_s
    x=pd.DataFrame({"n":g.size(),"p50":g.quantile(.5),"p80":g.quantile(.8)}).reset_index(); x=x[x.n>=10]
    x["r"]=x.p80/x.p50
    return x.groupby(["link","period"]).r.agg(d2d_lottr_median="median",d2d_lottr_max="max").reset_index()

def signflip_p(d,reps=20000):
    s=rng.choice([-1,1],size=(reps,len(d)))
    obs=abs(d.mean()); return float(((np.abs((s*d).mean(axis=1))>=obs-1e-12).mean()))
def bh(p):
    p=np.asarray(p); o=np.argsort(p); m=len(p); q=np.empty(m); c=1
    for r,i in zip(range(m,0,-1),o[::-1]): c=min(c,p[i]*m/r); q[i]=c
    return q

def compare_full(b,reps=1000):
    """朝と夕の差 (PM-AM)。日の引き直し (主)、週ブロックの引き直し、符号反転検定 (BH 補正)、比"""
    bb=with_periods(b); bb=bb[bb.period.isin(["AM","PM"])]
    day=bb.groupby(["link","day","period"]).travel_time_s.mean().unstack("period").dropna()
    rows=[]
    for link,g in day.groupby(level="link"):
        g=g.droplevel(0); d=(g.PM-g.AM).to_numpy(); n=len(d)
        bt=[d[rng.integers(0,n,n)].mean() for _ in range(reps)]
        # 暦の週 (月曜始まり) のブロック
        wk=pd.Series(pd.to_datetime(g.index)).dt.to_period("W").astype(str).to_numpy(); ws=np.unique(wk)
        bw=[]
        for _ in range(reps):
            pick=rng.choice(ws,len(ws)); bw.append(np.concatenate([d[wk==w] for w in pick]).mean())
        ar=g.AM.to_numpy(); pr=g.PM.to_numpy()
        br=[]
        for _ in range(reps):
            i=rng.integers(0,n,n); br.append(pr[i].mean()/ar[i].mean())
        rows.append(dict(link=link,days=n,mean_AM=ar.mean(),mean_PM=pr.mean(),diff_s=d.mean(),
            lo=np.percentile(bt,2.5),hi=np.percentile(bt,97.5),lo_wk=np.percentile(bw,2.5),hi_wk=np.percentile(bw,97.5),
            ratio=pr.mean()/ar.mean(),ratio_lo=np.percentile(br,2.5),ratio_hi=np.percentile(br,97.5),
            p_signflip=signflip_p(d),pm_slower_days=int((d>0).sum())))
    c=pd.DataFrame(rows); c["q_bh"]=bh(c.p_signflip.values); return c

def full(b,name,reps=1000):
    b=pd.concat([b,add_routes(b)],ignore_index=True)
    m=ttr.metrics(b,HOL); m["few_days"]=m.days<10
    ci=boot_ci(b,reps); m=m.merge(ci,on=["link","period"],how="left").merge(day_to_day(b),on=["link","period"],how="left")
    c=compare_full(b,reps)
    return b,m,c

if __name__=="__main__":
    import sys
    b0=pd.read_parquet(R+"bins_main.parquet")
    b,m,c=full(b0,"main")
    names=raw.link_name.to_dict(); 
    for t in (m,c):
        t["name"]=t.link.map(lambda x:x[2:] if x.startswith("R:") else names.get(x)); t["kind"]=np.where(t.link.str.startswith("R:"),"route","link")
        t["borough"]=t.link.map(lambda x:raw.borough.get(x,""))
    m.to_csv(O+"metrics_main.csv",index=False,float_format="%.4f"); c.to_csv(O+"compare_main.csv",index=False,float_format="%.4f")
    # 日 × 時間帯あたりの区切りの数
    bb=with_periods(b0); bb=bb[bb.period.isin(["AM","PM"])]
    k=bb.groupby(["link","day","period"]).size().describe(); print(k)
    # 区間の長さ (マイル): 速度 × 旅行時間
    print(m.groupby("kind").size(), c.groupby("kind").size())
    b.to_parquet(R+"bins_main_with_routes.parquet")
