"""uvx --with numpy --with rasterio --with pyproj --with scipy --with scikit-image --with pytest pytest test_cost_distance_crosscheck.py

solve() against scikit-image's MCP_Geometric, scipy's csgraph Dijkstra, and, when the grass command
is on the PATH, GRASS GIS r.cost. The GRASS tests write small GeoTIFFs and run r.cost in a temporary
location; they are skipped without GRASS.
"""

import math
import os
import shutil
import subprocess

import numpy as np
import pytest
import rasterio
from rasterio.transform import Affine
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra
from skimage.graph import MCP_Geometric

from cost_distance import solve


def _world(seed, h=12, w=15, blocked=0.2):
    rng = np.random.default_rng(seed)
    cost = rng.uniform(0.3, 4.0, size=(h, w))
    passable = rng.random((h, w)) > blocked
    starts = [tuple(map(int, rc)) for rc in np.argwhere(passable)[[0, -1]]]
    return cost, passable, starts


@pytest.mark.parametrize("seed", range(5))
def test_matches_scikit_image_mcp_geometric_when_corners_may_be_cut(seed):
    # MCP_Geometric: a step costs its length times the mean of the two cells; infinite costs are not
    # entered, and a diagonal step between two of them is taken (our corner rule 'allow').
    cost, passable, starts = _world(seed)
    dx, dy = 10.0, 30.0
    mcp = MCP_Geometric(np.where(passable, cost, np.inf), fully_connected=True, sampling=(dy, dx))
    ref, _ = mcp.find_costs(starts)
    ours = solve(cost, passable, dx, dy, starts, corner="allow")
    assert np.allclose(ours["accumulated"][passable], ref[passable], rtol=1e-12, atol=1e-9)
    for r, c in np.argwhere(passable & np.isfinite(ref))[::7]:
        assert starts.index(tuple(mcp.traceback((int(r), int(c)))[0])) == ours["nearest"][r, c]


def _graph(cost, passable, dx, dy, corner):
    """The same graph built edge by edge for scipy, independently of solve's loop."""
    h, w = cost.shape
    rows, cols, vals = [], [], []
    for r in range(h):
        for c in range(w):
            if not passable[r, c]:
                continue
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    rr, cc = r + dr, c + dc
                    if (dr, dc) == (0, 0) or not (0 <= rr < h and 0 <= cc < w) or not passable[rr, cc]:
                        continue
                    if dr and dc and corner == "both" and not passable[r + dr, c] and not passable[r, c + dc]:
                        continue
                    rows.append(r * w + c)
                    cols.append(rr * w + cc)
                    vals.append(math.hypot(dr * dy, dc * dx) * (cost[r, c] + cost[rr, cc]) / 2)
    return coo_matrix((vals, (rows, cols)), shape=(h * w, h * w)).tocsr()


@pytest.mark.parametrize("seed", range(5))
def test_matches_scipy_multi_source_dijkstra(seed):
    cost, passable, starts = _world(seed, blocked=0.35)
    dx, dy = 7.0, 4.0
    g = _graph(cost, passable, dx, dy, "both")
    idx = [r * cost.shape[1] + c for r, c in starts]
    dist, _, src = dijkstra(g, indices=idx, min_only=True, return_predecessors=True)
    ours = solve(cost, passable, dx, dy, starts)
    assert np.allclose(np.where(np.isinf(dist), -1, dist), np.where(np.isinf(ours["accumulated"]), -1,
                                                                     ours["accumulated"]).ravel())
    reached = np.isfinite(dist)
    assert (np.array([idx.index(s) for s in src[reached]]) == ours["nearest"].ravel()[reached]).all()


GRASS = shutil.which("grass")


