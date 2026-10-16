"""uvx --with numpy --with rasterio --with pyproj --with pytest pytest test_cost_distance.py"""

import csv
import heapq
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import Affine

from cost_distance import BARRIER, NODATA, REACHED, UNREACHABLE, grid_metres, solve

R2 = math.sqrt(2)


def _brute(cost, passable, dx, dy, sources, corner="both"):
    """Bellman-Ford relaxation until nothing changes, with the same edge rule: an independent
    reference for the heap-based solver."""
    h, w = cost.shape
    acc = np.full((h, w), np.inf)
    for r, c in sources:
        acc[r, c] = 0.0
    changed = True
    while changed:
        changed = False
        for r in range(h):
            for c in range(w):
                if not passable[r, c] or acc[r, c] == np.inf:
                    continue
                for dr in (-1, 0, 1):
                    for dc in (-1, 0, 1):
                        rr, cc = r + dr, c + dc
                        if (dr, dc) == (0, 0) or not (0 <= rr < h and 0 <= cc < w) or not passable[rr, cc]:
                            continue
                        if dr and dc:
                            blocked = [not passable[r + dr, c], not passable[r, c + dc]]
                            if (corner == "both" and all(blocked)) or (corner == "either" and any(blocked)):
                                continue
                        d = math.hypot(dr * dy, dc * dx)
                        v = acc[r, c] + d * (cost[r, c] + cost[rr, cc]) / 2
                        if v < acc[rr, cc] - 1e-12:
                            acc[rr, cc] = v
                            changed = True
    return acc


def _ok(shape):
    return np.ones(shape, bool)


# 1, 2. uniform cost: axial, diagonal and a knight's step


def test_uniform_cost_is_cost_times_distance_along_axes_and_diagonals():
    cost = np.full((5, 5), 0.5)  # 0.5 s/m
    res = solve(cost, _ok(cost.shape), 10.0, 10.0, [(2, 2)])
    acc = res["accumulated"]
    assert acc[2, 2] == 0
    assert acc[2, 4] == pytest.approx(2 * 10 * 0.5)  # two cells east
    assert acc[0, 2] == pytest.approx(2 * 10 * 0.5)  # two cells north
    assert acc[0, 0] == pytest.approx(2 * 10 * R2 * 0.5)  # two cells diagonally
    # A knight's step is one diagonal and one axial move in an 8-neighbour grid, not sqrt(5) cells.
    assert acc[1, 4] == pytest.approx((R2 + 1) * 10 * 0.5)
    assert acc[1, 4] > math.sqrt(5) * 10 * 0.5


def test_edge_cost_is_the_mean_of_the_two_cells_times_the_step_length():
    cost = np.array([[1.0, 3.0, 5.0]])
    res = solve(cost, _ok(cost.shape), 2.0, 2.0, [(0, 0)])
    # Half of each step lies in each cell: 1 m at 1 s/m and 1 m at 3 s/m, then 1 m at 3 and 1 m at 5.
    assert res["accumulated"][0].tolist() == pytest.approx([0, 4, 12])


# 9. non-square pixels


def test_non_square_pixels_use_width_east_west_and_height_north_south():
    cost = np.ones((3, 3))
    acc = solve(cost, _ok(cost.shape), 10.0, 30.0, [(1, 1)])["accumulated"]
    assert acc[1, 2] == pytest.approx(10)
    assert acc[0, 1] == pytest.approx(30)
    assert acc[0, 0] == pytest.approx(math.hypot(10, 30))


# 3. several destinations


def test_each_cell_takes_the_cheaper_destination_and_its_id():
    cost = np.ones((1, 7))
    res = solve(cost, _ok(cost.shape), 1.0, 1.0, [(0, 0), (0, 6)])
    assert res["accumulated"][0].tolist() == pytest.approx([0, 1, 2, 3, 2, 1, 0])
    assert res["nearest"][0].tolist()[:3] == [0, 0, 0]
    assert res["nearest"][0].tolist()[4:] == [1, 1, 1]
    assert res["nearest"][0, 3] == 0  # a tie goes to the destination listed first


def test_the_nearer_destination_in_cost_is_not_the_nearer_in_metres():
    cost = np.array([[1.0, 1.0, 1.0, 1.0, 9.0, 9.0]])
    res = solve(cost, _ok(cost.shape), 1.0, 1.0, [(0, 0), (0, 5)])
    # Cell 3 is 3 cells from the first and 2 from the second, but the second lies across costly ground.
    assert res["nearest"][0, 3] == 0
    assert res["accumulated"][0, 3] == pytest.approx(3)


# 4, 5, 6. walls, a gap, an enclosed cell


