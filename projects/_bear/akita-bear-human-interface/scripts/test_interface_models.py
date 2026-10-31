"""Known-answer tests for the role subsets of B_env."""

from pathlib import Path

import numpy as np
import pytest

import interface_models as im

ROLES = Path(__file__).resolve().parents[1] / "feature_roles.csv"
STATIC = ["tree", "tree_500", "tree_1500", "crop", "crop_500", "crop_1500", "built", "built_500", "built_1500",
          "grass", "grass_500", "grass_1500", "water", "water_500", "water_1500", "forest_edge", "elev", "slope",
          "tpi_500", "pop_500", "pop_2000", "d_road_major", "d_road", "d_track", "d_river", "d_stream", "d_building",
          "bldg_500"]


def test_the_roles_file_covers_every_static_feature_once():
    roles = im.load_roles(ROLES, STATIC)
    assert sorted(f for fs in roles.values() for f in fs) == sorted(STATIC)
    assert {k: len(v) for k, v in roles.items()} == {"B": 10, "H": 12, "I": 1, "X": 5}
    assert roles["I"] == ["forest_edge"]


def test_load_roles_refuses_a_file_that_misses_or_repeats_a_feature(tmp_path):
    p = tmp_path / "r.csv"
    p.write_text("feature,role,rationale,source\ntree,B,x,y\n", encoding="utf-8")
    with pytest.raises(ValueError):
        im.load_roles(p, ["tree", "elev"])
    p.write_text("feature,role,rationale,source\ntree,B,x,y\ntree,H,x,y\n", encoding="utf-8")
    with pytest.raises(ValueError):
        im.load_roles(p, ["tree"])
    p.write_text("feature,role,rationale,source\ntree,Q,x,y\n", encoding="utf-8")
    with pytest.raises(ValueError):
        im.load_roles(p, ["tree"])


def test_feature_sets_keep_the_static_order_and_build_every_union():
    roles = {"B": ["elev", "tree"], "H": ["pop_500"], "I": ["forest_edge"], "X": ["grass"]}
    order = ["tree", "grass", "forest_edge", "elev", "pop_500"]
    sets = im.feature_sets(roles, order)
    assert sets["M_B"] == ["tree", "elev"]
    assert sets["M_BH"] == ["tree", "elev", "pop_500"]
    assert sets["M_BHI"] == ["tree", "forest_edge", "elev", "pop_500"]
    assert sets["M_I"] == ["forest_edge"]
    assert sets["M_HI"] == ["forest_edge", "pop_500"]
    assert "M_FULL" not in sets  # read from the saved B_env, never refitted here


def test_skill_share_is_the_lift_over_random_relative_to_full():
    assert im.skill_share(0.30, 0.55) == pytest.approx(0.5)
    assert im.skill_share(0.05, 0.55) == pytest.approx(0.0)
    assert im.skill_share(0.55, 0.55) == pytest.approx(1.0)


def test_shapley_of_three_groups_sums_to_the_full_lift_and_is_symmetric():
    # v(S) = 0.05 + 0.1*[B] + 0.2*[H] + 0.04*[B and H]: the B-H synergy splits evenly, I adds nothing
    def v(s):
        return 0.05 + 0.1 * ("B" in s) + 0.2 * ("H" in s) + 0.04 * ("B" in s and "H" in s)
    caps = {k: v(k) for k in ("B", "H", "I", "BH", "BI", "HI", "BHI")}
    phi = im.shapley3(caps, base=0.05)
    assert phi["B"] == pytest.approx(0.12)
    assert phi["H"] == pytest.approx(0.22)
    assert phi["I"] == pytest.approx(0.0)
    assert sum(phi.values()) == pytest.approx(caps["BHI"] - 0.05)


def test_columns_picks_the_named_columns_in_order():
    X = np.arange(12).reshape(3, 4)
    assert im.columns(X, ["a", "b", "c", "d"], ["d", "b"]).tolist() == [[3, 1], [7, 5], [11, 9]]
    with pytest.raises(ValueError):
        im.columns(X, ["a", "b", "c", "d"], ["e"])
