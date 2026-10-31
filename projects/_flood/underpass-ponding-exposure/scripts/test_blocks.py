import importlib.util
from pathlib import Path

import numpy as np

spec = importlib.util.spec_from_file_location("blocks", Path(__file__).with_name("05_blocks.py"))
blocks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(blocks)


def test_auc():
    assert blocks.auc([3, 2, 1, 0], [1, 1, 0, 0]) == 1.0
    assert blocks.auc([0, 1, 2, 3], [1, 1, 0, 0]) == 0.0
    assert blocks.auc([1, 1, 1, 1], [1, 0, 1, 0]) == 0.5
    assert blocks.auc([1, 2], [0, 0]) is None


def test_top_set_ties_by_id():
    s = np.array([5, 5, 5, 1, 0, 0, 0, 0, 0, 0])
    assert blocks.top_set(s, np.arange(10), 0.2) == {0, 1}


def test_overlap():
    a = np.arange(10, 0, -1)
    assert blocks.overlap(a, a, np.arange(10), 0.2) == (1.0, 1.0)
    assert blocks.overlap(a, -a, np.arange(10), 0.2) == (0.0, 0.0)
