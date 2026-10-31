import importlib.util
from pathlib import Path

from shapely.geometry import Polygon, mapping, shape

SCRIPT = Path(__file__).with_name("07_map_tokyo23_points.py")
spec = importlib.util.spec_from_file_location("map_tokyo23_points", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_clean_zero_area_interior_rings_preserves_real_holes():
    source = Polygon(
        [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)],
        [
            [(2, 2), (4, 2), (4, 4), (2, 4), (2, 2)],
            [(6, 6), (7, 6), (8, 6), (6, 6)],
        ],
    )
    cleaned = shape(module.remove_zero_area_holes(mapping(source)))
    assert len(cleaned.interiors) == 1
    assert cleaned.interiors[0].area == 0
    assert cleaned.area == 96
