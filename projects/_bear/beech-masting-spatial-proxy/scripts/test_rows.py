import numpy as np
import pandas as pd
import pytest

import rows as R


def toy():
    years = range(1985, 2011)
    climate = pd.DataFrame([{"ID": i, "year": y, "Ts": y - 2000.0 + i, "Tsp": 0.1 * y, "P": 10.0 * y, "PET": y}
                            for i in (1, 2) for y in years])
    ranks = pd.DataFrame([{"ID": i, "year": y, "rank": float((y + i) % 4)} for i in (1, 2) for y in range(1989, 2009)
                          if not (i == 2 and y == 1999)])
    terrain = pd.DataFrame({"ID": [1, 2], "alt": [500, 900], "slope": [10.0, 20.0], "northness": [1.0, 0.0],
                            "eastness": [0.0, 1.0], "relief_300": [100.0, 200.0], "tpi_300": [5.0, -5.0],
                            "relief_1000": [300.0, 400.0], "tpi_1000": [10.0, -10.0]})
    sites = pd.DataFrame({"ID": [1, 2], "x": [0.0, 1000.0], "y_m": [0.0, 0.0]})
    return ranks, climate, terrain, sites


def test_cues_are_lagged_as_planned():
    ranks, climate, terrain, sites = toy()
    rows = R.build(ranks, climate, terrain, sites, 300)
    r = rows[(rows.ID == 1) & (rows.t == 2000)].iloc[0]
    assert r.Ts1 == pytest.approx(1999 - 2000 + 1) and r.Ts2 == pytest.approx(1998 - 2000 + 1)
    assert r.dT == pytest.approx(1.0)
    assert r.Tsp == pytest.approx(200.0)  # spring of t itself
    assert r.P == pytest.approx(19990.0) and r.PET == pytest.approx(1999.0)  # summer of t - 1
    assert r.WB == pytest.approx(19990.0 - 1999.0)
    assert r.lag_own == float((1999 + 1) % 4)
    assert r.elev == 500 and r.relief == 100.0 and r.tpi == 5.0
    assert R.build(ranks, climate, terrain, sites, 1000).query("ID == 1 and t == 2000").relief.iloc[0] == 300.0


def test_missing_rank_drops_the_row_and_leaves_next_lag_empty():
    ranks, climate, terrain, sites = toy()
    rows = R.build(ranks, climate, terrain, sites, 300)
    assert rows.query("ID == 2 and t == 1999").empty
    assert np.isnan(rows.query("ID == 2 and t == 2000").lag_own.iloc[0])
    assert rows.t.min() == 1990 and rows.t.max() == 2008


def test_missing_climate_stops():
    ranks, climate, terrain, sites = toy()
    with pytest.raises(KeyError):
        R.build(ranks, climate[climate.year != 1995], terrain, sites, 300)
