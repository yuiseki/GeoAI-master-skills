"""uvx --with numpy --with scipy --with rasterio --with duckdb --with pytest pytest test_point_pattern.py"""

import math

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from point_pattern import Baseline, pair_counts, pattern_test


def write_raster(path, data, west=130.0, north=40.0, res=0.1, nodata=-99999.0):
    with rasterio.open(path, "w", driver="GTiff", width=data.shape[1], height=data.shape[0],
                       count=1, dtype="float32", crs="EPSG:4326", nodata=nodata,
                       transform=from_origin(west, north, res, res)) as dst:
        dst.write(data.astype("float32"), 1)


@pytest.fixture
def population(tmp_path):
    # A 40 x 40 grid of 0.1-degree cells; people live mostly in two "cities".
    rng = np.random.default_rng(0)
    data = rng.uniform(0, 1, size=(40, 40))
    data[5:9, 5:9] += 400
    data[28:32, 25:29] += 200
    path = tmp_path / "pop.tif"
    write_raster(path, data)
    return path


def test_pair_counts_use_great_circle_distance():
    # Two points 1 degree of longitude apart at 60N: about 55.6 km.
    lon, lat = np.array([0.0, 1.0]), np.array([60.0, 60.0])
    assert pair_counts(lon, lat, [50.0, 60.0]).tolist() == [0, 1]


def test_points_drawn_like_the_baseline_are_not_clustered(population):
    base = Baseline(population, weights="values")
    rng = np.random.default_rng(1)
    lon, lat = base.sample(500, rng)
    r = pattern_test(lon, lat, base, radii=[5, 10, 20], simulations=99, seed=2)
    for row in r["radii"]:
        assert row["low"] <= row["observed"] <= row["high"]


def test_population_like_points_look_clustered_against_an_even_baseline(population):
    people = Baseline(population, weights="values")
    even = Baseline(population, weights="area")
    lon, lat = people.sample(500, np.random.default_rng(3))
    vs_even = pattern_test(lon, lat, even, radii=[10], simulations=99, seed=4)["radii"][0]
    vs_people = pattern_test(lon, lat, people, radii=[10], simulations=99, seed=4)["radii"][0]
    assert vs_even["observed"] > vs_even["high"]
    assert vs_even["ratio"] > 3
    assert vs_people["low"] <= vs_people["observed"] <= vs_people["high"]


def test_area_weights_spread_points_by_area_not_by_cell(tmp_path):
    # Cells from the equator to 80N: a cell at 75N has about a quarter of the area of one at 0N.
    data = np.ones((80, 10))
    path = tmp_path / "ones.tif"
    write_raster(path, data, west=0.0, north=80.0, res=1.0)
    base = Baseline(path, weights="area")
    _, lat = base.sample(200_000, np.random.default_rng(5))
    north_share = float(np.mean(lat > 40))
    area_share = (math.sin(math.radians(80)) - math.sin(math.radians(40))) / math.sin(math.radians(80))
    assert north_share == pytest.approx(area_share, abs=0.01)


def test_points_outside_the_baseline_are_counted(population):
    base = Baseline(population, weights="values")
    lon = np.array([130.55, 135.0, 150.0])  # the last two are outside the raster
    lat = np.array([39.35, 50.0, 10.0])
    assert base.outside(lon, lat) == 2
