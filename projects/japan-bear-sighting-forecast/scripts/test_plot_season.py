# uvx --with pandas --with matplotlib --with pytest python -m pytest -q projects/japan-bear-sighting-forecast/scripts/test_plot_season.py
import pandas as pd
import pytest

import plot_season as ps


def table(models=("hgb_nb", "naive")):
    return pd.DataFrame([{"model": m, "h": h, "season": s, "n": 1, "mae": 1.0 + k, "bias": 0.1, "capture5": 0.5}
                         for m in models for h in (1, 4) for k, s in enumerate(ps.SEASONS)])


def test_season_table_orders_seasons_and_models():
    t = ps.season_table(table(), 4, ["naive", "hgb_nb"])
    assert list(t.index) == ps.SEASONS
    assert list(t.columns.get_level_values(1).unique()) == ["naive", "hgb_nb"]
    assert t[("mae", "naive")].tolist() == [1.0, 2.0, 3.0, 4.0]


def test_season_table_refuses_a_missing_model():
    with pytest.raises(SystemExit):
        ps.season_table(table(models=("naive",)), 4, ["naive", "hgb_nb"])