def _walled(gap):
    cost = np.ones((5, 5))
    passable = _ok(cost.shape)
    passable[:, 2] = False  # a wall down the middle column
    if gap is not None:
        passable[gap, 2] = True
    return cost, passable


def test_a_wall_with_a_one_cell_gap_routes_through_the_gap():
    cost, passable = _walled(gap=0)
    acc = solve(cost, passable, 1.0, 1.0, [(4, 0)])["accumulated"]
    # From the bottom left to the bottom right: up to the gap at the top and down again.
    assert acc[4, 4] == pytest.approx(_brute(cost, passable, 1.0, 1.0, [(4, 0)])[4, 4])
    assert acc[4, 4] > 4  # longer than straight across


def test_detour_through_the_gap_has_the_hand_computed_cost():
    cost, passable = _walled(gap=0)
    acc = solve(cost, passable, 1.0, 1.0, [(4, 0)])["accumulated"]
    # Up to the gap: (4,0) (3,1) (2,1) (1,1) (0,2), one diagonal, two axial steps and a diagonal past the
    # corner of the wall (one side open, so the default rule allows it), then the mirror image down.
    assert acc[4, 4] == pytest.approx(2 * (2 * R2 + 2))


def test_a_wall_without_a_gap_leaves_the_far_side_unreachable_not_huge():
    cost, passable = _walled(gap=None)
    res = solve(cost, passable, 1.0, 1.0, [(4, 0)])
    assert np.isinf(res["accumulated"][:, 3:]).all()
    assert (res["status"][:, 3:] == UNREACHABLE).all()
    assert (res["status"][:, 2] == BARRIER).all()
    assert (res["nearest"][:, 3:] == -1).all()


def test_an_enclosed_cell_is_unreachable():
    cost = np.ones((5, 5))
    passable = _ok(cost.shape)
    passable[1:4, 1:4] = False
    passable[2, 2] = True
    res = solve(cost, passable, 1.0, 1.0, [(0, 0)])
    assert res["status"][2, 2] == UNREACHABLE and np.isinf(res["accumulated"][2, 2])
    assert (res["status"] == REACHED).sum() == 16


# 7. NoData


def test_nodata_blocks_like_a_barrier_and_keeps_its_own_status():
    cost = np.ones((3, 3))
    nodata = np.zeros((3, 3), bool)
    nodata[:, 1] = True
    res = solve(cost, ~nodata, 1.0, 1.0, [(0, 0)], nodata=nodata)
    assert (res["status"][:, 1] == NODATA).all()
    assert (res["status"][:, 2] == UNREACHABLE).all()  # not crossed as if it were free ground


# 8. corner cutting


def test_a_diagonal_between_two_barriers_is_closed_by_default():
    # S X
    # X T
    cost = np.ones((2, 2))
    passable = np.array([[True, False], [False, True]])
    assert solve(cost, passable, 1.0, 1.0, [(0, 0)])["status"][1, 1] == UNREACHABLE
    assert solve(cost, passable, 1.0, 1.0, [(0, 0)], corner="either")["status"][1, 1] == UNREACHABLE
    allowed = solve(cost, passable, 1.0, 1.0, [(0, 0)], corner="allow")["accumulated"]
    assert allowed[1, 1] == pytest.approx(R2)


def test_a_diagonal_past_one_barrier_corner_depends_on_the_rule():
    # S X
    # . T
    cost = np.ones((2, 2))
    passable = np.array([[True, False], [True, True]])
    assert solve(cost, passable, 1.0, 1.0, [(0, 0)])["accumulated"][1, 1] == pytest.approx(R2)
    assert solve(cost, passable, 1.0, 1.0, [(0, 0)], corner="either")["accumulated"][1, 1] == pytest.approx(2)


def test_a_one_cell_wide_diagonal_wall_does_not_leak():
    # A barrier line drawn cell by cell along a diagonal: 8-connected, with no axial gap.
    cost = np.ones((6, 6))
    passable = ~np.eye(6, dtype=bool)
    res = solve(cost, passable, 1.0, 1.0, [(5, 0)])
    assert (res["status"][np.triu_indices(6, 1)] == UNREACHABLE).all()
    leak = solve(cost, passable, 1.0, 1.0, [(5, 0)], corner="allow")
    assert (leak["status"][np.triu_indices(6, 1)] == REACHED).all()


# 10. heterogeneous cost


