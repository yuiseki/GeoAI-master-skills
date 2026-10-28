import math

import numpy as np
import pandas as pd
import pytest

import model as M


def grid_sites(n=8, step=20_000.0):
    """n x n sites on a 20 km grid (EPSG:6691-like metres)."""
    ids, xs, ys = [], [], []
    for i in range(n):
        for j in range(n):
            ids.append(len(ids) + 1)
            xs.append(300_000.0 + i * step)
            ys.append(4_400_000.0 + j * step)
    return pd.DataFrame({"ID": ids, "x": xs, "y_m": ys})


def test_blocks_keep_cells_together_and_folds_are_seeded():
    s = grid_sites()
    b = M.blocks(s)
    f1 = M.spatial_folds(s, 0)
    f2 = M.spatial_folds(s, 0)
    assert [t for t, _ in f1] == [t for t, _ in f2]
    fold_of = {i: k for k, (test, _) in enumerate(f1) for i in test}
    assert set(fold_of) == set(s.ID)
    for blk, ids in b.groupby(b).groups.items():
        assert len({fold_of[i] for i in ids}) == 1
    assert [t for t, _ in M.spatial_folds(s, 1)] != [t for t, _ in f1]


def test_buffer_leaves_out_every_site_near_a_test_site():
    s = grid_sites()
    xy = s.set_index("ID")
    for test, train in M.spatial_folds(s, 3):
        assert not set(test) & set(train)
        for i in train:
            d = np.hypot(xy.loc[test, "x"] - xy.at[i, "x"], xy.loc[test, "y_m"] - xy.at[i, "y_m"]).min()
            assert d > M.BUFFER_M
        # the buffer must bite: some non-test sites are within 15 km... on a 20 km grid none are, so use 25 km
    for test, train in M.spatial_folds(s, 3, buffer_m=25_000.0):
        left = set(s.ID) - set(test) - set(train)
        assert left  # neighbours 20 km away are dropped


def test_neighbour_lag_uses_only_training_sites_and_not_itself():
    s = pd.DataFrame({"ID": [1, 2, 3, 4], "x": [0.0, 1.0, 2.0, 100.0], "y_m": [0.0, 0.0, 0.0, 0.0]})
    ranks = pd.DataFrame({"ID": [1, 2, 3, 4], "year": [1999] * 4, "rank": [0, 1, 2, 3]})
    rows = pd.DataFrame({"ID": [1, 2, 4], "t": [2000, 2000, 2000]})
    lag = M.neighbour_lag(rows, ranks, train_ids=[1, 2, 3], sites=s, k=2)
    assert lag.tolist() == [1.5, 1.0, 1.5]  # site 1: sites 2, 3; site 2: sites 1, 3; site 4 (test): sites 3, 2
    # a site without a rank at t - 1 is skipped, not counted as 0
    ranks2 = ranks[ranks.ID != 3]
    assert M.neighbour_lag(rows.iloc[:1], ranks2, [1, 2, 3], s, k=2).tolist() == [1.0]


def test_fit_recovers_coefficients_and_clips():
    rng = np.random.default_rng(0)
    n = 400
    d = pd.DataFrame({"lag": rng.uniform(0, 3, n), "dT": rng.normal(0, 1, n), "elev": rng.uniform(200, 1200, n)})
    d["y"] = 2.0 - 0.5 * d.lag + 0.3 * d.dT
    d["t"] = 2000
    beta_pred = M.fit_predict(d, d, "M2")
    assert np.allclose(beta_pred, np.clip(d.y, 0, 3))
    far = d.iloc[:1].assign(dT=100.0)
    assert M.fit_predict(d, far, "M2")[0] == 3.0


def test_interaction_uses_training_centre_in_km():
    rows = pd.DataFrame({"dT": [2.0], "elev": [1500.0], "WB": [0.0], "northness": [0.0]})
    X = M.design(rows, ["dT:elev"], elev_centre=500.0)
    assert X.tolist() == [[1.0, 2.0]]