def _grass(tmp_path, cost, transform, starts_xy, extra=""):
    """r.cost on cost (NaN as NULL); returns the accumulated cost and the nearest start (1-based)."""
    with rasterio.open(tmp_path / "cost.tif", "w", driver="GTiff", height=cost.shape[0], width=cost.shape[1],
                       count=1, dtype="float64", crs="EPSG:32654", transform=transform, nodata=np.nan) as ds:
        ds.write(cost, 1)
    coords = ",".join(f"{x},{y}" for x, y in starts_xy)
    (tmp_path / "run.sh").write_text(
        f"r.in.gdal input=cost.tif output=cost --overwrite --quiet\n"
        f"g.region raster=cost\n"
        f"r.cost {extra} input=cost output=acc nearest=near start_coordinates={coords} --overwrite --quiet\n"
        f"r.out.gdal -c input=acc output=acc.tif format=GTiff type=Float64 --overwrite --quiet\n"
        f"r.out.gdal -c input=near output=near.tif format=GTiff type=Float64 --overwrite --quiet\n")
    env = {k: v for k, v in os.environ.items() if k not in ("GDAL_DATA", "PROJ_LIB", "PROJ_DATA",
                                                            "GDAL_DRIVER_PATH", "PYTHONPATH", "PYTHONHOME",
                                                            "VIRTUAL_ENV")}
    subprocess.run([GRASS, "--tmp-location", "EPSG:32654", "--exec", "bash", "run.sh"], cwd=tmp_path, env=env,
                   check=True, capture_output=True, timeout=300)
    with rasterio.open(tmp_path / "acc.tif") as a, rasterio.open(tmp_path / "near.tif") as n:
        return a.read(1), n.read(1)


def _centre(transform, r, c):
    return transform @ (c + 0.5, r + 0.5)


@pytest.mark.skipif(GRASS is None, reason="GRASS GIS (grass) is not on the PATH")
@pytest.mark.parametrize("seed", range(3))
def test_grass_r_cost_times_the_pixel_width_matches(tmp_path, seed):
    # r.cost measures steps in pixel widths (east-west = 1, north-south = ns_res / ew_res), so its
    # accumulated cost times the east-west resolution is ours for a cost per metre.
    cost, passable, starts = _world(seed, blocked=0.1)
    t = Affine(10, 0, 380_000, 0, -30, 3_950_000)
    acc, near = _grass(tmp_path, np.where(passable, cost, np.nan), t, [_centre(t, r, c) for r, c in starts])
    ours = solve(cost, passable, 10.0, 30.0, starts, corner="allow")
    ok = passable & np.isfinite(acc)
    assert ok.sum() > 0.8 * passable.sum()
    assert np.allclose(ours["accumulated"][ok], acc[ok] * 10, rtol=1e-9)
    assert (ours["nearest"][ok] == near[ok] - 1).all()


@pytest.mark.skipif(GRASS is None, reason="GRASS GIS (grass) is not on the PATH")
def test_grass_r_cost_cuts_corners_through_a_diagonal_wall(tmp_path):
    cost = np.ones((6, 6))
    wall = np.eye(6, dtype=bool)
    t = Affine(10, 0, 380_000, 0, -10, 3_950_000)
    acc, _ = _grass(tmp_path, np.where(wall, np.nan, cost), t, [_centre(t, 5, 0)])
    upper = np.triu_indices(6, 1)
    assert np.isfinite(acc[upper]).all()  # r.cost goes through the wall at its corners
    allow = solve(cost, ~wall, 10.0, 10.0, [(5, 0)], corner="allow")["accumulated"]
    assert np.allclose(acc[~wall] * 10, allow[~wall])
    assert np.isinf(solve(cost, ~wall, 10.0, 10.0, [(5, 0)])["accumulated"][upper]).all()


@pytest.mark.skipif(GRASS is None, reason="GRASS GIS (grass) is not on the PATH")
@pytest.mark.parametrize("seed,blocked", [(0, 0.0), (1, 0.0), (0, 0.2), (2, 0.2)])
def test_grass_r_cost_knights_moves_match(tmp_path, seed, blocked):
    # r.cost -k adds knight's moves at the mean of the four cells crossed, as here, and (with barriers) does
    # not take one across an impassable cell between: the same cells are reached at the same cost.
    cost, passable, starts = _world(seed, blocked=blocked)
    t = Affine(10, 0, 380_000, 0, -10, 3_950_000)
    acc, near = _grass(tmp_path, np.where(passable, cost, np.nan), t, [_centre(t, r, c) for r, c in starts],
                       extra="-k")
    ours = solve(cost, passable, 10.0, 10.0, starts, corner="allow", neighbours=16)
    reached = np.isfinite(ours["accumulated"])
    assert (reached == (passable & np.isfinite(acc))).all()
    assert np.allclose(ours["accumulated"][reached], acc[reached] * 10, rtol=1e-9)
