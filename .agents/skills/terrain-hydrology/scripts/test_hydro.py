"""uvx --python 3.12 --with pyflwdir --with numpy --with rasterio --with pyproj --with pytest pytest test_hydro.py"""

import csv
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from hydro import edge_mask, flow, run, snap

HERE = Path(__file__).parent
TR = from_origin(320000, 3950000, 10, 10)  # UTM 54N near 35.6 N, 139 E; 10 m cells
CELL_KM2 = 100 / 1e6


def valley(h=41, w=31, pit=True):
    """Sides fall 1 m per cell to the centre column, the floor falls 0.1 m per row to the bottom edge."""
    r, c = np.indices((h, w))
    cc = w // 2
    z = np.abs(c - cc) * 1.0 + (h - 1 - r) * 0.1 + 100
    if pit:
        z[h // 2, cc] -= 3.0
    return z


def boxed_valley(h=40, w=30):
    """A valley inside ridges (row 5 and columns 2 and w-3, 2000 m), outside the ridges low ground falling to the
    raster edge. The valley drains out through the bottom edge between the side ridges."""
    r, c = np.indices((h, w))
    z = 10.0 + np.minimum(np.minimum(r, c), w - 1 - c)          # outside: falls to the nearest edge
    inside = (r >= 6) & (c >= 3) & (c <= w - 4)
    cc = w // 2
    z = np.where(inside, 100 + np.abs(c - cc) + (h - 1 - r) * 0.1, z)
    ridge = ((r == 5) & (c >= 2) & (c <= w - 3)) | (((c == 2) | (c == w - 3)) & (r >= 5))
    return np.where(ridge, 2000.0, z)


def write(path, z, crs="EPSG:32654", transform=TR, nodata=-9999.0):
    with rasterio.open(path, "w", driver="GTiff", height=z.shape[0], width=z.shape[1], count=1, dtype="float32",
                       crs=crs, transform=transform, nodata=nodata) as d:
        d.write(z.astype("float32"), 1)
    return path


def points_csv(path, rows):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "x", "y"])
        for pid, (r, c) in rows.items():
            x, y = TR * (c + 0.5, r + 0.5)
            w.writerow([pid, x, y])
    return path


def bands(path):
    with rasterio.open(path) as s:
        return s.read()


