"""Tests for the anomalies, the A/B/C runs, the within-year Spearman and the permutations (model.py), on synthetic
sites: a within-year site signal planted in the satellite anomaly must be found in C, a year-only signal must not,
F2 must break a site signal and F1 a year signal."""

import numpy as np
import pandas as pd
import pytest

import model as M

SAT = M.SAT


def grid_sites(n=8, step=20_000.0):
    ids, xs, ys = [], [], []
    for i in range(n):
        for j in range(n):
            ids.append(len(ids) + 1)
            xs.append(300_000.0 + i * step)
            ys.append(4_400_000.0 + j * step)
    return pd.DataFrame({"ID": ids, "x": xs, "y_m": ys})


# ---- anomalies ----

def test_anomaly_uses_only_the_climatology_years():
    raw = pd.DataFrame({"ID": [1] * 4, "t": [2000, 2001, 2002, 2003], **{c: [1.0, 2.0, 3.0, 100.0] for c in SAT}})
    a = M.anomalies(raw, clim_years=[2000, 2001, 2002], min_years=2)
    # the test year 2003 (100) is not in the climatology (mean 2)
    assert a.set_index("t").loc[2003, SAT[0]] == 98.0
    assert a.set_index("t").loc[2000, SAT[0]] == -1.0


def test_anomaly_leave_own_year_out_for_B():
    raw = pd.DataFrame({"ID": [1] * 3, "t": [2000, 2001, 2002], **{c: [1.0, 2.0, 6.0] for c in SAT}})
    a = M.anomalies(raw, clim_years=[2000, 2001, 2002], min_years=2, leave_own_year=True).set_index("t")
    assert a.loc[2002, SAT[0]] == 6.0 - 1.5
    assert a.loc[2000, SAT[0]] == 1.0 - 4.0


def test_anomaly_missing_when_too_few_years_not_zero():
    raw = pd.DataFrame({"ID": [1, 1, 1], "t": [2000, 2001, 2002],
                        **{c: [np.nan, np.nan, 5.0] for c in SAT}})
    a = M.anomalies(raw, clim_years=[2000, 2001, 2002], min_years=2)
    assert a[SAT].isna().all().all()


# ---- within-year Spearman ----

def test_within_year_spearman_equal_weights_and_constant_years():
    p = pd.DataFrame({"ID": list(range(12)) * 3, "t": [2000] * 12 + [2001] * 12 + [2002] * 12,
                      "y": list(range(12)) * 2 + [1.0] * 12,
                      "pred": list(range(12)) + list(range(12))[::-1] + list(range(12))})
    w = M.within_year(p)
    assert w["by_year"] == {2000: 1.0, 2001: -1.0, 2002: 0.0}  # constant observations give 0
    assert w["mean"] == 0.0


def test_within_year_drops_years_with_fewer_than_10_rows():
    p = pd.DataFrame({"ID": list(range(12)) + list(range(9)), "t": [2000] * 12 + [2001] * 9,
                      "y": list(range(12)) + list(range(9)), "pred": list(range(12)) + list(range(9))[::-1]})
    w = M.within_year(p)
    assert w["by_year"] == {2000: 1.0} and w["years_dropped"] == [2001]


def test_bootstrap_of_within_year_difference_moves_years():
    a = {2000: 0.5, 2001: 0.5, 2002: 0.5}
    b = {2000: 0.0, 2001: 0.0, 2002: 0.0}
    r = M.diff_bootstrap(a, b, reps=200)
    assert r["diff"] == 0.5 and r["lo90"] == 0.5 and r["hi90"] == 0.5
    r = M.diff_bootstrap({2000: 1.0, 2001: -1.0}, {2000: 0.0, 2001: 0.0}, reps=500)
    assert r["diff"] == 0.0 and r["lo90"] == -1.0 and r["hi90"] == 1.0


def test_rule_needs_positive_point_and_lower_bound():
    assert M.rule({"diff": 0.1, "lo90": 0.01}) == "supported"
    assert M.rule({"diff": 0.1, "lo90": -0.01}) == "not supported"
    assert M.rule({"diff": -0.1, "lo90": -0.2}) == "not supported"


def test_centered_rmse_ignores_the_year_level():
    p = pd.DataFrame({"t": [2000, 2000, 2001, 2001], "y": [0.0, 1.0, 2.0, 3.0], "pred": [5.0, 6.0, -1.0, 0.0]})
    assert M.centered_rmse(p) == 0.0


# ---- synthetic study ----

def synthetic(kind, seed=0, n=8, years=range(1989, 2009)):
    """kind: 'site' plants a within-year site signal carried by the spring NDVI anomaly; 'year' plants only a year
    signal (all sites share the anomaly, which also moves the outcome); 'none' plants nothing."""
    rng = np.random.default_rng(seed)
    s = grid_sites(n)
    base = {i: rng.normal(0.8, 0.05) for i in s.ID}
    yr = {y: rng.normal(0, 1) for y in years}
    rows, ranks, raw = [], [], []
    prev = {i: 1.5 for i in s.ID}
    for y in years:
        for r in s.itertuples():
            site_dev = rng.normal(0, 1)
            sat = {c: base[r.ID] + rng.normal(0, 0.02) for c in SAT}
            v = 1.5 + 0.6 * yr[y] - 0.2 * (prev[r.ID] - 1.5) + rng.normal(0, 0.3)
            if kind == "site":
                sat["ndvi_cs"] = base[r.ID] + 0.05 * site_dev
                v += 0.8 * site_dev
            if kind == "year":
                sat["ndvi_cs"] = base[r.ID] + 0.05 * yr[y] + rng.normal(0, 0.002)
            rank = float(np.clip(np.round(v), 0, 3))
            ranks.append({"ID": r.ID, "year": y, "rank": rank})
            rows.append({"ID": r.ID, "t": y, "y": rank, "lag_own": prev[r.ID], "dT": yr[y]})
            raw.append({"ID": r.ID, "t": y, **sat})
            prev[r.ID] = rank
    rows = pd.DataFrame(rows).merge(s, on="ID")
    return rows[rows.t >= 1990].reset_index(drop=True), pd.DataFrame(ranks), s, pd.DataFrame(raw)


