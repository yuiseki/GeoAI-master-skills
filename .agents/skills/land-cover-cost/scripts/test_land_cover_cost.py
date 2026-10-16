"""uvx --with numpy --with rasterio --with pytest pytest test_land_cover_cost.py"""

import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import Affine

from land_cover_cost import convert, read_mapping

T = Affine(10, 0, 380_000, 0, -10, 3_950_000)
MAPPING = "class,status,cost_per_m,source,note\n1,passable,0.5,example,grass\n2,passable,0.8,example,forest\n3,barrier,,example,water\n"


def _raster(path, a, nodata=255, transform=T, crs="EPSG:32654", dtype="uint8", **kw):
    with rasterio.open(path, "w", driver="GTiff", height=a.shape[0], width=a.shape[1], count=1, dtype=dtype,
                       crs=crs, transform=transform, nodata=nodata, **kw) as ds:
        ds.write(a.astype(dtype), 1)
    return path


def _mapping(path, text=MAPPING):
    path.write_text(text)
    return path


def _run(tmp_path, a, text=MAPPING, *args, **kw):
    lc = _raster(tmp_path / "lc.tif", a, **kw)
    mp = _mapping(tmp_path / "map.csv", text)
    out = tmp_path / "cost.tif"
    audit = convert(str(lc), str(mp), str(out), "s/m", *args)
    with rasterio.open(out) as ds:
        return ds.read(1), ds, audit


A = np.array([[1, 2, 3], [255, 1, 2]])


# 1. class -> cost


def test_each_class_gets_its_cost_per_metre(tmp_path):
    cost, _, _ = _run(tmp_path, A)
    assert cost[0, 0] == 0.5 and cost[0, 1] == 0.8 and cost[1, 1] == 0.5 and cost[1, 2] == 0.8


# 2. barrier, 3. NoData


def test_barrier_cells_take_the_barrier_value_and_nodata_stays_nodata(tmp_path):
    cost, ds, audit = _run(tmp_path, A)
    assert cost[0, 2] == -1  # barrier
    assert np.isnan(cost[1, 0]) and math.isnan(ds.nodata)  # input NoData -> NoData (NaN)
    assert audit["barrier_value"] == -1


def test_the_barrier_value_can_be_changed_but_not_to_a_cost(tmp_path):
    cost, _, audit = _run(tmp_path, A, MAPPING, "inf")
    assert cost[0, 2] == np.inf and audit["barrier_value"] == "inf"
    for bad in ("0.5", "nan"):
        with pytest.raises(SystemExit):
            _run(tmp_path, A, MAPPING, bad)


def test_a_raster_without_nodata_has_no_nodata_cells(tmp_path):
    cost, _, audit = _run(tmp_path, np.array([[1, 3]]), nodata=None)
    assert audit["cells"]["nodata"] == 0 and not np.isnan(cost).any()


def test_a_mapped_class_equal_to_the_nodata_value_stops(tmp_path):
    with pytest.raises(SystemExit, match="NoData"):
        _run(tmp_path, A, MAPPING + "255,passable,1,example,\n")


# 4, 5, 6. the mapping table


def test_an_unmapped_class_stops_before_anything_is_written(tmp_path):
    with pytest.raises(SystemExit, match="7"):
        _run(tmp_path, np.array([[1, 7, 7]]))
    assert not (tmp_path / "cost.tif").exists()


def test_a_class_listed_twice_stops(tmp_path):
    with pytest.raises(SystemExit, match="more than once"):
        read_mapping(_mapping(tmp_path / "m.csv", MAPPING + "2,passable,0.9,example,forest again\n"))


@pytest.mark.parametrize("cost", ["0", "-0.5", "nan", "inf", "-inf", "", "fast"])
def test_a_passable_class_needs_a_positive_finite_cost(tmp_path, cost):
    with pytest.raises(SystemExit):
        read_mapping(_mapping(tmp_path / "m.csv", f"class,status,cost_per_m\n1,passable,{cost}\n"))


@pytest.mark.parametrize("row", ["3,barrier,0.5", "1,closed,0.5", "1.5,passable,0.5", "x,passable,0.5"])
def test_other_bad_rows_stop(tmp_path, row):
    # A barrier with a cost is ambiguous; the status has two values; classes are integers.
    with pytest.raises(SystemExit):
        read_mapping(_mapping(tmp_path / "m.csv", f"class,status,cost_per_m\n{row}\n"))


