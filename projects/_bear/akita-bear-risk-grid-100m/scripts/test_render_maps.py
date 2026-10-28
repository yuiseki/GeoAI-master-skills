import numpy as np
import pytest

import render_maps as rm
from grid import Grid


def test_percentile_classes_put_the_top_one_percent_in_the_top_class():
    score = np.arange(1000, dtype=float)
    cls = rm.risk_classes(score)
    assert (cls == len(rm.CLASSES) - 1).sum() == 10  # top 1%
    assert (cls == len(rm.CLASSES) - 2).sum() == 40  # 1-5%
    assert cls[score.argmax()] == len(rm.CLASSES) - 1 and cls[score.argmin()] == 0


def test_to_array_places_cells_by_ix_iy_and_leaves_the_rest_empty():
    arr = rm.to_array(np.array([3, 4], dtype=np.int16), np.array([0, 2]), np.array([1, 0]), nx=3, ny=2)
    assert arr[1, 0] == 3 and arr[0, 2] == 4 and (arr == -1).sum() == 4


def test_mercator_sampling_reads_the_cell_under_each_pixel_centre():
    # a 2 x 2 grid in a metric CRS; an identity "projection" stands in for EPSG:3857 -> EPSG:6678
    g = Grid(0, 0, 2, 2, 100)
    arr = np.array([[1, 2], [3, 4]], dtype=np.int16)  # row 0 is the south
    img = rm.sample_to_pixels(arr, g, xs=np.array([50.0, 150.0, 250.0]), ys=np.array([150.0, 50.0]), to_grid=lambda x, y: (x, y))
    # image rows go north to south: first row is y = 150 (grid row 1)
    assert img.tolist() == [[3, 4, -1], [1, 2, -1]]


def test_hillshade_is_brighter_on_a_slope_facing_the_light():
    import web_layers as wl

    # elevation rising to the east (slope faces west) and to the west (faces east); light from the north-west
    east_up = np.tile(np.arange(6) * 20.0, (6, 1))
    west_up = east_up[:, ::-1]
    assert wl.hillshade(east_up, 100.0)[3, 3] > wl.hillshade(west_up, 100.0)[3, 3]


def test_mercator_frame_is_snapped_to_pixel_edges_and_covers_the_grid():
    g = Grid(-97400.0, -125100.0, 50, 40, 100.0)
    xs, ys, (x0, y0, x1, y1), res = rm.mercator_frame(g)
    assert np.isclose(x0 / res, round(x0 / res)) and np.isclose(y1 / res, round(y1 / res))
    assert len(xs) * res == pytest.approx(x1 - x0) and ys[0] > ys[-1]


def test_rank_bytes_encode_the_top_share_in_half_percent_steps_and_zero_outside():
    score = np.arange(400, dtype=float)  # 400 cells
    ix = np.arange(400) % 20
    iy = np.arange(400) // 20
    b = rm.rank_bytes(score, ix, iy, nx=20, ny=21)
    assert b.dtype == np.uint8 and b.shape == (21, 20)
    assert b[iy[score.argmax()], ix[score.argmax()]] == 1  # the top cell: within the top 0.5%
    assert b[iy[score.argmin()], ix[score.argmin()]] == 200  # the bottom cell: the last step
    assert (b[20] == 0).all()  # row 20 has no cell of the prefecture
