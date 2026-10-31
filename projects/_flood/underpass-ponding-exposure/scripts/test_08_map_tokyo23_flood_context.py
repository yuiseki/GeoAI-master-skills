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


def test_map_layer_order_matches_requested_visual_priority():
    z = module.MAP_LAYER_ZORDER
    assert z["underpass"] > z["kansui"] > z["inferred_underpass"] > z["historical_flood"] > z["osm_roads"] > z["a31a"]


def test_gif_switches_the_four_point_layers_in_requested_order():
    assert module.ANIMATION_LAYER_SEQUENCE == (
        "underpass", "kansui", "inferred_underpass", "tokyo_flood_record_points"
    )
    assert module.ANIMATION_LAYER_LABELS == (
        "国交省アンダーパス", "地方整備局冠水想定", "OSMタグアンダーパス推定", "浸水実績"
    )
    assert [module.visible_animation_layers(frame) for frame in range(4)] == [
        ("underpass",),
        ("underpass", "kansui"),
        ("underpass", "kansui", "inferred_underpass"),
        ("underpass", "kansui", "inferred_underpass", "tokyo_flood_record_points"),
    ]


def test_h1_uses_allowed_osm_tags_and_excludes_motorways():
    assert module.is_h1_underpass_road("residential", "yes", None, None)
    assert module.is_h1_underpass_road("primary", None, "yes", None)
    assert module.is_h1_underpass_road("tertiary_link", None, None, "-1")
    assert not module.is_h1_underpass_road("motorway", "yes", None, None)
    assert not module.is_h1_underpass_road("residential", None, None, "0")


def test_h1_lines_are_merged_to_one_representative_point_per_area():
    from shapely.geometry import LineString, box

    records = [
        {"osm_id": 1, "highway": "primary", "tunnel": "yes", "covered": None, "layer": None,
         "line": LineString([(15550000, 4258000), (15550100, 4258000)])},
        {"osm_id": 2, "highway": "residential", "tunnel": None, "covered": "yes", "layer": None,
         "line": LineString([(15550000, 4258008), (15550100, 4258008)])},
    ]
    points, counts = module.build_h1_candidates(records, box(15549900, 4257900, 15550200, 4258100), buffer_ground_m=5)
    assert len(points) == 1
    assert counts == {"qualifying_osm_ways": 2, "buffered_line_parts": 2, "merged_candidate_areas": 1}
