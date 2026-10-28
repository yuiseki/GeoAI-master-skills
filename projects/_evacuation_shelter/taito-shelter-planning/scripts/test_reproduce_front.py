# uvx --with pytest pytest scripts/test_reproduce_front.py
import importlib.util
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("reproduce_front", Path(__file__).with_name("reproduce_front.py"))
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_build_front_preserves_unsupported_and_weak_points():
    points = MODULE.build_front([(10, 0), (12, 1), (20, 2)], {(10, 0), (20, 2), (20, 3)})
    assert len(points) == 4
    assert points[1] == {"x": 1, "y": 12, "methods": ["ε 制約法"]}
    assert points[-1]["front"] is False


def test_build_front_rejects_repeated_flood_rank():
    try:
        MODULE.build_front([(10, 0), (11, 0)], set())
    except ValueError as error:
        assert "rank" in str(error)
    else:
        raise AssertionError("duplicate rank was accepted")
