"""Known-answer tests for the candidate models."""

import numpy as np
import pandas as pd
import pytest

import models as md


def toy(n_years=12, slope=2.0, noise=0.0, seed=0):
    rng = np.random.default_rng(seed)
    years = range(2000, 2000 + n_years)
    prefs = ["A", "B"]
    ts = {(p, y): rng.normal() for p in prefs for y in range(1995, 2000 + n_years + 1)}
    cues = pd.DataFrame([{"pref": p, "year": y, "Ts": ts[(p, y)], "Tsp": 0.0} for p, y in ts])
    index = pd.DataFrame([{"pref": p, "year": y, "stage": "fruiting",
                           "index": (1.0 if p == "A" else 2.0) + slope * ts[(p, y - 1)] + noise * rng.normal()}
                          for p in prefs for y in years])
    return index, cues


def test_design_lags_and_lead():
    index, cues = toy()
    d = md.design(index, cues)
    r = d[(d.pref == "A") & (d.year == 2005)].iloc[0]
    c = cues.set_index(["pref", "year"]).Ts
    assert r.Ts_lag1 == c[("A", 2004)] and r.Ts_lag2 == c[("A", 2003)] and r.Ts_lead1 == c[("A", 2006)]
    assert r.dT == pytest.approx(c[("A", 2004)] - c[("A", 2003)])
    assert r.F_lag == pytest.approx(index[(index.pref == "A") & (index.year == 2004)]["index"].iloc[0])


def test_fit_recovers_intercepts_and_slope_and_loyo_is_exact_without_noise():
    index, cues = toy()
    d = md.complete_rows(md.design(index, cues), {"M2": ["Ts_lag1"]})
    m = md.fit(d, ["Ts_lag1"])
    assert m["coef"] == pytest.approx([1.0, 2.0, 2.0])
    assert md.rmse(d.F, md.loyo(d, ["Ts_lag1"])) == pytest.approx(0, abs=1e-9)
    assert md.rmse(d.F, md.loyo(d, [])) > 1


def test_loyo_holds_out_every_prefecture_of_the_year():
    index, cues = toy(noise=1.0)
    d = md.complete_rows(md.design(index, cues), {"M2": ["Ts_lag1"]})
    p = md.loyo(d, ["Ts_lag1"])
    y0 = d.year == d.year.min()
    m = md.fit(d[~y0], ["Ts_lag1"])
    assert p[y0.to_numpy()] == pytest.approx(md.predict(m, d[y0]))


def test_choose_prefers_the_smallest_then_fewer_cues():
    s = {m: 1.0 for m in md.CANDIDATES}
    s.update({"M4": 0.5, "M2": 0.5005, "M7": 0.4})
    assert md.choose(s) == "M7"
    s["M7"] = 0.6
    assert md.choose(s) == "M2"  # within 0.001 of M4 and with fewer cues


def test_year_bootstrap_moves_prefectures_together():
    d = pd.DataFrame({"year": [1, 1, 2, 2], "pref": ["A", "B", "A", "B"], "F": [0.0, 0.0, 1.0, 1.0]})
    out = md.year_bootstrap(d, {"zero": np.zeros(4)}, B=200, seed=0)
    assert set(np.round(out["zero"] ** 2, 6)) <= {0.0, 0.5, 1.0}


def test_placebo_swaps_the_previous_summer_for_the_next():
    assert md.placebo(["Ts_lag1", "F_lag"]) == ["Ts_lead1", "F_lag"]
    assert md.placebo(["dT"]) == ["dT_lead"]
    with pytest.raises(ValueError):
        md.placebo(["F_lag"])
