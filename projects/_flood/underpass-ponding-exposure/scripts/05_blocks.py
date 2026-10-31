"""B1 to B4 of the plan and the robustness table, from measures.parquet.

uvx --from 'duckdb>=1.5.5' --with numpy python scripts/05_blocks.py [--measures PATH] [--out outputs/blocks.json]

Rules (fixed in EXPERIMENT_PLAN.md):
- measurable: the nearest eligible road within MATCH m and a measurable profile in the setting;
- captured: measurable and depth >= THRESH m;
- top share: the top 10% by score among the points measurable in both settings, ties broken by id;
- AUC: Mann-Whitney, ties counted half; intervals are the 5th and 95th percentiles of 1,000 resamples (seed 0).
"""
import argparse
import json
import sys
from pathlib import Path

import duckdb
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
ART = ROOT / "artifacts/_flood/underpass-ponding-exposure"
sys.path.insert(0, str(ROOT / "evals/curriculum/dry-runs/underpass-pilots"))
from kansui_labels import NONE, RECORD  # noqa: E402  the same sign rules as the dry-run

B = 1000
MAIN, VARIANTS = None, None


def use(prefix):
    """Score columns of one depth rule: `depth` (bottom within 30 m, the plan) or `depthw` (bottom within L,
    added after the visual check, exploratory)."""
    global MAIN, VARIANTS
    MAIN = f"{prefix}_mix_100"
    VARIANTS = {"dem_5a_only": f"{prefix}_5a_100", "dem_10b_only": f"{prefix}_10b_100", "L50": f"{prefix}_mix_50",
                "L200": f"{prefix}_mix_200", "surface": "surface_mix", "depth_and_catchment": f"combo_{prefix}"}


def auc(score, y):
    """Probability that a positive scores above a negative, ties counting half."""
    score, y = np.asarray(score, float), np.asarray(y, bool)
    pos, neg = score[y], score[~y]
    if len(pos) == 0 or len(neg) == 0:
        return None
    d = np.subtract.outer(pos, neg)
    return float((d > 0).mean() + 0.5 * (d == 0).mean())


def interval(vals):
    v = np.array([x for x in vals if x is not None])
    return [float(np.percentile(v, 5)), float(np.percentile(v, 95))] if len(v) else None


def top_set(score, ids, share):
    order = np.lexsort((ids, -np.asarray(score)))
    return set(order[:int(np.ceil(share * len(score)))].tolist())


def overlap(a, b, ids, share):
    A, Bs = top_set(a, ids, share), top_set(b, ids, share)
    return len(A & Bs) / len(A), len(A & Bs) / len(A | Bs)


def load(path, match):
    c = duckdb.connect()
    rows = c.execute(f"select * from '{path}' order by id").fetchdf()
    rows["matched"] = rows["match_m"].notna() & (rows["match_m"] <= match)
    for col in [x for x in rows.columns if x.startswith("ok_")]:
        rows[col] = rows[col].fillna(False).astype(bool) & rows["matched"]
    pct = lambda s: s.rank(pct=True)
    ok = rows["ok_mix_100"] & rows["catch_m2"].notna()
    for p in ("depth", "depthw"):
        rows[f"combo_{p}"] = np.where(ok, (pct(rows[f"{p}_mix_100"].where(ok)) + pct(rows["catch_m2"].where(ok))) / 2, np.nan)
    return rows


def ok_col(score):
    if score == "surface_mix":
        return None
    if score.startswith("combo"):
        return "ok_mix_100"
    return "ok_" + score.split("_", 1)[1]


def measurable(rows, score):
    oc = ok_col(score)
    m = rows[score].notna()
    if oc:
        m &= rows[oc]
    elif score == "surface_mix":
        m &= rows["matched"]
    return m


def b1(rows, thresh, n_all):
    m = measurable(rows, MAIN)
    cap = m & (rows[MAIN] >= thresh)
    by = lambda col: {str(k): {"n": int(len(g)), "measurable": int(m[g.index].sum()), "captured": int(cap[g.index].sum()),
                               "share_of_measurable": cap[g.index].sum() / max(m[g.index].sum(), 1)}
                      for k, g in rows.groupby(col)}
    return {"threshold_m": thresh, "n_all": n_all, "matched": int(rows["matched"].sum()), "measurable": int(m.sum()),
            "captured": int(cap.sum()), "share_of_all": cap.sum() / n_all, "share_of_measurable": cap.sum() / max(m.sum(), 1),
            "by_block": by("block"), "by_dem": by("dem_mix_100")}


def b2(rows, share, rng):
    out = {}
    for name, col in VARIANTS.items():
        m = measurable(rows, MAIN) & measurable(rows, col)
        sub = rows[m]
        if len(sub) < 10:
            out[name] = {"n": int(len(sub))}
            continue
        a, b, ids = sub[MAIN].to_numpy(), sub[col].to_numpy(), np.arange(len(sub))
        ov, jac = overlap(a, b, ids, share)
        boot = []
        for _ in range(B):
            k = rng.integers(0, len(sub), len(sub))
            boot.append(overlap(a[k], b[k], ids, share))
        out[name] = {"n": int(len(sub)), "overlap": ov, "jaccard": jac,
                     "overlap_90": interval([x[0] for x in boot]), "jaccard_90": interval([x[1] for x in boot])}
    return out


