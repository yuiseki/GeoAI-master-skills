"""uvx --with numpy --with matplotlib --with pytest pytest test_cvd.py"""

import matplotlib
import numpy as np
import pytest

from cvd import lab, report, simulate


def _sample(name, k=7):
    cmap = matplotlib.colormaps[name]
    return np.array([cmap((i + 0.5) / k)[:3] for i in range(k)])


def test_white_black_and_greys_are_kept_by_every_simulation():
    greys = np.array([[0, 0, 0], [0.5, 0.5, 0.5], [1, 1, 1.0]])
    for kind in ("protan", "deutan", "tritan"):
        np.testing.assert_allclose(simulate(greys, kind), greys, atol=2e-3)


def test_lab_of_known_colours():
    np.testing.assert_allclose(lab(np.array([[1.0, 1, 1]])), [[100, 0, 0]], atol=1e-3)
    np.testing.assert_allclose(lab(np.array([[0.0, 0, 0]])), [[0, 0, 0]], atol=1e-6)
    np.testing.assert_allclose(lab(np.array([[1.0, 0, 0]]))[0], [53.24, 80.09, 67.20], atol=0.05)


def test_red_and_green_come_together_for_protan_and_deutan_but_not_tritan():
    rg = np.array([[0.84, 0.15, 0.16], [0.17, 0.63, 0.17]])  # matplotlib's tab:red and tab:green
    d = {k: float(np.sqrt(((lab(simulate(rg, k))[0] - lab(simulate(rg, k))[1]) ** 2).sum()))
         for k in ("normal", "protan", "deutan", "tritan")}
    assert d["protan"] < 0.4 * d["normal"] and d["deutan"] < 0.4 * d["normal"]
    assert d["tritan"] > 0.6 * d["normal"]


def test_a_red_green_diverging_palette_loses_its_two_sides_and_red_blue_keeps_them():
    # Measured with 7 classes: RdYlGn's two ends 109.8 apart in normal vision, 19.4 (protan) and 23.5 (deutan);
    # RdBu 82.9, 53.6 and 75.4. The sides of a diverging palette are told apart by hue, not lightness.
    rdylgn = report(_sample("RdYlGn"), diverging=True)
    rdbu = report(_sample("RdBu"), diverging=True)
    for kind in ("protan", "deutan"):
        assert rdylgn[kind]["ends_delta_e"] < 0.3 * rdylgn["normal"]["ends_delta_e"]
        assert rdbu[kind]["ends_delta_e"] > 0.6 * rdbu["normal"]["ends_delta_e"]


def test_viridis_keeps_its_order_and_jet_has_none_in_any_vision():
    v, j = report(_sample("viridis")), report(_sample("jet"))
    assert all(v[k]["lightness_ordered"] for k in v)
    assert not any(j[k]["lightness_ordered"] for k in j)
    assert min(v[k]["min_delta_e"] for k in v) > 10  # measured 10.3 (deutan) at the dark end
