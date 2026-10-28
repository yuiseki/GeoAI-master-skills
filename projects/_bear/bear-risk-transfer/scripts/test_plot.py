# uvx --with numpy --with matplotlib --with pandas --with pytest python -m pytest -q projects/_bear/bear-risk-transfer/scripts/test_plot.py
import json

import pytest

import plot


def test_explored_reads_the_maps_in_order(tmp_path):
    json.dump({"maps": {"AK": {"capture@0.05": 0.1}, "H1": {"capture@0.05": 0.4}}}, open(tmp_path / "gifu_e3.json", "w"))
    assert plot.explored(tmp_path, ["gifu"], ["H1", "AK"]) == {"gifu": [0.4, 0.1]}


def test_explored_refuses_a_missing_map(tmp_path):
    json.dump({"maps": {"AK": {"capture@0.05": 0.1}}}, open(tmp_path / "gifu_e3.json", "w"))
    with pytest.raises(SystemExit):
        plot.explored(tmp_path, ["gifu"], ["AK", "H1"])