YEARS = list(range(1990, 2009))


def run_C(kind, models=("B0", "S2"), transform=None, seed=0):
    rows, ranks, s, raw = synthetic(kind, seed)
    pred = M.run_BC(rows, raw, ranks, s, "C", YEARS[-9:], YEARS, list(models), min_years=5, repeats=2,
                    transform=transform)
    return M.evaluate(pred, list(models))


def test_C_finds_a_planted_within_year_site_signal():
    ev = run_C("site")
    h = M.diff_bootstrap(ev["within"]["S2"]["by_year"], ev["within"]["B0"]["by_year"], reps=300)
    assert h["diff"] > 0.2 and M.rule(h) == "supported"


def test_C_does_not_find_a_year_only_signal_within_years():
    ev = run_C("year")
    h = M.diff_bootstrap(ev["within"]["S2"]["by_year"], ev["within"]["B0"]["by_year"], reps=300)
    assert M.rule(h) == "not supported"


def test_F2_breaks_a_site_signal_and_F1_breaks_it_too():
    rows, ranks, s, raw = synthetic("site")
    real = M.evaluate(M.run_BC(rows, raw, ranks, s, "C", YEARS[-9:], YEARS, ["S2"], min_years=5, repeats=1),
                      ["S2"])["within"]["S2"]["mean"]
    f2 = M.site_permutation(raw, np.random.default_rng(1))
    f1 = M.year_permutation(YEARS, np.random.default_rng(1))
    for tf in (f2, f1):
        perm = M.evaluate(M.run_BC(rows, raw, ranks, s, "C", YEARS[-9:], YEARS, ["S2"], min_years=5, repeats=1,
                                   transform=tf), ["S2"])["within"]["S2"]["mean"]
        assert perm < real - 0.2


def test_site_permutation_keeps_each_year_and_moves_sites():
    raw = pd.DataFrame({"ID": [1, 2, 3, 1, 2, 3], "t": [2000] * 3 + [2001] * 3})
    an = raw.assign(**{c: [1.0, 2.0, 3.0, 4.0, 5.0, 6.0] for c in SAT})
    tf = M.site_permutation(an, np.random.default_rng(0))
    out = tf(an)
    for t, g in out.groupby("t"):
        assert sorted(g[SAT[0]]) == sorted(an[an.t == t][SAT[0]])
        assert (g[SAT].nunique(axis=1) == 1).all()  # the four features move together
    assert not out[SAT[0]].equals(an[SAT[0]])


def test_year_permutation_moves_all_sites_together():
    an = pd.DataFrame({"ID": [1, 2, 1, 2, 1, 2], "t": [2000, 2000, 2001, 2001, 2002, 2002],
                       **{c: [10.0, 20.0, 11.0, 21.0, 12.0, 22.0] for c in SAT}})
    tf = M.year_permutation([2000, 2001, 2002], np.random.default_rng(3))
    out = tf(an).set_index(["ID", "t"])[SAT[0]]
    src = {t: int(round(out[(1, t)] - 10)) + 2000 for t in (2000, 2001, 2002)}
    for t in (2000, 2001, 2002):
        assert out[(2, t)] == 20.0 + (src[t] - 2000)
    assert sorted(src.values()) == [2000, 2001, 2002]


def test_A_and_C_climatology_never_holds_the_test_year():
    rows, ranks, s, raw = synthetic("none")
    seen = []
    orig = M.anomalies

    def spy(r, clim_years, *a, **k):
        seen.append(set(clim_years))
        return orig(r, clim_years, *a, **k)

    M.anomalies = spy
    try:
        M.run_A(rows, raw, [2005], YEARS, ["B0"], min_years=5)
        M.run_BC(rows, raw, ranks, s, "C", [2005], YEARS, ["B0"], min_years=5, repeats=1)
    finally:
        M.anomalies = orig
    assert seen and all(not c & {2005, 2006} for c in seen)


def test_all_models_scored_on_the_same_rows():
    rows, ranks, s, raw = synthetic("none")
    raw.loc[raw.sample(frac=0.2, random_state=0).index, "ndmi_ps"] = np.nan
    pred = M.run_BC(rows, raw, ranks, s, "C", YEARS[-3:], YEARS, list(M.FEATURES), min_years=5, repeats=1)
    ev = M.evaluate(pred, list(M.FEATURES))
    n = {m: v["n"] for m, v in ev["scores"].items()}
    assert len(set(n.values())) == 1
    with pytest.raises(KeyError):
        M.FEATURES["M7"]
