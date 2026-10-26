# uvx --with numpy --with pandas --with matplotlib --with pytest python -m pytest -q projects/akita-bear-risk-grid-100m/scripts/test_plot_figures.py
import pandas as pd
import pytest

import plot_figures as pf


def table(drop=None):
    rows = []
    for b in pf.BUILDING + ["(all)"]:
        for e in pf.EDGE + ["(all)"]:
            if (b, e) != drop and not (b == "(all)" and e == "(all)"):
                rows.append({"building": b, "forest_edge": e, "cells": 10, "share_with_report": 0.1, "cells_with_report": 1})
    return pd.DataFrame(rows)


def test_edge_matrix_orders_rows_and_columns():
    share, cells = pf.edge_matrix(table())
    assert list(share.index) == pf.BUILDING + ["(all)"]
    assert list(share.columns) == pf.EDGE
    assert cells.shape == share.shape


def test_edge_matrix_refuses_a_missing_class():
    with pytest.raises(SystemExit):
        pf.edge_matrix(table(drop=(pf.BUILDING[0], pf.EDGE[3])))
