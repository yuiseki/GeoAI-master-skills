"""uvx --python 3.12 --with pyflwdir --with numpy --with rasterio --with pyproj --with scipy --with 'duckdb>=1.5.5' --with pytest pytest -q -p no:cacheprovider test_run_breach.py"""

# walk, exposed and rain_200 of run_breach.py, and annual_max of fetch_rain.py.
import csv
import math
import os

for _k in ("GDAL_DATA", "PROJ_LIB", "PROJ_DATA"):    # an anaconda proj.db breaks rasterio's CRS (see the scripts' env -u)
    os.environ.pop(_k, None)

import numpy as np  # noqa: E402
import pytest  # noqa: E402

import fetch_rain  # noqa: E402
import run_breach as rb  # noqa: E402


def test_walk_follows_downstream_and_measures_diagonals():
    # 3 x 3 grid, flat index r * 3 + c: 0 -> 4 (diagonal) -> 5 (east) -> 5 (pit)
    ds = np.array([4, 1, 2, 3, 5, 5, 6, 7, 8])
    assert rb.walk(ds, 0, ncol=3) == [0, 4, 5]
    # stop on reaching a cell of another pond, or after max_m metres (5 m * sqrt 2 = 7.07 >= 7)
    assert rb.walk(ds, 0, stop_cells={4}, ncol=3) == [0, 4]
    assert rb.walk(ds, 0, max_m=7.0, ncol=3) == [0, 4]
    assert rb.walk(ds, 0, max_m=7.1, ncol=3) == [0, 4, 5]


def test_walk_stops_at_nodata():
    ds = np.array([1, -1])
    assert rb.walk(ds, 0, ncol=2) == [0, 1]


def test_exposed_counts_people_within_100m_of_the_path():
    pop = np.ones((60, 60))
    # one cell: the disc of radius 20 cells holds the lattice points with x^2 + y^2 <= 400 (Gauss circle N(20) = 1257)
    assert rb.exposed([30 * 60 + 30], pop, pop.shape) == 1257
    # a path at the edge is cut by the grid
    assert rb.exposed([0], pop, pop.shape) < 1257 / 4 + 21
    # two cells next to each other: one more column of the disc, 41 cells
    assert rb.exposed([30 * 60 + 30, 30 * 60 + 31], pop, pop.shape) == 1257 + 41


def test_rain_200_uses_complete_years_and_the_larger_of_q200_and_observed(tmp_path, monkeypatch):
    rows = [dict(station="s1", name="A", box="kagawa", role="main", year=2000 + i, max_1h_mm=str(v), days_ok=365)
            for i, v in enumerate([20, 25, 30, 22, 28, 35, 40, 26, 31, 24])]
    rows.append(dict(station="s1", name="A", box="kagawa", role="main", year=2010, max_1h_mm="200", days_ok=300))
    rows.append(dict(station="s1", name="A", box="kagawa", role="main", year=2011, max_1h_mm="", days_ok=365))
    with open(tmp_path / "rain_annual_max.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    monkeypatch.setattr(rb, "OUT", tmp_path)
    r = rb.rain_200()["s1"]
    assert r["years"] == 10 and r["observed_max_mm"] == 40.0          # the 300-day year and the blank are out
    assert r["r_design_mm_h"] == round(max(r["r200_mm_h"], 40.0), 1)
    assert r["r200_ge_observed_max"] == (r["r200_mm_h"] >= 40.0)
    assert r["r200_gumbel_mm_h"] > 40.0
    assert (tmp_path / "rain_gumbel.csv").read_text(encoding="utf-8").startswith("station,name,box,role,years")


def test_annual_max_reads_jma_csv_quality_flags(tmp_path):
    head = ["header"] * 6
    body = ["2001/1/1,10.5,8,1", "2001/1/2,30.0,5,1", "2001/1/3,99.0,4,1", "2001/1/4,,8,1", "2002/7/1,0,8,1", "x,1,8,1"]
    p = tmp_path / "rain.csv"
    p.write_bytes("\n".join(head + body).encode("cp932"))
    years = fetch_rain.annual_max(p)
    # quality 4 (not 8 or 5) and a blank value do not count as observed days
    assert years == {2001: {"max_mm": 30.0, "days_ok": 2}, 2002: {"max_mm": 0.0, "days_ok": 1}}
    assert not math.isnan(years[2002]["max_mm"])