def test_a_missing_column_stops(tmp_path):
    with pytest.raises(SystemExit, match="cost_per_m"):
        read_mapping(_mapping(tmp_path / "m.csv", "class,status\n1,passable\n"))


def test_a_float_raster_is_not_categorical(tmp_path):
    with pytest.raises(SystemExit, match="integer"):
        _run(tmp_path, A, dtype="float32")


# 7. the grid, 8. the counts


def test_the_grid_is_unchanged(tmp_path):
    _, ds, _ = _run(tmp_path, A, transform=Affine(10, 0, 380_000, 0, -30, 3_950_000))
    with rasterio.open(tmp_path / "lc.tif") as src:
        assert (ds.crs, ds.transform, ds.width, ds.height, ds.res) == (src.crs, src.transform, src.width,
                                                                       src.height, src.res)
    assert ds.res == (10, 30)


def test_counts_by_class_and_by_status_add_up(tmp_path):
    rng = np.random.default_rng(0)
    a = rng.choice([1, 2, 3, 255], size=(300, 500), p=[0.4, 0.3, 0.2, 0.1])
    # Tiled in blocks of 256, so the counts come from several blocks.
    _, _, audit = _run(tmp_path, a, tiled=True, blockxsize=256, blockysize=256)
    by_class = {c["class"]: c["cells"] for c in audit["classes"]}
    for k in (1, 2, 3):
        assert by_class[k] == int((a == k).sum())
    cells = audit["cells"]
    assert cells["nodata"] == int((a == 255).sum())
    assert cells["passable"] == by_class[1] + by_class[2] and cells["barrier"] == by_class[3]
    assert cells["passable"] + cells["barrier"] + cells["nodata"] == cells["total"] == a.size


def test_a_mapped_class_absent_from_the_raster_is_counted_as_zero(tmp_path):
    _, _, audit = _run(tmp_path, np.array([[1, 1]]))
    assert {c["class"]: c["cells"] for c in audit["classes"]} == {1: 2, 2: 0, 3: 0}


def test_output_cells_match_the_counts(tmp_path):
    cost, _, audit = _run(tmp_path, A)
    assert int(np.isnan(cost).sum()) == audit["cells"]["nodata"]
    assert int((cost == -1).sum()) == audit["cells"]["barrier"]
    assert int((cost > 0).sum()) == audit["cells"]["passable"]


# the audit and the command line


def test_audit_records_inputs_hash_unit_and_output(tmp_path):
    _, _, audit = _run(tmp_path, A)
    assert audit["mapping_sha256"] == hashlib.sha256((tmp_path / "map.csv").read_bytes()).hexdigest()
    assert audit["cost_unit"] == "s/m"
    assert audit["input"].endswith("lc.tif") and audit["output"].endswith("cost.tif")
    assert audit["mapping"].endswith("map.csv")
    assert {c["class"]: c["note"] for c in audit["classes"]}[2] == "forest"
    assert audit["grid"]["width"] == 3 and audit["grid"]["height"] == 2


def test_cli_writes_the_audit_json_and_refuses_to_overwrite(tmp_path):
    lc = _raster(tmp_path / "lc.tif", A)
    mp = _mapping(tmp_path / "map.csv")
    cmd = [sys.executable, str(Path(__file__).with_name("land_cover_cost.py")), str(lc), str(mp),
           "--cost-unit", "s/m", "--out", str(tmp_path / "cost.tif")]
    out = subprocess.run(cmd, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    audit = json.loads((tmp_path / "cost.audit.json").read_text())
    assert audit["cells"] == {"total": 6, "passable": 4, "barrier": 1, "nodata": 1}
    assert "passable 4, barrier 1, nodata 1" in out.stdout
    again = subprocess.run(cmd, capture_output=True, text=True)
    assert again.returncode != 0 and "exists" in again.stderr


def test_cli_needs_a_cost_per_metre_unit(tmp_path):
    lc = _raster(tmp_path / "lc.tif", A)
    mp = _mapping(tmp_path / "map.csv")
    out = subprocess.run([sys.executable, str(Path(__file__).with_name("land_cover_cost.py")), str(lc), str(mp),
                          "--cost-unit", "km/h", "--out", str(tmp_path / "cost.tif")], capture_output=True, text=True)
    assert out.returncode != 0 and "/m" in out.stderr
