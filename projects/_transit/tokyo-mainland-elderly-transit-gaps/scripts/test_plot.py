"""Map classification must keep unknown cells separate from known zeroes."""

import importlib.util
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("transit_plot", Path(__file__).with_name("plot.py"))
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_classify_distinguishes_no_data_from_no_gap():
    labels, counts, nodata, boundaries = MODULE.classify([0, 1, 250, 500, 1000, 2000, None])
    assert labels == [0, 0, 1, 2, 3, 4, -1]
    assert counts == [2, 1, 1, 1, 1]
    assert nodata == 1
    assert boundaries == [0, 1, 250, 500, 1000, 2000]
