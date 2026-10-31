# uvx --from 'duckdb>=1.5.5' --with pytest --with numpy --with pandas --with pyarrow --with shapely --with rasterio --with matplotlib pytest scripts/test_04_layers_gif.py -q
import importlib
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
g = importlib.import_module("04_layers_gif")


def test_visible_is_cumulative():
    assert g.visible(0) == ("listed",)
    assert g.visible(len(g.SEQUENCE) - 1) == g.SEQUENCE
    with pytest.raises(IndexError):
        g.visible(len(g.SEQUENCE))


def test_burn_max_keeps_the_deeper_rank_where_polygons_overlap():
    grid = np.zeros((1, 3), np.uint8)
    out = g.burn_max({4: np.array([[True, True, False]]), 2: np.array([[False, True, True]])}, grid)
    assert out.tolist() == [[4, 4, 2]]


def test_road_class_folds_links():
    assert g.road_class("trunk_link") == "trunk" and g.road_class("tertiary") == "tertiary"


def test_no_elevation_layer():
    src = Path(g.__file__).read_text(encoding="utf-8")
    assert "dem" not in src.lower().replace("demo", "")
