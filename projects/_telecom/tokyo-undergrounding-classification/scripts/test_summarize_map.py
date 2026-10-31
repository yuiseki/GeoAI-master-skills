# uvx --with pytest pytest scripts/test_summarize_map.py
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("summarize_map", Path(__file__).with_name("summarize_map.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_drawn_cells_are_the_classes_and_the_total_adds_nodata():
    assert module.summarize({"units_per_class": [5, 2, 1], "nodata_units": 3}) == {
        "cells_drawn": 8, "cells_nodata": 3, "cells_total": 11}