def tokyo_labels(rows, dist, since=None, heavy=None):
    """Tokyo points within `dist` m (EPSG:6677) of a flood record (areas and points). With `heavy`, only records
    whose days had a greatest 1 hour rain >= heavy mm at the nearest mainland station that has a value then."""
    c = duckdb.connect()
    c.execute("load spatial")
    c.execute("set geometry_always_xy = true")
    c.register("t", rows[rows["pref"] == "東京都"][["id", "lon", "lat"]])
    cond = f"where year >= {since}" if since else ""
    c.execute(f"""create table f as select row_number() over () rid, dis_date_s, dis_date_e,
            st_transform(geometry::GEOMETRY, 'EPSG:4612', 'EPSG:6677') g
        from (select * from '{ART / 'raw/flood_record_area.parquet'}' union all by name
              select * from '{ART / 'raw/flood_record_point.parquet'}') {cond}""")
    c.execute("create table p as select id, st_transform(st_point(lon, lat), 'EPSG:4326', 'EPSG:6677') g from t")
    c.execute(f"create table hit as select p.id, f.rid, f.dis_date_s, f.dis_date_e from p join f on st_dwithin(p.g, f.g, {dist})")
    if not heavy:
        return rows["id"].isin({r[0] for r in c.execute("select distinct id from hit").fetchall()})
    c.execute(f"""create table st as select station_id, st_transform(st_point(lon, lat), 'EPSG:4326', 'EPSG:6677') g
        from '{ART / 'raw/rain_stations.parquet'}' where lat > 35.4""")
    c.execute(f"""create table rr as select h.id, h.rid, r.station_id, max(r.max1h_mm) mx
        from hit h join '{ART / 'raw/rain_daily.parquet'}' r on r.date between h.dis_date_s and h.dis_date_e
        where r.station_id in (select station_id from st) group by all having max(r.max1h_mm) is not null""")
    c.execute("""create table pick as select rr.id, rr.rid, arg_min(rr.mx, st_distance(p.g, st.g)) mx
        from rr join p using (id) join st using (station_id) group by all""")
    return rows["id"].isin({r[0] for r in c.execute(f"select distinct id from pick where mx >= {heavy}").fetchall()})


def b3(rows, rng, **kw):
    y_all = tokyo_labels(rows, **kw) & (rows["pref"] == "東京都")
    m = measurable(rows, MAIN) & (rows["pref"] == "東京都")
    s, y = rows.loc[m, MAIN].to_numpy(), y_all[m].to_numpy()
    boot = []
    for _ in range(B):
        k = rng.integers(0, len(s), len(s))
        boot.append(auc(s[k], y[k]))
    return {"n": int(m.sum()), "positives": int(y.sum()), "auc": auc(s, y), "auc_90": interval(boot), **kw}


def kansui_labels(rows):
    c = duckdb.connect()
    c.execute("load spatial")
    c.execute("set geometry_always_xy = true")
    c.register("u", rows[["id", "lon", "lat"]])
    hrr = ["注意喚起方法", "情報入手方法", "冠水原因", "冠水範囲", "その他"]
    txt = ", ".join(f"json_extract_string(r.extra_cells, '$.\"{k}\"')" for k in hrr)
    c.execute(f"""create table k as select k.fid, k.pref, k.lon, k.lat, pp.pdf_match, r.parse_status,
            concat_ws(' ', r.remarks, {txt}) txt,
            coalesce(json_extract_string(r.extra_cells, '$."1m以上の冠水の有無"'), '') deep
        from '{ART / 'raw/kansui_points.parquet'}' k join '{ART / 'raw/kansui_point_pdf.parquet'}' pp using (fid)
        left join '{ART / 'raw/kansui_pdf_records.parquet'}' r on r.pdf_key = pp.pdf_key""")
    c.execute(f"""create table lab as select fid, pref, lon, lat, pdf_match = 'pdf_unique' and parse_status is not null
            and parse_status <> 'layout_unknown' readable,
            (regexp_matches(txt, '{RECORD}') and not regexp_matches(txt, '{NONE}')) rec_text,
            regexp_matches(deep, '^(有|あり)') rec_deep,
            (regexp_matches(txt, '{RECORD}') and not regexp_matches(txt, '{NONE}')) or regexp_matches(deep, '^(有|あり)') rec,
            regexp_matches(txt, 'ポンプ') pump, regexp_matches(txt, '水位センサ|冠水センサ|水位計') sensor from k""")
    c.execute("""create table near as select u.id, arg_min(lab.fid, st_distance_sphere(st_point(u.lon, u.lat), st_point(lab.lon, lab.lat))) fid,
            min(st_distance_sphere(st_point(u.lon, u.lat), st_point(lab.lon, lab.lat))) d
        from u join lab on abs(u.lat - lab.lat) < 0.01 and abs(u.lon - lab.lon) < 0.01 group by 1""")
    prefs = [r[0] for r in c.execute("select distinct pref from lab where readable and rec").fetchall()]
    lab = c.execute("select near.id, lab.readable, lab.rec, lab.rec_text, lab.rec_deep, lab.pump, lab.sensor from near join lab using (fid) where d <= 30").fetchdf()
    return lab, prefs


