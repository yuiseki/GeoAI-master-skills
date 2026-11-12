"""uvx --with numpy --with pytest pytest test_surface_material.py"""

# Tests for surface_material.py without the image model: classes from prompt similarities, and the agreement
# table against a reference label (OpenStreetMap's surface, as carried by Overture's road segments).

import numpy as np
import pytest

from surface_material import CLASSES, PROMPTS, agreement, classify, osm_class


def test_every_class_has_prompts_and_softmax_picks_the_highest():
    assert set(PROMPTS) == set(CLASSES)
    sims = np.zeros((2, sum(len(v) for v in PROMPTS.values())))
    names = [c for c in CLASSES for _ in PROMPTS[c]]
    sims[0, names.index("sett")] = 0.4            # one prompt of sett far above the rest
    sims[1, names.index("asphalt")] = 0.3
    labels, probs = classify(sims, names)
    assert labels == ["sett", "asphalt"]
    assert probs.shape == (2, len(CLASSES)) and np.allclose(probs.sum(axis=1), 1)


def test_osm_surface_values_map_to_classes():
    assert osm_class("asphalt") == "asphalt"
    assert osm_class("paving_stones") == "sett" and osm_class("cobblestone") == "sett" and osm_class("sett") == "sett"
    assert osm_class("concrete:plates") == "concrete"
    assert osm_class("gravel") == "unpaved" and osm_class("dirt") == "unpaved"
    assert osm_class("paved") is None and osm_class(None) is None      # too vague to grade a class


def test_agreement_counts_only_labelled_rows():
    t = agreement(["asphalt", "sett", "asphalt", "unpaved"], ["asphalt", "asphalt", None, "unpaved"])
    assert t["labelled"] == 3 and t["agree"] == 2 and t["accuracy"] == pytest.approx(2 / 3)
    assert t["confusion"]["asphalt"]["sett"] == 1
