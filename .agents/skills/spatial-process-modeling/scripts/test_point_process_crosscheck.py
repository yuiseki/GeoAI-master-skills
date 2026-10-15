"""uvx --from 'duckdb>=1.5.5' --with pyproj --with numpy --with statsmodels --with pytest pytest test_point_process_crosscheck.py

point_process against statsmodels' Poisson GLM. Grid counts with log-area offsets are the same model, so the
answers must agree exactly. The point-process likelihood is compared with the Berman-Turner device (data points
and dummy points as weighted Poisson rows), a different quadrature of the same likelihood: the two must approach
each other as the quadrature is refined. Set GEOAI_REALDATA=1 to also fit evacuation sites around Tokyo Station.
"""

import math
import os

import numpy as np
import pytest
import statsmodels.api as sm

from point_process import (fit_grid_poisson, fit_poisson_process, grid_counts, intensity_upper, quadrature,
                           simulate_poisson)

UNIT = (0.0, 1.0, 0.0, 1.0)


def _berman_turner(points, window, n, cov):
    q, w = quadrature(window, n)
    x0, x1, y0, y1 = window
    cell = ((x1 - x0) / n, (y1 - y0) / n)
    allp = np.r_[points, q]
    ix = np.clip(((allp[:, 0] - x0) // cell[0]).astype(int), 0, n - 1)
    iy = np.clip(((allp[:, 1] - y0) // cell[1]).astype(int), 0, n - 1)
    key = iy * n + ix
    share = np.bincount(key, minlength=n * n)[key]  # points of all kinds in the same cell share its area
    wt = (cell[0] * cell[1]) / share
    z = np.r_[np.ones(len(points)), np.zeros(len(q))]
    X = sm.add_constant(cov(allp), has_constant="add")
    r = sm.GLM(z / wt, X, family=sm.families.Poisson(), var_weights=wt).fit()
    return r.params, r.bse


def _world(seed=0):
    rng = np.random.default_rng(seed)
    lam = lambda xy: np.exp(6 + 1.5 * xy[:, 0] - 1.0 * xy[:, 1] ** 2)
    return simulate_poisson(lam, UNIT, intensity_upper(lam, UNIT), rng)


def test_grid_poisson_equals_a_glm_with_area_offsets():
    pts = _world()
    g = grid_counts(pts, UNIT, cell=0.1, origin=0.05)  # cut cells at the edges: unequal areas
    cov = np.c_[g["centres"][:, 0], g["centres"][:, 1] ** 2]
    ours = fit_grid_poisson(g["counts"], cov, g["area"])
    glm = sm.GLM(g["counts"], sm.add_constant(cov), family=sm.families.Poisson(), offset=np.log(g["area"])).fit()
    assert ours["beta"] == pytest.approx(glm.params, rel=1e-9)
    assert ours["se"] == pytest.approx(glm.bse, rel=1e-6)


def test_the_likelihood_approaches_berman_turner_as_the_quadrature_is_refined():
    pts = _world()
    cov = lambda xy: np.c_[xy[:, 0], xy[:, 1] ** 2]
    gaps = []
    for n in (20, 80, 320):
        q, w = quadrature(UNIT, n)
        ours = fit_poisson_process(cov(pts), cov(q), w)
        bt, bt_se = _berman_turner(pts, UNIT, n, cov)
        gaps.append(np.max(np.abs(ours["beta"] - bt)))
        if n == 320:
            assert ours["beta"] == pytest.approx(bt, abs=0.01)
            assert ours["se"] == pytest.approx(bt_se, rel=0.01)
    assert gaps[0] > gaps[1] > gaps[2]


@pytest.mark.skipif(os.environ.get("GEOAI_REALDATA") != "1", reason="real data: set GEOAI_REALDATA=1")
def test_evacuation_sites_around_tokyo_station():
    duckdb = pytest.importorskip("duckdb")
    from pyproj import Transformer

    to_m = Transformer.from_crs("EPSG:4326", "EPSG:6690", always_xy=True)  # JGD2011 UTM 54N
    cx, cy = to_m.transform(139.7671, 35.6812)
    window = (cx - 10_000, cx + 10_000, cy - 10_000, cy + 10_000)
    rows = duckdb.sql("""select longitude, latitude from 'hf://datasets/yuiseki/gsi-evacuation-sites-jp/parquet/sites.parquet'
                         where longitude between 139.6 and 139.95 and latitude between 35.55 and 35.8""").fetchall()
    x, y = to_m.transform([r[0] for r in rows], [r[1] for r in rows])
    p = np.c_[x, y]
    p = p[(p[:, 0] >= window[0]) & (p[:, 0] < window[1]) & (p[:, 1] >= window[2]) & (p[:, 1] < window[3])]
    p = np.unique(p, axis=0)  # several designations of one place share a point
    km = lambda xy: (xy - [window[0], window[2]]) / 1000.0  # kilometres from the window's corner
    p = km(p)
    win = (0.0, 20.0, 0.0, 20.0)
    cov = lambda xy: np.sqrt(((xy - 10.0) ** 2).sum(axis=1))[:, None]  # km to Tokyo Station
    q, w = quadrature(win, 400)
    ours = fit_poisson_process(cov(p), cov(q), w)
    bt, bt_se = _berman_turner(p, win, 400, cov)
    assert len(p) == 516  # sites in the 20 km square on 2026-10-15
    assert ours["beta"] == pytest.approx(bt, abs=0.01)
    assert ours["se"] == pytest.approx(bt_se, rel=0.02)
    g = grid_counts(p, win, cell=1.0)
    gc = cov(g["centres"])
    glm = sm.GLM(g["counts"], sm.add_constant(gc), family=sm.families.Poisson(), offset=np.log(g["area"])).fit()
    assert fit_grid_poisson(g["counts"], gc, g["area"])["beta"] == pytest.approx(glm.params, rel=1e-9)