def b4(rows, rng, label="rec"):
    """label: rec (the plan: text record or the Hokuriku 1 m flag), rec_text (text records only, exploratory)."""
    lab, prefs = kansui_labels(rows)
    lab["rec"] = lab[label]
    d = rows.merge(lab, on="id")
    d = d[measurable(d, MAIN) & d["readable"] & d["pref"].isin(prefs)]
    use = [p for p, g in d.groupby("pref") if g["rec"].sum() >= 3 and (~g["rec"]).sum() >= 3]
    d = d[d["pref"].isin(use)]
    groups = {p: (g[MAIN].to_numpy(), g["rec"].to_numpy(bool)) for p, g in d.groupby("pref")}

    def weighted(gs):
        a = [(auc(s, y), len(s)) for s, y in gs.values()]
        a = [(x, n) for x, n in a if x is not None]
        return sum(x * n for x, n in a) / sum(n for _, n in a) if a else None
    boot = []
    for _ in range(B):
        bs = {}
        for p, (s, y) in groups.items():
            k = rng.integers(0, len(s), len(s))
            bs[p] = (s[k], y[k])
        boot.append(weighted(bs))
    per = {p: {"n": len(s), "positives": int(y.sum()), "auc": auc(s, y)} for p, (s, y) in groups.items()}
    desc = {f: auc(d[MAIN], d[f].astype(bool)) for f in ("pump", "sensor")}
    return {"prefs_with_signs": prefs, "prefs_used": use, "n_prefs_used": len(use), "n": int(len(d)), "positives": int(d["rec"].sum()),
            "auc_weighted": weighted(groups), "auc_weighted_90": interval(boot), "by_pref": per,
            "descriptive_auc_equipment": desc}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--measures", default=str(ART / "measures.parquet"))
    ap.add_argument("--out", default=str(HERE.parent / "outputs/blocks.json"))
    a = ap.parse_args()
    rows = load(a.measures, 30)
    n_all = len(rows)
    res = {"sanity": {"n": n_all, "matched_30": int(rows["matched"].sum()),
                      "ambiguous": int((rows["matched"] & rows["ambiguous"].fillna(False)).sum()),
                      "tunnel": int((rows["matched"] & rows["tunnel"].fillna(False)).sum())}}
    m = measurable(rows, "depth_mix_100")
    mt = rows["matched"]
    res["sanity"]["not_measurable_reason"] = {
        "short_side": int((mt & ((rows["left_m"] < 50) | (rows["right_m"] < 50))).sum()),
        "short_side_or_no_value": int((mt & ~measurable(rows, "depth_mix_100")).sum())}
    res["sanity"]["dip_only_away_from_point"] = int((m & (rows["depth_mix_100"] < 2) & (rows["depthw_mix_100"] >= 2)).sum())
    for prefix, mode in (("depth", "confirmatory"), ("depthw", "exploratory")):
        use(prefix)
        rng = np.random.default_rng(0)
        r = {"mode": mode, "B1": b1(rows, 2.0, n_all), "B2": b2(rows, 0.10, rng), "B3": b3(rows, rng, dist=30),
             "B4": b4(rows, rng)}
        rob = {}
        for t in (1.0, 3.0):
            rob[f"B1_threshold_{t:g}"] = b1(rows, t, n_all)
        for mm in (15, 50):
            r2 = load(a.measures, mm)
            rob[f"match_{mm}"] = {"B1": b1(r2, 2.0, n_all), "B2": b2(r2, 0.10, rng), "B3": b3(r2, rng, dist=30)}
        nt = rows[~rows["tunnel"].fillna(False).astype(bool)].copy()
        rob["no_tunnel"] = {"B1": b1(nt, 2.0, n_all), "B2": b2(nt, 0.10, rng)}
        dd = rows.drop_duplicates(subset=["lon", "lat"]).copy()
        rob["dedupe_coords"] = {"n": len(dd), "B1": b1(dd, 2.0, len(dd)), "B2": b2(dd, 0.10, rng)}
        for sh in (0.05, 0.20):
            rob[f"B2_top_{sh:g}"] = b2(rows, sh, rng)
        for kw in ({"dist": 0}, {"dist": 100}, {"dist": 30, "since": 1997}, {"dist": 30, "heavy": 30},
                   {"dist": 30, "heavy": 50}):
            rob["B3_" + "_".join(f"{k}{v}" for k, v in kw.items())] = b3(rows, rng, **kw)
        rob["B4_text_records_only"] = b4(rows, rng, label="rec_text")  # exploratory: the 1 m flag can follow depth by construction
        r["robustness"] = rob
        res[prefix] = r
    Path(a.out).parent.mkdir(exist_ok=True)
    Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=1, default=float) + "\n")
    print(json.dumps(res["sanity"], ensure_ascii=False))


if __name__ == "__main__":
    main()
