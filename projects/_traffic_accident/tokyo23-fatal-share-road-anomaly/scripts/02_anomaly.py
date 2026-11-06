"""B2-B6: stratified fatal-share anomalies of the 500 m meshes, and their turnover against the total-count ranking.

systemd-run --user --scope -q -p MemoryMax=8G -p MemorySwapMax=0 -p CPUQuota=400% -- \
  uvx --from 'duckdb>=1.5.5' --with numpy --with scipy --with pandas --with pyarrow python -u scripts/02_anomaly.py

Reads artifacts/.../accidents.parquet (01_extract.py). Follows EXPERIMENT_PLAN.md: severe = 死者数 >= 1; strata =
道路形状 group x 車道幅員 x 中央分離帯 group, merged upward below ceil(1 / overall fatal share) accidents; expected
deaths of a mesh from the leave-mesh-out stratum shares; P = Poisson-binomial upper tail; BH q.
Writes outputs/meshes_main.csv, strata_main.csv, top20_main.csv, permutation.csv, variants.csv, summary.json.
"""
import json
import math
import time
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

import fatalshare as fs

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "outputs"
ART = HERE.parents[3] / "artifacts/_traffic_accident/tokyo23-fatal-share-road-anomaly"
ADMIN = "hf://datasets/yuiseki/jp-admin-2026-09@e6c87b1d7095c17422147962185071a986e13135/municipalities.parquet"
SEED = 49
N_PERM = 999
TOPS = (10, 20, 50)

SHAPE = {"01": "交差点", "31": "交差点", "07": "交差点付近", "37": "交差点付近", "11": "トンネル", "12": "橋",
         "13": "カーブ・屈折", "14": "単路その他", "21": "踏切", "22": "踏切", "23": "踏切", "00": "一般交通の場所"}
WIDTH_2022 = {"12": "14", "13": "17", "16": "18"}
MEDIAN = {"1": "中央分離帯", "4": "ペイント", "5": "分離なし", "2": "その他の中央線", "3": "その他の中央線",
          "6": "その他の中央線", "7": "その他の中央線", "0": "一般交通の場所"}
VULNERABLE = {"51", "52", "61"}


def load():
    d = pd.read_parquet(ART / "accidents.parquet")
    d["fatal"] = (d.died > 0).astype(int)
    d["shape_g"] = d["shape"].map(SHAPE)
    d["width_g"] = d.width.replace(WIDTH_2022)
    d["median_g"] = d["median"].map(MEDIAN)
    r = pd.to_numeric(d.route.str[:4], errors="coerce")
    d["motorway"] = np.where((r >= 4000) & (r <= 5999), "専用道", "一般道")
    d["vulnerable"] = np.where(d.party_a.isin(VULNERABLE) | d.party_b.isin(VULNERABLE), "歩行者か自転車", "その他")
    for lv, col in ((3, "m1000"), (4, "m500"), (5, "m250")):
        d[col] = fs.mesh_code(d.latitude.values, d.longitude.values, lv)
    assert d[["shape_g", "median_g"]].notna().all().all(), "unmapped road code"
    return d


def strata(d, extra=()):
    keys = list(zip(d.shape_g, d.width_g, d.median_g, *[d[c] for c in extra]))
    min_n = math.ceil(len(d) / d.fatal.sum())
    return np.array(fs.merge_strata(keys, min_n)), min_n


def score(d, unit_col, extra=(), p_fn=None):
    """p_fn(stratum, unit, fatal) -> death probability per row; the plain leave-unit-out share by default."""
    lab, min_n = strata(d, extra)
    unit = d[unit_col].values
    p = (p_fn or (lambda s, u, f: fs.leave_unit_out_p(s, u, f, {})))(lab, unit, d.fatal.values)
    g = pd.DataFrame({"unit": unit, "fatal": d.fatal.values, "p": p, "city": d.city.values})
    rows = []
    n_units = g.unit.nunique()
    for u, t in g.groupby("unit", sort=True):
        o, pp = int(t.fatal.sum()), t.p.values
        # k_needed: fatal accidents the mesh would need for P <= 0.05 / M, the P that the first-ranked mesh
        # needs for BH q < 0.05
        rows.append(dict(unit=u, n=len(t), O=o, E=float(pp.sum()), P=fs.poibin_sf(pp, o),
                         k_needed=fs.poibin_k_needed(pp, 0.05 / n_units), zero_p_rows=int((pp == 0).sum()),
                         city=t.city.mode().iloc[0]))
    m = pd.DataFrame(rows)
    m["q"] = fs.bh(m.P.values)
    m["O_minus_E"] = m.O - m.E
    m = m.sort_values(["P", "O_minus_E", "unit"], ascending=[True, False, True]).reset_index(drop=True)
    m["anomaly_rank"] = np.arange(1, len(m) + 1)
    cr = m.sort_values(["n", "unit"], ascending=[False, True]).unit.tolist()
    m["count_rank"] = m.unit.map({u: i + 1 for i, u in enumerate(cr)})
    return m, lab, min_n


