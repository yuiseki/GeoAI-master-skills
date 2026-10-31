import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).with_name("08_map_tokyo23_flood_context.py")
spec = importlib.util.spec_from_file_location("map_tokyo23_flood_context", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_a31a_maximum_scenario_depth_labels():
    assert module.depth_label(1) == "0–0.5 m"
    assert module.depth_label(3) == "3–5 m"
    assert module.depth_label(6) == "20 m以上"


def test_a31a_unknown_class_is_rejected():
    try:
        module.depth_label(7)
    except ValueError as exc:
        assert "unknown A31a maximum-depth class" in str(exc)
    else:
        raise AssertionError("unknown A31a class must not be silently mapped")


def test_historical_flood_points_use_translucent_yellow_circles():
    style = module.historical_marker_style()
    assert style["marker"] == "o"
    assert style["color"] == "#F0E442"
    assert style["edgecolor"] == "#6F6200"
    assert 0 < style["alpha"] < 1
