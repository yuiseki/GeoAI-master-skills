"""uvx --python 3.12 --with 'duckdb>=1.5.5' --with numpy --with pandas --with scipy --with pytest pytest -q -p no:cacheprovider test_anomaly.py"""

# Tests for the scoring pieces of 02_anomaly.py (strata, score, overlap, turnover) and 03_explore.mesh_bounds.
import importlib

import numpy as np
import pandas as pd
import pytest

import fatalshare as fs

an = importlib.import_module("02_anomaly")
ex = importlib.import_module("03_explore")


def frame(rows):
    return pd.DataFrame(rows, columns=["shape_g", "width_g", "median_g", "fatal", "m500", "city"])


def test_strata_merge_rare_keys_to_the_top():
    # 8 accidents, 2 fatal -> min_n = ceil(8 / 2) = 4. The 6 crossing rows keep their full key; the 2 bridge rows are
    # fewer than 4 at every level and end in '*'.
    d = frame([["交差点", "01", "分離なし", f, "A", "101"] for f in (1, 0, 0, 0, 0, 0)]
              + [["橋", "01", "分離なし", f, "B", "101"] for f in (1, 0)])
    lab, min_n = an.strata(d)
    assert min_n == 4
    assert lab.tolist() == ["交差点|01|分離なし"] * 6 + ["*"] * 2


def test_score_leave_mesh_out_expectation_and_ranks():
    # One stratum (8 rows >= min_n 4). Mesh A: 4 rows, 2 deaths; B and C: 2 rows, no deaths.
    # A's rows see the other meshes' share 0 / 4 -> E_A = 0, P_A = P(X >= 2 | p = 0) = 0.
    # B's rows see (2 + 0) / (4 + 2) = 1/3 -> E_B = 2/3, O_B = 0, P_B = 1; C the same.
    rows = [["交差点", "01", "分離なし", f, "A", "101"] for f in (1, 1, 0, 0)]
    rows += [["交差点", "01", "分離なし", 0, u, "102"] for u in ("B", "B", "C", "C")]
    m, lab, min_n = an.score(frame(rows), "m500")
    m = m.set_index("unit")
    assert m.loc["A", "E"] == 0 and m.loc["A", "P"] == 0 and m.loc["A", "O"] == 2
    assert m.loc["B", "E"] == pytest.approx(2 / 3) and m.loc["B", "P"] == 1.0
    assert m.loc[["A", "B", "C"], "anomaly_rank"].tolist() == [1, 2, 3]       # tie B/C broken by unit
    assert m.loc[["A", "B", "C"], "count_rank"].tolist() == [1, 2, 3]
    # BH of P = [0, 1, 1]: q = [0, min(3/2, 3/3), 1] = [0, 1, 1]
    assert m.q.tolist() == [0.0, 1.0, 1.0]
    # k_needed against 0.05 / 3: A (p = 0) reaches it with 1; B: P(X>=2) = 1/9 > 0.0167 -> none, len + 1 = 3
    assert m.loc["A", "k_needed"] == 1 and m.loc["B", "k_needed"] == 3
    assert m.loc["A", "zero_p_rows"] == 4 and m.loc["B", "zero_p_rows"] == 0
    assert m.loc["A", "city"] == "101" and m.n.sum() == 8 and m.O.sum() == 2


def test_score_takes_a_custom_probability():
    rows = [["交差点", "01", "分離なし", f, u, "101"] for f, u in ((1, "A"), (0, "A"), (0, "B"), (0, "B"))]
    m, _, _ = an.score(frame(rows), "m500", p_fn=lambda s, u, f: np.full(len(f), 0.5))
    m = m.set_index("unit")
    assert m.loc["A", "E"] == 1.0 and m.loc["A", "P"] == pytest.approx(0.75)   # P(X >= 1), two coins
    assert m.loc["B", "P"] == 1.0


def test_overlap_and_turnover(monkeypatch):
    monkeypatch.setattr(an, "TOPS", (1, 2))
    m = pd.DataFrame({"unit": list("ABCD"), "n": [3, 4, 1, 2], "P": [0.01, 0.02, 0.5, 0.4],
                      "count_rank": [2, 1, 4, 3]})
    assert an.overlap(list("ABCD"), list("BADC"), 1) == 0 and an.overlap(list("ABCD"), list("BADC"), 2) == 2
    res = an.turnover(m)
    assert res["top1"] == dict(common=0, jaccard=0.0, random_expectation=0.25)
    assert res["top2"] == dict(common=2, jaccard=1.0, random_expectation=1.0)
    # rank n = [3, 4, 1, 2], rank P = [1, 2, 4, 3]: sum d^2 = 18, rho = 1 - 6*18/(4*15) = -0.8 -> reported +0.8
    assert res["spearman_n_vs_minus_log10_P"] == pytest.approx(0.8)


def test_mesh_bounds_contains_the_point_its_code_came_from():
    lat, lon = 35.6812, 139.7671                      # Tokyo station
    for level, (dlat, dlon) in ((3, (1 / 120, 1 / 80)), (4, (1 / 240, 1 / 160)), (5, (1 / 480, 1 / 320))):
        code = fs.mesh_code([lat], [lon], level)[0]
        w, s, e, n = ex.mesh_bounds(code)
        assert w <= lon < e and s <= lat < n
        assert e - w == pytest.approx(dlon) and n - s == pytest.approx(dlat)
    assert ex.mesh_bounds("53394611")[:2] == pytest.approx((139 + 6 / 8 + 1 / 80, 53 / 1.5 + 4 / 12 + 1 / 120))
