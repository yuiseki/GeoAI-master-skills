"""uvx --with numpy --with duckdb --with shapely --with matplotlib --with pyarrow --with pandas --with pytest pytest test_network_map.py"""

import json
import os
import subprocess
import sys
from pathlib import Path

import duckdb
import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import network_map as nm  # noqa: E402


def grid_edges(tmp_path, values):
    """A 3 x 3 street grid in metres (12 edges), with the given value per edge (None = no value)."""
    rows = []
    k = 0
    for i in range(3):
        for j in range(2):
            rows.append((k, f"LINESTRING({j * 100} {i * 100}, {(j + 1) * 100} {i * 100})"))
            k += 1
            rows.append((k, f"LINESTRING({i * 100} {j * 100}, {i * 100} {(j + 1) * 100})"))
            k += 1
    assert len(rows) == len(values) == 12
    c = duckdb.connect()
    c.execute("install spatial; load spatial")
    c.execute("create table e (id int, wkt varchar, v double, br boolean, name varchar)")
    for (i, w), v in zip(rows, values):
        c.execute("insert into e values (?, ?, ?, ?, ?)", [i, w, v, i == 0, "橋A" if i == 0 else None])
    p = tmp_path / "edges.parquet"
    c.execute(f"copy (select id, v, br, name, st_geomfromtext(wkt) geometry from e) to '{p}' (format parquet)")
    return p


def run(args):
    return subprocess.run([sys.executable, str(HERE / "network_map.py"), *map(str, args)], capture_output=True,
                          text=True)


def base_args(edges, png):
    return [edges, "--crs", "EPSG:6677", "--source", "合成", "--question", "どの辺を多く通るか",
            "--value", "v", "--value-label", "通る点の数", "--unit", "点", "--bins", 1, 10, 100, "--png", png]


def test_counts_every_edge_by_class_and_nodata(tmp_path):
    vals = [0, 0.5, 1, 5, 10, 50, 100, None, None, 3, 0, 7]
    e = grid_edges(tmp_path, vals)
    r = run(base_args(e, tmp_path / "m.png"))
    assert r.returncode == 0, r.stderr
    meta = json.loads((tmp_path / "m.json").read_text(encoding="utf-8"))
    # classes are (0, 1], (1, 10], (10, 100]; 0 is drawn as the base network, None as no data
    assert meta["counts"] == {"zero": 2, "nodata": 2, "classes": [2, 4, 2]}
    assert meta["edges"] == 12 and sum(meta["counts"]["classes"]) + 2 + 2 == 12
    assert (tmp_path / "m.png").stat().st_size > 1000


def test_value_above_last_bin_stops(tmp_path):
    e = grid_edges(tmp_path, [1] * 11 + [101])
    r = run(base_args(e, tmp_path / "m.png"))
    assert r.returncode != 0 and "above the last bin" in r.stderr


def test_negative_value_stops(tmp_path):
    e = grid_edges(tmp_path, [1] * 11 + [-1])
    r = run(base_args(e, tmp_path / "m.png"))
    assert r.returncode != 0 and "negative" in r.stderr


def test_palette_must_rise_against_the_background():
    # on a dark background the high class must be the light end; YlOrRd ends dark
    assert nm.palette_contrast_ok("magma", "dark")
    assert not nm.palette_contrast_ok("YlOrRd", "dark")
    assert nm.palette_contrast_ok("YlOrRd", "light")
    assert not nm.palette_contrast_ok("magma", "light")  # its high end is pale yellow
    assert nm.palette_contrast_ok("magma_r", "light")


def test_wrong_palette_for_theme_stops(tmp_path):
    e = grid_edges(tmp_path, [1] * 12)
    r = run(base_args(e, tmp_path / "m.png") + ["--theme", "dark", "--palette", "YlOrRd"])
    assert r.returncode != 0 and "background" in r.stderr


def test_widths_grow_with_class():
    w = nm.class_widths(4, (0.5, 3.0))
    assert w[0] == pytest.approx(0.5) and w[-1] == pytest.approx(3.0) and all(a < b for a, b in zip(w, w[1:]))


def test_highlight_labels_and_points_are_recorded(tmp_path):
    e = grid_edges(tmp_path, [5] * 12)
    pts = tmp_path / "pts.csv"
    pts.write_text("x,y\n0,0\n200,200\n", encoding="utf-8")
    r = run(base_args(e, tmp_path / "m.png") + ["--highlight", "br", "--highlight-label", "外すと伸びる橋",
                                                "--label-col", "name", "--points", f"{pts},避難場所,^,#1f6fb2",
                                                "--theme", "dark"])
    assert r.returncode == 0, r.stderr
    meta = json.loads((tmp_path / "m.json").read_text(encoding="utf-8"))
    assert meta["highlighted"] == 1 and meta["labels"] == ["橋A"]
    assert meta["points"] == [{"label": "避難場所", "path": str(pts), "n": 2}]
    assert meta["theme"] == "dark" and meta["palette"] == "magma"
    assert "text_overlaps" in meta


def test_geographic_crs_sets_aspect(tmp_path):
    e = grid_edges(tmp_path, [5] * 12)
    assert nm.aspect("EPSG:4326", 35, 36) > 1.2
    assert nm.aspect("EPSG:6677", 0, 100) == 1.0


def test_point_overlaps_checks_each_point_not_the_layer_box():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    fig, ax = plt.subplots()
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    pts = np.array([[5.0, 5.0], [95.0, 95.0]])
    ax.scatter(pts[:, 0], pts[:, 1])
    t_on = ax.text(5, 5, "on")      # sits on the first point
    t_off = ax.text(50, 50, "off")  # inside the layer's bounding box, but far from both points
    found = nm.point_overlaps(fig, ax, [t_on, t_off], [("pts", pts)])
    plt.close(fig)
    assert found == [("on", "pts")]


def test_label_moves_off_a_point(tmp_path):
    e = grid_edges(tmp_path, [5] * 12)
    pts = tmp_path / "pts.csv"
    # edge 0 runs (0,0)-(100,0); its label sits up and to the right of (50, 0) by default
    pts.write_text("x,y\n54,3\n", encoding="utf-8")
    args = base_args(e, tmp_path / "m.png") + ["--highlight", "br", "--label-col", "name",
                                               "--points", f"{pts},点,o,#1f6fb2"]
    r = run(args)
    assert r.returncode == 0, r.stderr
    meta = json.loads((tmp_path / "m.json").read_text(encoding="utf-8"))
    assert meta["text_overlaps"] == []
    # with only the default offset, the same label overlaps the point (the test can fail)
    src = (HERE / "network_map.py").read_text(encoding="utf-8").replace(
        "LABEL_OFFSETS = [(5, 5), (-5, 5),", "LABEL_OFFSETS = [(5, 5)] or [(-5, 5),")
    one = tmp_path / "network_map_one.py"
    one.write_text(src, encoding="utf-8")
    r = subprocess.run([sys.executable, str(one), *map(str, args)], capture_output=True, text=True,
                       env={**os.environ, "PYTHONPATH": str(HERE)})
    assert r.returncode == 0, r.stderr
    meta = json.loads((tmp_path / "m.json").read_text(encoding="utf-8"))
    assert meta["text_overlaps"] == [["橋A", "点"]]
