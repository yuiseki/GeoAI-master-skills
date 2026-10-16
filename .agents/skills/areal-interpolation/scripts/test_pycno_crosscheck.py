"""uvx --with numpy --with geopandas --with shapely --with rasterio --with tobler --with pytest pytest test_pycno_crosscheck.py

Against PySAL's tobler (0.14) pycno_interpolate with handle_null=False, whose edge rule is this script's
edge="mean". Sources and targets are blocks of unit cells written as polygons, so tobler's rasterisation lands
exactly on this grid (row 0 at the top).
"""

import numpy as np
import pytest
from shapely.geometry import box

from pycno import pycno, to_targets

gpd = pytest.importorskip("geopandas")
tobler_pycno = pytest.importorskip("tobler.pycno")


def _blocks(n, b, offset=0):
    r, c = np.indices((n, n))
    lab = ((r - offset) // b) * ((n + b) // b + 1) + (c - offset) // b
    return np.where((r >= offset) & (c >= offset), lab, -1)


def _polygons(labels, n):
    geoms, ids = [], []
    for z in np.unique(labels[labels >= 0]):
        rr, cc = np.nonzero(labels == z)
        geoms.append(box(cc.min(), n - rr.max() - 1, cc.max() + 1, n - rr.min()))
        ids.append(int(z))
    return ids, geoms


def test_pycno_matches_tobler():
    n, b = 30, 6
    zones = _blocks(n, b)
    targets = _blocks(n, 5, offset=0)
    rng = np.random.default_rng(3)
    zid, zgeo = _polygons(zones, n)
    totals = {z: float(rng.uniform(100, 1000)) for z in zid}
    src = gpd.GeoDataFrame({"v": [totals[z] for z in zid]}, geometry=zgeo, index=zid, crs="EPSG:3857")
    tid, tgeo = _polygons(targets, n)
    tgt = gpd.GeoDataFrame({"tid": tid}, geometry=tgeo, crs="EPSG:3857")
    ref = tobler_pycno.pycno_interpolate(src, tgt, variables=["v"], cellsize=1, r=0.2, handle_null=False,
                                         converge=3, verbose=False)
    surface, _ = pycno(zones, totals, r=0.2, converge=3, edge="mean")
    ours = to_targets(surface, targets)
    np.testing.assert_allclose([ours[t] for t in tid], ref["v"].to_numpy(), rtol=1e-6)