def overlap(a, b, k):
    return len(set(a[:k]) & set(b[:k]))


def turnover(m):
    an = m.unit.tolist()
    ct = m.sort_values("count_rank").unit.tolist()
    res = {}
    for k in TOPS:
        o = overlap(an, ct, k)
        res[f"top{k}"] = dict(common=o, jaccard=round(o / (2 * k - o), 4), random_expectation=round(k * k / len(m), 3))
    rho = spearmanr(m.n, m.P).statistic  # ranks of -log10 P are those of P reversed
    res["spearman_n_vs_minus_log10_P"] = round(float(-rho), 4)
    return res


def main():
    t0 = time.time()
    OUT.mkdir(exist_ok=True)
    d = load()
    names = duckdb.sql(f"select code5, name from '{ADMIN}' where code5 like '131%'").df()
    ward = dict(zip(names.code5.str[2:], names.name))
    summary = dict(accidents=int(len(d)), fatal=int(d.fatal.sum()))

    # B2 + B4: main
    m, lab, min_n = score(d, "m500")
    m["ward"] = m.city.map(ward)
    m["O_over_E"] = m.O / m.E
    m.to_csv(OUT / "meshes_main.csv", index=False, encoding="utf-8")
    st = pd.DataFrame({"stratum": lab, "fatal": d.fatal}).groupby("stratum").agg(n=("fatal", "size"), fatal=("fatal", "sum"))
    st["share"] = st.fatal / st.n
    st.sort_values("n", ascending=False).to_csv(OUT / "strata_main.csv", encoding="utf-8")
    assert m.n.sum() == len(d) and m.O.sum() == d.fatal.sum()
    b2 = dict(meshes=int(len(m)), min_n_stratum=min_n, strata=int(st.shape[0]),
              q_lt_005=int((m.q < 0.05).sum()), q_lt_010=int((m.q < 0.10).sum()),
              P_needed_first=0.05 / len(m), k_needed_median=float(m.k_needed.median()),
              meshes_k_needed_le_n=int((m.k_needed <= m.n).sum()),
              meshes_one_short=int((m.O >= m.k_needed - 1).sum()), meshes_P_zero=int((m.P == 0).sum()),
              meshes_with_fatal=int((m.O > 0).sum()), min_P=float(m.P.min()), min_q=float(m.q.min()),
              E_total=round(float(m.E.sum()), 2))
    summary["B2"] = b2
    summary["B4"] = turnover(m)
    print(json.dumps(b2, ensure_ascii=False), json.dumps(summary["B4"], ensure_ascii=False), flush=True)

    # details of the top 20
    top = m.head(20).copy()
    rows = []
    for r in top.itertuples():
        t = d[d.m500 == r.unit]
        f = t[t.fatal == 1]
        rows.append(dict(unit=r.unit, distinct_points=int(t[["latitude", "longitude"]].drop_duplicates().shape[0]),
                         fatal_distinct_points=int(f[["latitude", "longitude"]].drop_duplicates().shape[0]),
                         motorway_share=round(float((t.motorway == "専用道").mean()), 3),
                         fatal_motorway=int((f.motorway == "専用道").sum()),
                         fatal_vulnerable=int((f.vulnerable == "歩行者か自転車").sum()),
                         fatal_years=" ".join(map(str, sorted(f.occ_year))),
                         fatal_shapes=" ".join(sorted(f.shape_g)),
                         top_stratum=pd.Series(lab[(d.m500 == r.unit).values]).value_counts().index[0],
                         lat=float(t.latitude.mean()), lon=float(t.longitude.mean())))
    top = top.merge(pd.DataFrame(rows), on="unit")
    top.to_csv(OUT / "top20_main.csv", index=False, encoding="utf-8")
    print(top[["anomaly_rank", "unit", "ward", "n", "O", "E", "P", "q", "count_rank", "fatal_motorway",
               "fatal_vulnerable", "fatal_distinct_points"]].to_string(), flush=True)

    # B3: overdispersion against a within-stratum permutation (full-data shares, no leave-out)
    share = pd.Series(d.fatal.values).groupby(lab).transform("mean").values
    t_obs = fs.overdispersion(d.m500.values, d.fatal.values, share)
    rng = np.random.default_rng(SEED)
    t_null = np.array([fs.overdispersion(d.m500.values, fs.permute_within(lab, d.fatal.values, rng), share)
                       for _ in range(N_PERM)])
    pd.DataFrame({"T": t_null}).to_csv(OUT / "permutation.csv", index=False, encoding="utf-8")
    summary["B3"] = dict(T_obs=round(t_obs, 2), null_mean=round(float(t_null.mean()), 2),
                         null_p95=round(float(np.quantile(t_null, 0.95)), 2), n_perm=N_PERM, seed=SEED,
                         p_perm=round(float(((t_null >= t_obs).sum() + 1) / (N_PERM + 1)), 4))
    print("B3", summary["B3"], flush=True)

    # B5: persistence, early 2019-2022 -> late 2023-2025
    early, late = d[d.occ_year <= 2022].reset_index(drop=True), d[d.occ_year >= 2023].reset_index(drop=True)
    me, _, _ = score(early, "m500")
    lab_l, _ = strata(late)
    p_l = fs.leave_unit_out_p(lab_l, late.m500.values, late.fatal.values, {})
    b5 = dict(early_accidents=int(len(early)), early_fatal=int(early.fatal.sum()),
              late_accidents=int(len(late)), late_fatal=int(late.fatal.sum()), early_q_lt_005=int((me.q < 0.05).sum()))
    for k in (20, 50):
        for name, sel in (("anomaly", me.unit.head(k)), ("count", me.sort_values("count_rank").unit.head(k))):
            mask = late.m500.isin(set(sel)).values
            o, pp = int(late.fatal.values[mask].sum()), p_l[mask]
            b5[f"{name}_top{k}"] = dict(late_n=int(mask.sum()), late_O=o, late_E=round(float(pp.sum()), 3),
                                       late_O_over_E=round(o / pp.sum(), 3) if pp.sum() > 0 else None,
                                       late_P=float(fs.poibin_sf(pp, o)),
                                       early_O=int(me.set_index("unit").loc[list(sel), "O"].sum()),
                                       early_E=round(float(me.set_index("unit").loc[list(sel), "E"].sum()), 3))
    summary["B5"] = b5
    print("B5", json.dumps(b5, ensure_ascii=False), flush=True)

    # B6: variants
    main_top10 = m.unit.head(10).tolist()
    var = [dict(variant="main", unit="m500", extra="", q_lt_005=b2["q_lt_005"], q_lt_010=b2["q_lt_010"],
                min_q=b2["min_q"], strata=b2["strata"], common_top10_with_main=10,
                common_top20_with_count=summary["B4"]["top20"]["common"])]
    for extra in ("sidewalk", "signal", "alignment", "motorway", "vulnerable"):
        mv, labv, _ = score(d, "m500", (extra,))
        var.append(dict(variant=f"+{extra}", unit="m500", extra=extra, q_lt_005=int((mv.q < 0.05).sum()),
                        q_lt_010=int((mv.q < 0.10).sum()), min_q=float(mv.q.min()), P_zero=int((mv.P == 0).sum()), strata=int(len(set(labv))),
                        common_top10_with_main=overlap(mv.unit.tolist(), main_top10, 10),
                        common_top20_with_count=turnover(mv)["top20"]["common"], top10=" ".join(mv.unit.head(10))))
    for col, lv in (("m1000", 3), ("m250", 5)):
        mv, labv, _ = score(d, col)
        vt = mv.unit.head(10).tolist()
        if lv == 3:
            common = sum(fs.mesh_parent(u, 3) in set(vt) for u in main_top10)
        else:
            common = sum(any(v.startswith(u) for v in vt) for u in main_top10)
        var.append(dict(variant=col, unit=col, extra="", q_lt_005=int((mv.q < 0.05).sum()),
                        q_lt_010=int((mv.q < 0.10).sum()), min_q=float(mv.q.min()), P_zero=int((mv.P == 0).sum()), strata=int(len(set(labv))),
                        common_top10_with_main=common, common_top20_with_count=turnover(mv)["top20"]["common"],
                        top10=" ".join(vt), meshes=int(len(mv))))
        mv.to_csv(OUT / f"meshes_{col}.csv", index=False, encoding="utf-8")
    var[0]["top10"] = " ".join(main_top10)
    pd.DataFrame(var).to_csv(OUT / "variants.csv", index=False, encoding="utf-8")
    print(pd.DataFrame(var).drop(columns=["top10"]).to_string(), flush=True)
    summary["seconds"] = round(time.time() - t0, 1)
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
