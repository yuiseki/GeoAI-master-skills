"""uvx --python 3.12 --with numpy --with pandas --with pytest pytest -q -p no:cacheprovider test_coverage.py"""

# season_rows, counts and rule_table of coverage.py on a two-site acquisition table.
import pandas as pd
import pytest

import coverage as cv


def acq():
    rows = []
    # site A: summer 1999 (serves t = 2000) and spring 2000, both T1 with 200 valid pixels
    rows += [("A", 1999, "summer", "T1", 200, True), ("A", 2000, "spring", "T1", 200, True)]
    # site A: spring 2000 again on T2 with 40 pixels; a dropped acquisition; a summer of 2008 (t = 2009: out of range)
    rows += [("A", 2000, "spring", "T2", 40, True), ("A", 2000, "spring", "T1", 300, False), ("A", 2008, "summer", "T1", 300, True)]
    # site B: only a spring of 1995 with 100 pixels
    rows += [("B", 1995, "spring", "T1", 100, True)]
    return pd.DataFrame(rows, columns=["ID", "year", "season", "tier", "n_valid", "kept_for_site_date"])


SITES = pd.DataFrame({"ID": ["A", "B"]})


def test_season_rows_shift_summer_to_the_next_target_year():
    a = cv.season_rows(acq())
    assert len(a) == 4                                             # dropped and t = 2009 rows are out
    assert a[(a.season == "summer")].t.tolist() == [2000] and set(a.window) == {"prev_summer", "current_spring"}


def test_counts_fill_every_site_year_window():
    c = cv.counts(cv.season_rows(acq()), SITES, ["T1", "T2"], 32)
    assert len(c) == 2 * len(cv.TARGETS) * 2
    assert c[("A", 2000, "current_spring")] == 2 and c[("A", 2000, "prev_summer")] == 1 and c[("A", 1991, "prev_summer")] == 0
    assert cv.counts(cv.season_rows(acq()), SITES, ["T1"], 157)[("A", 2000, "current_spring")] == 1


def test_rule_table_shares_and_dev_confirm_split():
    t = {(r["tiers"], r["min_valid"], r["min_scenes"]): r for r in cv.rule_table(cv.season_rows(acq()), SITES)}
    n = 2 * len(cv.TARGETS)                                        # site x t rows
    r = t[("T1", 1, 1)]
    assert r["rows_all_four"] == 1 and r["rows_all_four_confirm"] == 1 and r["rows_all_four_dev"] == 0
    assert r["share_rows_all_four"] == pytest.approx(1 / n)
    assert r["share_current_spring"] == pytest.approx(2 / n) and r["share_prev_summer"] == pytest.approx(1 / n)
    assert r["sites_with_5_years_both_windows"] == 0
    assert t[("T1+T2", 1, 2)]["share_current_spring"] == pytest.approx(1 / n)   # two springs only with T2
    assert t[("T1", 157, 1)]["rows_all_four"] == 1 and t[("T1", 157, 1)]["share_current_spring"] == pytest.approx(1 / n)
    assert len(t) == len(cv.TIERS) * len(cv.MIN_VALID) * len(cv.MIN_SCENES)
