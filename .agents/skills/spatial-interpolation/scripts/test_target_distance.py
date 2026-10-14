"""uvx --from 'duckdb>=1.5.5' --with numpy --with scipy --with pyproj --with pyarrow --with pytest pytest test_target_distance.py

A 2 km square of observations every 100 m (a regular network), and prediction points placed where the
network has a hole, or between the stations. Distances are worked out from the layout, not from the code.
"""

import duckdb
import numpy as np
import pytest

from evaluate_interpolation import evaluate, read_xy
from interpolate_points import Obs

X0, Y0 = 500000.0, 3950000.0
g = np.arange(0, 2001, 100.0)
GRID = np.array([[X0 + x, Y0 + y] for x in g for y in g])


def field(xy):
    return 0.01 * (xy[:, 0] - X0) + np.sin((xy[:, 1] - Y0) / 300.0) * 20


def hole_network():
    """The grid with a 600 m square hole (700..1300) in the middle; predictions inside the hole."""
    keep = ~((GRID[:, 0] - X0 > 650) & (GRID[:, 0] - X0 < 1350) & (GRID[:, 1] - Y0 > 650) & (GRID[:, 1] - Y0 < 1350))
    o = Obs(GRID[keep], field(GRID[keep]))
    p = np.array([[X0 + x, Y0 + y] for x in range(800, 1201, 100) for y in range(800, 1201, 100)], float)
    return o, p   # prediction points sit 200 to 400 m from the nearest station (stations stop at 600 and 1400)


def median(d):
    return float(np.median(d))


def test_random_is_optimistic_and_target_distance_follows_the_deployment():
    o, p = hole_network()
    rand = evaluate(o, ["nearest"], split="random")
    td = evaluate(o, ["nearest"], split="target-distance", pred_xy=p)
    deploy = median(td["distances"]["deployment"])
    assert deploy == pytest.approx(200, abs=1)                 # 25 points: 200 m x 16, 300 m x 8, 400 m x 1
    assert median(rand["distances"]["validation"]) <= 100       # every held-out station has a neighbour 100 m away
    assert median(td["distances"]["validation"]) == pytest.approx(deploy, rel=0.25)
    assert td["match"]["ok"]


def test_a_large_block_is_pessimistic_and_target_distance_is_closer():
    o = Obs(GRID, field(GRID))
    p = GRID + 50.0                                             # between stations: 70.7 m from the nearest
    blk = evaluate(o, ["nearest"], split="block", block_m=1000)
    td = evaluate(o, ["nearest"], split="target-distance", pred_xy=p)
    deploy = median(td["distances"]["deployment"])
    assert deploy == pytest.approx(50 * 2 ** 0.5, abs=0.5)
    assert median(blk["distances"]["validation"]) > 1.5 * deploy
    assert abs(median(td["distances"]["validation"]) - deploy) < abs(median(blk["distances"]["validation"]) - deploy)


def test_the_split_reads_no_value_at_the_prediction_points(tmp_path):
    o, p = hole_network()
    for name, val in (("a", 1.0), ("b", 999.0)):
        rows = ", ".join(f"('p{i}', {x}, {y}, {val})" for i, (x, y) in enumerate(p))
        duckdb.sql(f"copy (select * from (values {rows}) t(id, x, y, elev)) to '{tmp_path / name}.parquet' (format parquet)")
    pa = read_xy(str(tmp_path / "a.parquet"), "x", "y")          # only coordinates are read
    pb = read_xy(str(tmp_path / "b.parquet"), "x", "y")
    ra = evaluate(o, ["nearest"], split="target-distance", pred_xy=pa)
    rb = evaluate(o, ["nearest"], split="target-distance", pred_xy=pb)
    assert np.array_equal(ra["distances"]["validation"], rb["distances"]["validation"])
    assert ra["nearest"]["all"]["mae"] == rb["nearest"]["all"]["mae"]


def test_a_held_out_point_never_counts_itself_as_its_nearest_training_point():
    o, p = hole_network()
    td = evaluate(o, ["nearest"], split="target-distance", pred_xy=p)
    v = td["distances"]["validation"]
    assert (v >= 100).all()                                     # the closest other station is 100 m away


def test_a_deployment_far_beyond_the_network_is_reported_as_not_reproduced():
    o = Obs(GRID, field(GRID))
    p = np.array([[X0 + 50000, Y0 + 50000], [X0 + 60000, Y0 + 40000]])   # 50 km and more from a 2 km network
    td = evaluate(o, ["nearest", "mean"], split="target-distance", pred_xy=p)
    assert not td["match"]["ok"]
    assert td["match"]["reason"]


def test_the_hull_shares_are_reported_for_both_sides():
    o, p = hole_network()
    td = evaluate(o, ["nearest"], split="target-distance", pred_xy=p)
    assert td["hull"]["deployment_outside"] == 0.0               # the hole is inside the network
    assert 0.0 <= td["hull"]["validation_outside"] <= 1.0


def test_every_method_is_scored_on_the_same_held_out_rows():
    o, p = hole_network()
    td = evaluate(o, ["mean", "nearest", "idw"], split="target-distance", pred_xy=p)
    assert td["mean"]["all"]["n"] == td["nearest"]["all"]["n"] == td["idw"]["all"]["n"]


def test_a_network_coarser_than_the_deployment_is_reported_as_pessimistic_not_hidden():
    # Prediction points 70.7 m from the stations; no held-out station can be nearer than the 100 m spacing.
    o = Obs(GRID, field(GRID))
    td = evaluate(o, ["nearest"], split="target-distance", pred_xy=GRID + 50.0)
    assert not td["match"]["ok"] and td["match"]["direction"] == "longer"
    far = evaluate(o, ["nearest"], split="target-distance", pred_xy=np.array([[X0 + 50000, Y0 + 50000]]))
    assert far["match"]["direction"] == "shorter"           # the network ends 2.8 km out: held-out points stay too near (optimistic)


def test_a_held_out_point_is_not_its_own_neighbour_even_when_the_deployment_distance_is_zero():
    o = Obs(GRID, field(GRID))
    td = evaluate(o, ["nearest"], split="target-distance", pred_xy=GRID.copy())   # predictions on the stations
    assert (td["distances"]["validation"] >= 100).all()