def test_a_longer_cheap_route_beats_a_short_costly_one():
    cost = np.ones((5, 7))
    cost[1:, 3] = 50.0  # a costly band across the middle, open only along the top row
    res = solve(cost, _ok(cost.shape), 1.0, 1.0, [(4, 0)])
    acc = res["accumulated"]
    straight = 2 * 1 + 2 * (1 + 50) / 2 + 2 * 1  # (4,0) -> (4,6) along the bottom row, through the band
    # Round the band through (0,3): three diagonals and one axial step up, the same down.
    assert acc[4, 6] == pytest.approx(6 * R2 + 2)
    assert acc[4, 6] < straight
    assert res["accumulated"][4, 6] > 6  # more than the straight line in metres x the cheapest cost


@pytest.mark.parametrize("seed", range(6))
@pytest.mark.parametrize("corner", ["both", "either", "allow"])
def test_matches_brute_force_relaxation_on_random_grids(seed, corner):
    rng = np.random.default_rng(seed)
    cost = rng.uniform(0.2, 5.0, size=(7, 8))
    passable = rng.random((7, 8)) > 0.25
    sources = [tuple(map(int, rc)) for rc in np.argwhere(passable)[:2]]
    dx, dy = 3.0, 7.0
    got = solve(cost, passable, dx, dy, sources, corner=corner)["accumulated"]
    want = _brute(cost, passable, dx, dy, sources, corner=corner)
    assert np.allclose(np.where(np.isinf(want), -1, want), np.where(np.isinf(got), -1, got))


def test_status_counts_add_up_to_every_cell():
    rng = np.random.default_rng(9)
    passable = rng.random((10, 10)) > 0.3
    nodata = ~passable & (rng.random((10, 10)) > 0.5)
    src = tuple(map(int, np.argwhere(passable)[0]))
    res = solve(np.ones((10, 10)), passable, 1.0, 1.0, [src], nodata=nodata)
    counts = {s: int((res["status"] == s).sum()) for s in (REACHED, UNREACHABLE, BARRIER, NODATA)}
    assert sum(counts.values()) == 100
    assert counts[NODATA] == int(nodata.sum())


def test_a_destination_on_a_barrier_stops():
    passable = np.array([[True, False]])
    with pytest.raises(SystemExit):
        solve(np.ones((1, 2)), passable, 1.0, 1.0, [(0, 1)])


def test_two_destinations_in_one_cell_stop():
    with pytest.raises(SystemExit):
        solve(np.ones((2, 2)), _ok((2, 2)), 1.0, 1.0, [(0, 0), (0, 0)])


# CRS and the grid


def _profile(crs, transform, h=4, w=5):
    return {"crs": rasterio.crs.CRS.from_user_input(crs), "transform": transform, "height": h, "width": w}


def test_geographic_crs_stops():
    with pytest.raises(SystemExit, match="geographic"):
        grid_metres(**_profile("EPSG:4326", Affine(0.001, 0, 139.7, 0, -0.001, 35.7)))


def test_web_mercator_away_from_the_equator_stops():
    with pytest.raises(SystemExit, match="scale"):
        grid_metres(**_profile("EPSG:3857", Affine(100, 0, 15_550_000, 0, -100, 4_260_000)))  # about 35.7 N


def test_utm_passes_and_reports_the_pixel_size_in_metres():
    g = grid_metres(**_profile("EPSG:32654", Affine(30, 0, 380_000, 0, -10, 3_950_000)))
    assert (g["dx"], g["dy"]) == (30, 10)
    assert abs(g["scale_error"]) < 0.001


def test_a_crs_in_us_survey_feet_is_converted_to_metres():
    g = grid_metres(**_profile("EPSG:2263", Affine(100, 0, 980_000, 0, -100, 200_000)))  # New York, ftUS
    assert g["dx"] == pytest.approx(100 * 1200 / 3937)


def test_a_rotated_grid_stops():
    with pytest.raises(SystemExit, match="rotat"):
        grid_metres(**_profile("EPSG:32654", Affine(30, 5, 380_000, 0, -30, 3_950_000)))


def test_a_raster_without_crs_stops():
    with pytest.raises(SystemExit, match="CRS"):
        grid_metres(crs=None, transform=Affine(1, 0, 0, 0, -1, 0), height=2, width=2)


# The command line, on a small GeoTIFF


def _write(path, a, transform, crs="EPSG:32654", nodata=None):
    with rasterio.open(path, "w", driver="GTiff", height=a.shape[0], width=a.shape[1], count=1,
                       dtype="float64", crs=crs, transform=transform, nodata=nodata) as ds:
        ds.write(a, 1)


