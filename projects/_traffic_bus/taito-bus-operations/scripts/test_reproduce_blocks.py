# uvx --with pytest pytest scripts/test_reproduce_blocks.py
import importlib.util
from pathlib import Path
from types import SimpleNamespace

SPEC = importlib.util.spec_from_file_location("reproduce_blocks", Path(__file__).with_name("reproduce_blocks.py"))
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_intervals_include_every_trip_once():
    trips = SimpleNamespace(start=[100, 300, 200], end=[150, 350, 250])
    rows = MODULE.intervals(trips, [[0, 1], [2]])
    assert len(rows) == 3
    assert rows[0] == {"group": "車両1", "start": 100, "end": 150, "kind": "運行"}
    assert rows[-1]["group"] == "車両2"


def test_intervals_reject_duplicate_trip():
    trips = SimpleNamespace(start=[100], end=[150])
    try:
        MODULE.intervals(trips, [[0], [0]])
    except ValueError as error:
        assert "duplicate" in str(error)
    else:
        raise AssertionError("duplicate trip was accepted")
