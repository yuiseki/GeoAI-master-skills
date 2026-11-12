"""report.md を、outputs/ の表と数字から組み立てる (表の数字は CSV から写す)。使い方: python 08_build_report.py"""
import json, pandas as pd
O="/work/projects/nyc-arterial-reliability/outputs/"
S=json.load(open(O+"summary_numbers.json",encoding="utf-8")); DC=json.load(open(O+"data_checks.json",encoding="utf-8"))
rt=pd.read_csv(O+"table_routes.csv"); tp=pd.read_csv(O+"table_top_delay_PM.csv"); ta=pd.read_csv(O+"table_top_delay_AM.csv")
un=pd.read_csv(O+"table_unreliable_links.csv"); dp=pd.read_csv(O+"table_diff_pm_slower.csv"); da=pd.read_csv(O+"table_diff_am_slower.csv")
rb=pd.read_csv(O+"robustness_summary.csv"); sh=pd.read_csv(O+"split_half_stability.csv"); ff=pd.read_csv(O+"table_ff_doubtful.csv"); d2=pd.read_csv(O+"table_top_day_to_day_PM.csv")
pti=pd.read_csv(O+"table_top_pti_PM.csv")
def f(x,n=2): return f"{x:,.{n}f}"
def short(n): return n.title() if n.isupper() else n
# --- 表 ---
T_route="| 路線 (方向と区間) | 長さ mi | PM の遅延 分 | AM の遅延 分 | PM TTI | AM TTI | PM の LOTTR | AM の LOTTR | PM − AM 秒 [95% 区間] | BH 補正 q |\n|---|---|---|---|---|---|---|---|---|---|\n"
for _,r in rt.iterrows():
    T_route+=f"| {r['name']} | {f(r.length_mi)} | {f(r.PM_delay_min)} | {f(r.AM_delay_min)} | {f(r.PM_tti)} | {f(r.AM_tti)} | {f(r.PM_lottr)} | {f(r.AM_lottr)} | {f(r.diff_s,1)} [{f(r.lo,1)}, {f(r.hi,1)}] | {f(r.q_bh,3)} |\n"
T_pm="| 区間 | 長さ mi | PM の平均 秒 | PM の遅延 秒 | PM TTI | PM の LOTTR | 自由流の速度 mph |\n|---|---|---|---|---|---|---|\n"
for _,r in tp.head(10).iterrows(): T_pm+=f"| {r['name']} | {f(r.length_mi)} | {f(r.PM_mean_s,1)} | {f(r.PM_delay_s,1)} | {f(r.PM_tti)} | {f(r.PM_lottr)} | {f(r.ff_speed_mph,1)} |\n"
T_am="| 区間 | AM の日数 | AM の平均 秒 | AM の遅延 秒 | AM TTI | AM の LOTTR | 自由流の速度 mph |\n|---|---|---|---|---|---|---|\n"
for _,r in ta.head(6).iterrows(): T_am+=f"| {r['name']} | {int(r.days_AM)} | {f(r.AM_mean_s,1)} | {f(r.AM_delay_s,1)} | {f(r.AM_tti)} | {f(r.AM_lottr)} | {f(r.ff_speed_mph,1)} |\n"
T_un="| 区間 | 日数 AM/PM | AM の LOTTR [95% 区間] | PM の LOTTR [95% 区間] | PM の PTI | 同じ時刻の日ごと LOTTR AM/PM |\n|---|---|---|---|---|---|\n"
for _,r in un.head(12).iterrows(): T_un+=f"| {r['name']} | {int(r.days_AM)}/{int(r.days_PM)} | {f(r.AM_lottr)} [{f(r.AM_lottr_lo)}, {f(r.AM_lottr_hi)}] | {f(r.PM_lottr)} [{f(r.PM_lottr_lo)}, {f(r.PM_lottr_hi)}] | {f(r.PM_pti,1)} | {f(r.AM_d2d_lottr)}/{f(r.PM_d2d_lottr)} |\n"
T_dp="| 区間 | 日数 | AM の平均 秒 | PM の平均 秒 | PM − AM 秒 [95% 区間] | BH 補正 q |\n|---|---|---|---|---|---|\n"
for _,r in dp.head(6).iterrows(): T_dp+=f"| {r['name']} | {int(r.days_both)} | {f(r.AM_mean_s,1)} | {f(r.PM_mean_s,1)} | {f(r.diff_s,1)} [{f(r.lo,1)}, {f(r.hi,1)}] | {f(r.q_bh,3)} |\n"
T_da="| 区間 | 日数 | AM の平均 秒 | PM の平均 秒 | PM − AM 秒 [95% 区間] | BH 補正 q |\n|---|---|---|---|---|---|\n"
for _,r in da.head(5).iterrows(): T_da+=f"| {r['name']} | {int(r.days_both)} | {f(r.AM_mean_s,1)} | {f(r.PM_mean_s,1)} | {f(r.diff_s,1)} [{f(r.lo,1)}, {f(r.hi,1)}] | {f(r.q_bh,3)} |\n"
T_rb="| 設定 | PM の遅延 上位 10 の一致 | PM の遅延 順位の Spearman | LOTTR ≥ 1.5 の区間数 | S0 と同じ集合の数 | 朝夕の差の符号の一致率 | BH 有意な区間と路線の数 |\n|---|---|---|---|---|---|---|\n"
for _,r in rb.iterrows(): T_rb+=f"| {r.scenario} | {int(r['top10_overlap_PM_delay_s'])} | {f(r['spearman_PM_delay_s'],3)} | {int(r['n_links_lottr_ge_1.5'])} (母数 {int(r.n_links)}) | {int(r.same_set_unreliable_as_S0)} | {f(r.sign_agree_diff_with_S0,3)} | {int(r.n_diff_excl0_bh)} (母数 {int(r.n_pairs)}) |\n"
T_sh="| 分け方 | 時間帯 | 指標 | n | Spearman | 上位 10 の一致 (差は符号の一致率) |\n|---|---|---|---|---|---|\n"
for _,r in sh.iterrows(): T_sh+=f"| {r.split} | {r.period} | {r.metric} | {int(r.n)} | {f(r.spearman,3)} | {f(r.top10_overlap,3)} |\n"
T_ff="| 区間 | 長さ mi | 自由流の速度 mph | PM の平均速度 mph | PM TTI | PM の遅延 秒 |\n|---|---|---|---|---|---|\n"
for _,r in ff.iterrows(): T_ff+=f"| {r['name']} | {f(r.length_mi)} | {f(r.ff_speed_mph,1)} | {f(r.PM_mean_speed_mph,1)} | {f(r.PM_tti)} | {f(r.PM_delay_s,1)} |\n"
top=rt.iloc[0]; g=lambda k:S[k]
vals=dict(T_route=T_route,T_pm=T_pm,T_am=T_am,T_un=T_un,T_dp=T_dp,T_da=T_da,T_rb=T_rb,T_sh=T_sh,T_ff=T_ff,S=S,DC=DC,top=top)
tpl=open("/work/projects/nyc-arterial-reliability/scripts/report_template.md",encoding="utf-8").read()
import re
def sub(m):
    return str(eval(m.group(1),{"f":f},vals))
out=re.sub(r"\{\{(.+?)\}\}",sub,tpl)
open("/work/projects/nyc-arterial-reliability/report.md","w",encoding="utf-8").write(out); print(len(out))