def _cli(tmp_path, cost, rows, *args, transform=None, nodata=None):
    t = transform or Affine(10, 0, 380_000, 0, -30, 3_950_000)
    _write(tmp_path / "cost.tif", cost, t, nodata=nodata)
    with open(tmp_path / "dest.csv", "w", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["id", "x", "y"])
        for did, r, c in rows:
            wr.writerow([did, t.c + (c + 0.5) * t.a, t.f + (r + 0.5) * t.e])
    return subprocess.run([sys.executable, str(Path(__file__).with_name("cost_distance.py")), str(tmp_path / "cost.tif"),
                           str(tmp_path / "dest.csv"), "--cost-unit", "s/m", "--out", str(tmp_path / "out.tif"), *args],
                          capture_output=True, text=True)


def test_cli_writes_cost_nearest_and_status_bands(tmp_path):
    cost = np.ones((3, 4))
    cost[0, 3] = -9999
    out = _cli(tmp_path, cost, [("west", 1, 0), ("east", 1, 3)], nodata=-9999)
    assert out.returncode == 0, out.stderr
    with rasterio.open(tmp_path / "out.tif") as ds:
        acc, nearest, status = ds.read(1), ds.read(2), ds.read(3)
        assert ds.descriptions == ("accumulated_cost_s", "nearest_destination", "status")
    assert acc[1, 1] == pytest.approx(10)  # 10 m wide pixels at 1 s/m
    assert acc[0, 0] == pytest.approx(30)  # 30 m tall
    assert np.isnan(acc[0, 3]) and status[0, 3] == NODATA and nearest[0, 3] == -1
    assert nearest[1, 3] == 1
    with open(tmp_path / "out.destinations.csv") as f:
        assert [r["id"] for r in csv.DictReader(f)] == ["west", "east"]
    assert "cells 12: reached 11, unreachable 0, barrier 0, nodata 1" in out.stdout


def test_cli_stops_on_a_destination_outside_the_raster(tmp_path):
    out = _cli(tmp_path, np.ones((2, 2)), [("far", 5, 5)])
    assert out.returncode != 0 and "outside the raster" in out.stderr


def test_cli_stops_on_zero_or_negative_cost(tmp_path):
    cost = np.ones((2, 2))
    cost[0, 1] = 0
    out = _cli(tmp_path, cost, [("a", 0, 0)])
    assert out.returncode != 0 and "1 cells" in out.stderr


def test_cli_barrier_value_and_nodata_stop_policy(tmp_path):
    cost = np.ones((3, 3))
    cost[:, 1] = 999
    out = _cli(tmp_path, cost, [("a", 0, 0)], "--barrier-value", "999")
    assert out.returncode == 0, out.stderr
    assert "barrier 3" in out.stdout and "unreachable 3" in out.stdout
    cost[0, 2] = -1
    out = _cli(tmp_path, cost, [("a", 0, 0)], "--barrier-value", "999", "--nodata", "stop", nodata=-1)
    assert out.returncode != 0 and "NoData" in out.stderr


# 16 neighbours (knight's moves)

def test_a_knights_move_by_hand():
    from cost_distance import solve

    # 3 rows x 2 cols, 1 m pixels. From (0, 0) to (2, 1): the segment runs a quarter of sqrt(5) m in each of
    # (0, 0), (1, 0), (1, 1), (2, 1).
    cost = np.array([[1.0, 9.0], [2.0, 3.0], [9.0, 4.0]])
    acc = solve(cost, np.ones((3, 2), bool), 1.0, 1.0, [(0, 0)], neighbours=16)["accumulated"]
    knight = np.sqrt(5) * (1 + 2 + 3 + 4) / 4
    other = 1.0 * (1 + 2) / 2 + np.sqrt(2) * (2 + 4) / 2  # down, then diagonal
    assert knight < other and acc[2, 1] == pytest.approx(knight)


def test_a_knights_move_is_not_taken_across_a_barrier():
    from cost_distance import solve

    cost = np.ones((3, 2))
    passable = np.ones((3, 2), bool)
    passable[1, 1] = False  # one of the two cells between
    acc = solve(cost, passable, 1.0, 1.0, [(0, 0)], neighbours=16)["accumulated"]
    assert acc[2, 1] == pytest.approx(1 + np.sqrt(2))  # down, then diagonal; never the knight's line


def test_sixteen_neighbours_bring_paths_closer_to_straight_lines():
    from cost_distance import solve

    n = 101
    worst = {}
    for k in (8, 16):
        acc = solve(np.ones((n, n)), np.ones((n, n), bool), 1.0, 1.0, [(50, 50)], neighbours=k)["accumulated"]
        r, c = np.indices((n, n))
        d = np.hypot(r - 50, c - 50)
        ratio = acc[d > 20] / d[d > 20]
        worst[k] = ratio.max()
    assert worst[8] == pytest.approx(1.0824, abs=2e-3)
    assert worst[16] < 1.03  # measured below