def test_bootstrap_moves_whole_years():
    err = pd.DataFrame({"model": ["a"] * 4 + ["b"] * 4, "ID": [1, 2, 1, 2] * 2, "t": [1, 1, 2, 2] * 2,
                        "se": [0, 0, 1, 1, 1, 1, 1, 1]})
    b = M.year_bootstrap(err, "a", "b", reps=500)
    assert b["years"] == 2 and b["rows"] == 4
    assert b["diff"] == pytest.approx(math.sqrt(0.5) - 1)
    # resampled years give 0 - 1 (both year 1), 1 - 1 (both year 2) or the point: never anything else
    assert b["lo90"] >= -1 - 1e-12 and b["hi90"] <= 0 + 1e-12
    same = M.year_bootstrap(err.assign(model="a").pipe(lambda e: pd.concat([e, e.assign(model="b")])), "a", "b",
                            reps=50)
    assert same["diff"] == 0 and same["lo90"] == 0 and same["hi90"] == 0


def test_rule():
    assert M.rule({"diff": -0.1, "hi90": -0.01}) == "supported"
    assert M.rule({"diff": 0.0, "hi90": 0.2}) == "rejected"
    assert M.rule({"diff": -0.1, "hi90": 0.05}) == "undecided"


def synthetic(interaction, seed=0, n=8, years=range(1989, 2009)):
    """Sites on a grid; the year signal dT is shared, and its effect grows with elevation if interaction."""
    rng = np.random.default_rng(seed)
    s = grid_sites(n)
    s["elev"] = rng.uniform(200, 1200, len(s))
    yr = {y: rng.normal(0, 1) for y in years}
    rows, ranks = [], []
    prev = {i: 1.0 for i in s.ID}
    for y in years:
        for r in s.itertuples():
            eff = 0.4 + (1.2 * (r.elev - 700) / 1000.0 if interaction else 0.0)
            v = 1.5 + eff * yr[y] - 0.3 * (prev[r.ID] - 1.5) + rng.normal(0, 0.3)
            rank = float(np.clip(np.round(v), 0, 3))
            ranks.append({"ID": r.ID, "year": y, "rank": rank})
            rows.append({"ID": r.ID, "t": y, "y": rank, "lag_own": prev[r.ID], "dT": yr[y], "elev": r.elev,
                         "slope": 0.0, "northness": 0.0, "eastness": 0.0, "relief": 0.0, "tpi": 0.0,
                         "WB": rng.normal(0, 1), "P": 0.0, "PET": 0.0, "Ts1": 0.0, "Ts2": 0.0, "Tsp": 0.0})
            prev[r.ID] = rank
    rows = pd.DataFrame(rows)
    return rows[rows.t >= 1990], pd.DataFrame(ranks), s


def test_C_scheme_finds_a_planted_interaction_and_not_a_missing_one():
    years = list(range(1990, 2009))
    out = {}
    for planted in (True, False):
        rows, ranks, s = synthetic(planted)
        pred = M.run_BC(rows, ranks, s, "C", years, years, ["M4", "M5"], "w1", repeats=2)
        err = M.common_rows(M.row_errors(pred), ["M4", "M5"])
        out[planted] = M.year_bootstrap(err, "M5", "M4", reps=300)
    assert out[True]["hi90"] < 0  # the interaction helps when it is there
    assert out[False]["diff"] > -0.02  # and gives nothing much when it is not


def test_A_never_trains_on_the_test_year_or_the_next():
    rows, ranks, s = synthetic(False)
    seen = []
    orig = M.fit_predict

    def spy(train, test, *a, **k):
        seen.append((set(train.t), set(test.t)))
        return orig(train, test, *a, **k)

    M.fit_predict = spy
    try:
        M.run_A(rows, [1995], range(1990, 2009), ["M1"], "w1")
    finally:
        M.fit_predict = orig
    tr, te = seen[0]
    assert te == {1995} and not tr & {1995, 1996}
