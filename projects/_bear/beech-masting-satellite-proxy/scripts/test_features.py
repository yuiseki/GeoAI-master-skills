"""Tests for the seasonal values (features.py): windows, the coverage rule, medians, missing stays missing."""

import numpy as np
import pandas as pd

import features as F


def acq(rows):
    cols = ["ID", "year", "season", "tier", "n_valid", "ndvi", "ndmi", "kept_for_site_date"]
    return pd.DataFrame(rows, columns=cols)


RULE = {"tiers": ["T1"], "min_valid": 79, "min_scenes": 1}


def test_previous_summer_serves_the_next_target_year_and_spring_the_same_year():
    a = acq([(5, 1999, "summer", "T1", 300, 0.80, 0.30, True),
             (5, 2000, "spring", "T1", 300, 0.60, 0.20, True)])
    s = F.seasonal(a, RULE).set_index(["ID", "t"])
    assert s.loc[(5, 2000), "ndvi_ps"] == 0.80 and s.loc[(5, 2000), "ndvi_cs"] == 0.60
    assert np.isnan(s.loc[(5, 1999), "ndvi_cs"])


def test_rule_drops_cloudy_tier2_and_duplicate_dates_then_takes_the_median():
    a = acq([(5, 1999, "summer", "T1", 300, 0.80, 0.30, True),
             (5, 1999, "summer", "T1", 290, 0.90, 0.40, True),
             (5, 1999, "summer", "T1", 300, 0.10, 0.10, False),  # the other scene of the same date
             (5, 1999, "summer", "T1", 40, 0.10, 0.10, True),  # too few valid pixels
             (5, 1999, "summer", "T2", 300, 0.10, 0.10, True)])  # tier 2 not in the rule
    s = F.seasonal(a, RULE).set_index(["ID", "t"])
    assert np.isclose(s.loc[(5, 2000), "ndvi_ps"], 0.85) and s.loc[(5, 2000), "n_ps"] == 2


def test_min_scenes_makes_a_season_missing():
    a = acq([(5, 1999, "summer", "T1", 300, 0.80, 0.30, True)])
    s = F.seasonal(a, {**RULE, "min_scenes": 2}).set_index(["ID", "t"])
    assert np.isnan(s.loc[(5, 2000), "ndvi_ps"]) and s.loc[(5, 2000), "n_ps"] == 1


def test_every_site_and_target_year_has_a_row():
    a = acq([(5, 1999, "summer", "T1", 300, 0.80, 0.30, True), (7, 2003, "spring", "T1", 300, 0.5, 0.2, True)])
    s = F.seasonal(a, RULE)
    assert len(s) == 2 * len(F.TARGETS)
