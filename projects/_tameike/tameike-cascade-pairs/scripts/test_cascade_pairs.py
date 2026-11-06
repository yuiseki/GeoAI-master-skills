"""uvx --python 3.12 --with pyflwdir --with numpy --with rasterio --with pyproj --with scipy --with pytest pytest -q scripts/test_cascade_pairs.py"""

import numpy as np
import pytest
from rasterio.transform import from_origin

from cascade_pairs import assign_nodes, cumulative, cumulative_within, downstream_nodes, fill_holes, top_only_in_cum

TR = from_origin(320000, 3950000, 5, 5)


def valley_with_ponds(h=60, w=31):
    """A valley falling south (0.5 m per row) with sides rising 1 m per cell. Two ponds on the floor masked as NaN
    (upper rows 10-15, lower rows 35-40, columns 13-17), as DEM5A masks water, and a third pond in a side valley
    that drains to the east edge."""
    r, c = np.indices((h, w))
    cc = w // 2
    z = 100 + np.abs(c - cc) * 1.0 + (h - 1 - r) * 0.5
    z[10:16, cc - 2:cc + 3] = np.nan
    z[35:41, cc - 2:cc + 3] = np.nan
    return z


def test_holes_are_filled_level_at_the_rim_minimum_and_edge_holes_stay():
    z = valley_with_ponds()
    z[0, 0:3] = np.nan                              # touches the edge: sea or missing tile
    filled, labels = fill_holes(z)
    lake = filled[10:16, 13:18]
    assert np.ptp(lake) == 0
    rim = np.concatenate([z[9, 12:19], z[16, 12:19], z[10:16, 12], z[10:16, 18]])
    assert lake[0, 0] == np.nanmin(rim)
    assert np.isnan(filled[0, 0:3]).all() and labels[0, 0] == 0
    assert len(np.unique(labels[labels > 0])) == 2


def test_points_join_the_hole_they_fall_in_or_near_else_a_3x3_footprint():
    z = valley_with_ponds()
    _, labels = fill_holes(z)
    rows = np.array([12, 41, 50])                   # in the upper hole, one cell below the lower hole, far from both
    cols = np.array([15, 15, 3])
    nodes, node_of_point, how = assign_nodes(labels, rows, cols, max_cells=6)
    assert how.tolist() == ["hole", "hole", "point"]
    assert node_of_point[0] != node_of_point[1] != node_of_point[2]
    assert (nodes == node_of_point[2]).sum() == 9
    assert (nodes == node_of_point[0]).sum() == 30   # the whole 6 x 5 hole


def test_two_points_in_one_hole_share_a_node():
    z = valley_with_ponds()
    _, labels = fill_holes(z)
    _, node_of_point, _ = assign_nodes(labels, np.array([11, 14]), np.array([14, 16]), max_cells=6)
    assert node_of_point[0] == node_of_point[1]


def test_the_upper_pond_drains_into_the_lower_and_the_lower_leaves_the_area():
    from hydro import flow
    z = valley_with_ponds()
    filled, labels = fill_holes(z)
    nodes, node_of_point, _ = assign_nodes(labels, np.array([12, 37, 50]), np.array([15, 15, 3]), max_cells=6)
    _, _, fd = flow(np.where(np.isnan(filled), -9999, filled), TR)
    down = downstream_nodes(nodes, fd)
    up, low, side = node_of_point
    assert down[up] == low
    assert down[low] is None                        # leaves through the bottom edge
    assert down[side] in (None, low)                # a valley-side point flows down to the floor, maybe through the lower lake


def test_cumulative_storage_adds_everything_upstream():
    down = {1: 2, 2: 3, 3: None, 4: 3, 5: None}
    own = {1: 10.0, 2: 1.0, 3: 0.5, 4: 2.0, 5: 7.0}
    cum = cumulative(down, own)
    assert cum == {1: 10.0, 2: 11.0, 3: 13.5, 4: 2.0, 5: 7.0}


def test_top_only_in_cum_finds_the_small_pond_below_the_large_one():
    own = {1: 100.0, 2: 1.0, 3: 50.0, 4: 40.0, 5: 30.0, 6: 20.0, 7: 10.0, 8: 5.0, 9: 3.0, 10: 2.0}
    cum = dict(own)
    cum[2] = 101.0                                  # pond 2 sits below pond 1
    assert top_only_in_cum(own, cum, 0.2) == [2]    # top 2 by cum: 2 and 1; by own: 1 and 3
    assert top_only_in_cum(own, own, 0.2) == []


def test_cycles_are_refused():
    with pytest.raises(ValueError, match="cycle"):
        cumulative({1: 2, 2: 1}, {1: 1.0, 2: 1.0})


def test_flow_length_between_ponds():
    from hydro import flow
    z = valley_with_ponds()
    filled, labels = fill_holes(z)
    nodes, (up, low), _ = assign_nodes(labels, np.array([12, 37]), np.array([15, 15]), max_cells=6)
    _, _, fd = flow(np.where(np.isnan(filled), -9999, filled), TR)
    lengths = {}
    downstream_nodes(nodes, fd, lengths=lengths, cell=5.0)
    # outlet on the upper lake's bottom row (15) to the lower lake's top row (35): 20 steps down the floor; the
    # outlet may sit off the centre column, so a step or two may be diagonal (5 sqrt 2 m)
    assert 20 * 5.0 <= lengths[up] <= 18 * 5.0 + 2 * 5.0 * 2 ** 0.5 + 1e-9


def test_cumulative_within_drops_ponds_beyond_the_distance():
    down = {1: 2, 2: 3, 3: None}
    own = {1: 10.0, 2: 1.0, 3: 0.5}
    lengths = {1: 800.0, 2: 300.0}
    assert cumulative_within(down, own, lengths, 1000) == {1: 10.0, 2: 11.0, 3: 1.5}   # 1 is 1,100 m above 3
    assert cumulative_within(down, own, lengths, 2000) == cumulative(down, own)


def test_a_pond_on_nodata_does_not_follow_a_negative_index():
    from hydro import flow
    z = valley_with_ponds()
    filled, labels = fill_holes(z)
    filled[50:53, 2:5] = np.nan                      # a NoData patch with a point pond on it
    nodes, (up, low, odd), _ = assign_nodes(labels, np.array([12, 37, 51]), np.array([15, 15, 3]), max_cells=6)
    _, _, fd = flow(np.where(np.isnan(filled), -9999, filled), TR)
    nodes[-1, -1] = 99                               # if -1 were followed as an index, it would land here
    down = downstream_nodes(nodes, fd)
    assert down[odd] is None
