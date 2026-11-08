"""uvx --python 3.12 --with numpy --with pandas --with scipy --with pytest pytest -q -p no:cacheprovider test_diagnostics.py"""

import numpy as np
import pandas as pd
import pytest

from diagnostics import overlap_at_k, positive_union_spearman, rank_table, top_union_spearman

FRAME = pd.DataFrame({
    "mesh": ["m1", "m2", "m3", "m4", "m5"],
    "a": [5.0, 3.0, 3.0, 0.0, np.nan],
    "b": [1.0, 4.0, 2.0, 3.0, 0.0],
})


def test_rank_table_drops_zero_and_missing_and_breaks_ties_by_mesh():
    t = rank_table(FRAME, "a")
    assert t.mesh.tolist() == ["m1", "m2", "m3"] and t["rank"].tolist() == [1, 2, 3]
    assert rank_table(FRAME, "b").mesh.tolist() == ["m2", "m4", "m3", "m1"]


def test_overlap_at_k_counts_all_ordered_pairs():
    tables = {"a": rank_table(FRAME, "a"), "b": rank_table(FRAME, "b")}
    assert overlap_at_k(tables, 2) == {"a__a": 2, "a__b": 1, "b__a": 1, "b__b": 2}
    assert overlap_at_k(tables, 3)["a__b"] == 2              # {m1, m2, m3} & {m2, m4, m3}


def test_positive_union_spearman():
    # Union of positive rows: m1..m4 (m5 is NaN / 0). a = [5, 3, 3, 0], b = [1, 4, 2, 3].
    out = positive_union_spearman(FRAME, ["a", "b"], {"a": "a", "b": "b"})
    assert out["n"] == 4
    # ranks a = [4, 2.5, 2.5, 1], ranks b = [1, 4, 2, 3]: Pearson of the ranks = -0.6325.
    assert out["pairs"]["a__b"] == pytest.approx(np.corrcoef([4, 2.5, 2.5, 1], [1, 4, 2, 3])[0, 1])
    assert out["pairs"]["a__b"] == pytest.approx(-0.6325, abs=1e-4)
    assert out["pairs"]["a__a"] == pytest.approx(1.0)


def test_top_union_spearman_uses_union_of_top_k():
    out = top_union_spearman(FRAME, ["a", "b"], {"a": "a", "b": "b"}, k=1)
    # top 1 of a = m1, of b = m2 -> rows m1, m2: a = [5, 3], b = [1, 4] -> rho = -1
    assert out["n"] == 2 and out["k"] == 1 and out["pairs"]["a__b"] == pytest.approx(-1.0)