def test_every_cell_drains_to_the_outlet_through_the_pit(tmp_path):
    z = valley()
    filled, d8, fd = flow(z, TR)
    upa = fd.upstream_area(unit="cell")
    h, w = z.shape
    assert upa[h - 1, w // 2] == h * w                      # all cells, the pit's included
    # the pit is filled to its spill level: the lower of its neighbours, the next floor cell downstream
    assert filled[h // 2, w // 2] == pytest.approx(z[h // 2 + 1, w // 2])
    assert np.all(filled >= z - 1e-9)                        # filling never lowers


def test_d8_is_steepest_descent_not_the_lowest_neighbour():
    """On a valley side the step across (1 m in 10 m) is steeper than the step down the diagonal (1.1 m in 14.1 m),
    though the diagonal neighbour is lower. pyflwdir's own directions take the lowest neighbour."""
    z = valley(pit=False)
    cc = z.shape[1] // 2
    _, d8, _ = flow(z, TR)
    assert d8[20, cc + 3] == 16 and d8[20, cc - 3] == 1      # W and E, towards the floor
    assert d8[20, cc] == 4                                    # S along the floor
    _, d8f, _ = flow(z, TR, rule="flood")
    assert d8f[20, cc + 3] == 8 and d8f[20, cc - 3] == 2      # SW and SE: the lowest neighbour


def bowl_valley():
    """The valley with a closed bowl (rows 4-9, columns 1-5, 50 m) in its upper left side."""
    z = valley(pit=False)
    z[4:10, 1:6] = 50.0
    return z


def test_a_closed_bowl_spills_into_the_valley_unless_it_is_a_sink():
    z = bowl_valley()
    h, w = z.shape
    cc = w // 2
    _, _, fd = flow(z, TR)
    assert fd.upstream_area(unit="cell")[h - 1, cc] == h * w            # filled over: everything reaches the outlet
    sink = 6 * w + 3
    _, d8, fd = flow(z, TR, sinks=[sink])
    upa = fd.upstream_area(unit="cell")
    assert d8.flat[sink] == 0
    assert upa.flat[sink] >= 30                                          # the bowl's 30 cells at least
    # the edge is still an outlet: the bowl and the outlet share every cell between them
    assert upa[h - 1, cc] + upa.flat[sink] == h * w


def test_sinks_from_a_file(tmp_path):
    z = bowl_valley()
    h, w = z.shape
    write(tmp_path / "d.tif", z)
    points_csv(tmp_path / "s.csv", {"bowl": (6, 3)})
    out = run(tmp_path / "d.tif", tmp_path / "o.tif", points_csv(tmp_path / "p.csv", {"outlet": (h - 1, w // 2)}),
              snap_m=0, snap_min_km2=0, sinks=tmp_path / "s.csv")
    _, _, fd = flow(z, TR, sinks=[6 * w + 3])
    assert out[0]["catchment_cells"] == h * w - fd.upstream_area(unit="cell").flat[6 * w + 3]


def test_flats_drain_without_loops():
    """A filled lake is a flat: no strictly lower neighbour, so the flood's directions carry it to the outlet."""
    z = valley(pit=False)
    h, w = z.shape
    cc = w // 2
    z[15:25, cc - 3:cc + 4] = 50.0                            # a deep basin, filled to a flat lake by the filling
    filled, d8, fd = flow(z, TR)
    lake = filled[15:25, cc - 3:cc + 4]
    assert np.ptp(lake) < 1e-9
    assert fd.upstream_area(unit="cell")[h - 1, cc] == h * w  # every cell still reaches the outlet


def test_two_valleys_split_by_a_ridge(tmp_path):
    left, right = valley(41, 15, pit=False), valley(41, 16, pit=False)
    z = np.hstack([left, np.full((41, 1), 500.0), right])
    write(tmp_path / "d.tif", z)
    out = run(tmp_path / "d.tif", tmp_path / "o.tif", points_csv(tmp_path / "p.csv", {"L": (40, 7), "R": (40, 24)}),
              snap_m=0, snap_min_km2=0)
    got = {o["id"]: o["catchment_cells"] for o in out}
    # the ridge column drains to one side or the other; each side gets its own cells plus part of the ridge
    assert got["L"] + got["R"] == z.size
    assert 41 * 15 <= got["L"] <= 41 * 16 and 41 * 16 <= got["R"] <= 41 * 17


def test_enclosed_catchment_is_exact_and_not_flagged(tmp_path):
    z = boxed_valley()
    h, w = z.shape
    write(tmp_path / "d.tif", z)
    out = run(tmp_path / "d.tif", tmp_path / "o.tif", points_csv(tmp_path / "p.csv", {"in": (h - 5, w // 2), "out": (h - 1, w // 2)}),
              snap_m=0, snap_min_km2=0)
    o = {r["id"]: r for r in out}
    assert o["in"]["catchment_cells"] == (h - 5 - 6 + 1) * (w - 6)   # rows 6..h-5 of the box interior
    assert o["in"]["edge_cells"] == 0
    assert o["in"]["catchment_km2"] == pytest.approx(o["in"]["catchment_cells"] * CELL_KM2)
    assert o["in"]["upstream_km2"] == pytest.approx(o["in"]["catchment_km2"])
    assert o["out"]["edge_cells"] > 0                       # the outlet's catchment holds bottom-edge cells


def test_snap_takes_the_nearest_stream_cell_not_the_largest_downstream(tmp_path):
    z = valley(pit=False)
    h, w = z.shape
    cc = w // 2
    _, _, fd = flow(z, TR)
    upa = fd.upstream_area(unit="km2")
    thr = w * CELL_KM2                                      # only the centre column reaches w cells
    r, c, d = snap(upa, 20, cc + 3, radius_cells=10, min_area=thr)
    assert (r, c) == (20, cc) and d == pytest.approx(3)
    # the rule this replaces (largest upstream area in the radius) jumps 7 rows downstream
    win = upa[10:31, cc - 7:cc + 14]
    i, j = np.unravel_index(np.argmax(win), win.shape)
    assert (10 + i, cc - 7 + j) == (30, cc)


def test_no_stream_within_the_radius_gives_no_catchment(tmp_path):
    z = valley(pit=False)
    write(tmp_path / "d.tif", z)
    out = run(tmp_path / "d.tif", tmp_path / "o.tif", points_csv(tmp_path / "p.csv", {"far": (5, 0)}),
              snap_m=20, snap_min_km2=1.0)
    assert out[0]["snapped"] is False and out[0]["catchment_km2"] == ""


def test_hand_is_the_drop_to_the_stream_along_the_flow_path(tmp_path):
    z = valley(pit=False)
    h, w = z.shape
    cc = w // 2
    write(tmp_path / "d.tif", z)
    run(tmp_path / "d.tif", tmp_path / "o.tif", stream_km2=w * CELL_KM2 * 0.999)
    b = bands(tmp_path / "o.tif")
    stream, hand = b[2], b[3]
    assert np.array_equal(np.where(stream[:, :] == 1)[1], np.full(h, cc))   # only the centre column
    for k in range(1, cc + 1):
        assert hand[20, cc + k] == pytest.approx(k, abs=1e-4)
        assert hand[20, cc - k] == pytest.approx(k, abs=1e-4)
    assert np.all(hand[:, cc] == 0)


def test_nodata_is_kept_out_and_counted(tmp_path):
    z = valley(pit=False)
    z[0:5, 0:5] = -9999.0
    write(tmp_path / "d.tif", z)
    run(tmp_path / "d.tif", tmp_path / "o.tif", stream_km2=0.001)
    b = bands(tmp_path / "o.tif")
    assert np.all(np.isnan(b[:, 0:5, 0:5]))
    h, w = z.shape
    assert b[0, h - 1, w // 2] == pytest.approx((z.size - 25) * CELL_KM2, rel=1e-5)


def test_edge_mask():
    v = np.ones((5, 5), bool)
    v[2, 2] = False
    e = edge_mask(v)
    assert e[0].all() and e[:, 0].all() and e[1, 1] and not e[2, 2]
    assert e.sum() == 16 + 8  # the border, and the ring around the hole (the hole itself is not valid)


@pytest.mark.parametrize("crs,transform,msg", [
    (None, TR, "no CRS"),
    ("EPSG:4326", from_origin(139.0, 35.6, 0.0001, 0.0001), "geographic"),
    ("EPSG:3857", from_origin(15470000, 4245000, 10, 10), "areal scale"),
    ("EPSG:2263", from_origin(1000000, 200000, 30, 30), "unit"),
])
def test_grids_that_would_give_wrong_areas_stop(tmp_path, crs, transform, msg):
    write(tmp_path / "d.tif", valley(), crs=crs, transform=transform)
    with pytest.raises(SystemExit, match=msg):
        run(tmp_path / "d.tif", tmp_path / "o.tif")


def test_command_writes_the_raster_and_the_points(tmp_path):
    z = boxed_valley()
    h, w = z.shape
    write(tmp_path / "d.tif", z)
    points_csv(tmp_path / "p.csv", {"in": (h - 5, w // 2 + 2)})
    res = subprocess.run([sys.executable, str(HERE / "hydro.py"), str(tmp_path / "d.tif"), "--out", str(tmp_path / "o.tif"),
                          "--points", str(tmp_path / "p.csv"), "--snap-m", "30", "--snap-min-km2", "0.01",
                          "--stream-km2", "0.01"], capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    assert "snapped 1, not snapped 0" in res.stdout
    with open(str(tmp_path / "o.tif") + ".points.csv") as f:
        row = next(csv.DictReader(f))
    assert int(row["col"]) == w // 2 and float(row["snap_m"]) == pytest.approx(20)
    assert bands(tmp_path / "o.tif").shape == (5, h, w)
