# uvx --with matplotlib --with pytest python -m pytest -q projects/bear-outbreak-weather/scripts/test_plot_rho.py
import pytest

import plot_rho as pr


def explore(measures):
    return {"measures": {m: {"rho": 0.1, "p_two_sided": 0.5, "per_region_rho": {"akita": 0.2}} for m in measures}}


H1 = {"H1": {"rho": -0.28, "p_perm_one_sided": 0.08, "per_region_rho": {"akita": -0.6}},
      "falsification_future_dT": {"rho": -0.38, "p_two_sided": 0.06}}


def test_rows_put_the_planned_test_first_then_the_falsification_then_the_exploration():
    rows = pr.rows(H1, explore([m for m, _ in pr.EXPLORE]))
    assert [r["key"] for r in rows] == ["H1", "future_dT"] + [m for m, _ in pr.EXPLORE]
    assert rows[0]["p"] == 0.08 and rows[0]["regions"] == {"akita": -0.6}
    assert rows[1]["regions"] == {}


def test_rows_refuse_a_missing_measure():
    with pytest.raises(SystemExit):
        pr.rows(H1, explore(["T_now"]))
