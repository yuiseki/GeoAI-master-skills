"""uvx --with h3 --with s2sphere --with numpy --with scipy --with esda --with libpysal --with pytest pytest test_grid_hotspots_crosscheck.py"""

# Gi* of grid_hotspots.py against esda.G_Local (star=True, binary weights with the cell itself) on H3 cells.

import h3
import numpy as np
import pytest
from esda.getisord import G_Local
from libpysal.weights import W

from grid_hotspots import gi_star, study_cells


def test_gi_star_matches_esda():
    cells = study_cells((-0.2, 51.45, -0.05, 51.55), 8)
    idx = {c: i for i, c in enumerate(cells)}
    rng = np.random.default_rng(3)
    x = rng.poisson(2.0, len(cells)).astype(float)
    x[:5] += 30
    nb = [[idx[v] for v in h3.grid_disk(c, 1) if v in idx] for c in cells]
    ours = gi_star(x, nb)
    neighbours = {i: [j for j in nb[i] if j != i] for i in range(len(cells))}
    w = W(neighbours, silence_warnings=True)
    g = G_Local(x, w, transform="B", star=True, permutations=0)
    assert ours == pytest.approx(np.asarray(g.Zs), rel=1e-6, abs=1e-9)
