"""uvx --with numpy --with duckdb --with pytest pytest test_series_breaks.py"""

import numpy as np

from series_breaks import aggregate_breaks, find_breaks


def smooth(n_series=6, length=40, seed=0):
    rng = np.random.default_rng(seed)
    t = np.arange(length)
    return np.array([100 * np.exp(0.02 * t + rng.normal(scale=0.01, size=length)) * (1 + i) for i in range(n_series)])


def test_smooth_series_have_no_breaks():
    v = smooth()
    assert find_breaks([f"s{i}" for i in range(len(v))], np.arange(v.shape[1]), v) == []


def test_a_level_shift_in_one_series_is_found_at_its_time():
    v = smooth()
    v[2, 25:] *= 1.3
    found = find_breaks([f"s{i}" for i in range(len(v))], np.arange(v.shape[1]), v)
    assert [(k, int(t)) for k, t, _ in found] == [("s2", 25)]
    assert abs(found[0][2] - np.log(1.3)) < 0.05


def test_a_noisy_series_is_judged_against_its_own_spread():
    rng = np.random.default_rng(1)
    v = smooth()
    v[4] = 100 * np.exp(rng.normal(scale=0.2, size=v.shape[1]))
    assert find_breaks([f"s{i}" for i in range(len(v))], np.arange(v.shape[1]), v) == []


def test_zero_and_missing_values_are_skipped_not_logged():
    v = smooth()
    v[0, 10] = 0.0
    v[1, 5:8] = np.nan
    find_breaks([f"s{i}" for i in range(len(v))], np.arange(v.shape[1]), v)  # must not raise


def test_a_jump_shared_by_every_series_shows_in_the_total_but_not_in_each_series():
    v = smooth()
    v[:, 30:] *= 1.25
    keys = [f"s{i}" for i in range(len(v))]
    t = np.arange(v.shape[1])
    # every series jumps by the same amount, so each is flagged against its own spread
    assert {int(x) for _, x, _ in find_breaks(keys, t, v)} == {30}
    agg = aggregate_breaks(v, t)
    assert [int(x["time"]) for x in agg if x["flag"]] == [30]


def test_a_series_that_starts_late_moves_the_raw_total_but_not_the_like_for_like_total():
    v = smooth()
    v[5, :30] = np.nan  # series 5 enters at t=30
    agg = {int(x["time"]): x for x in aggregate_breaks(v, np.arange(v.shape[1]))}
    assert agg[30]["entering"] == 1
    assert abs(agg[30]["raw_change"]) > 0.05          # the total jumps because a series entered
    assert abs(agg[30]["like_for_like_change"]) < 0.05  # the same series moved smoothly


def test_a_series_that_grows_steadily_fast_is_not_a_break_but_a_jump_in_it_is():
    """Growth of 25% a period is the series' normal change; judged against zero it would be flagged everywhere."""
    t = np.arange(40)
    v = np.array([100 * 1.25 ** t * (1 + 0.001 * np.sin(t * (i + 1))) for i in range(3)])
    keys = ["a", "b", "c"]
    assert find_breaks(keys, t, v) == []
    v[1, 20:] *= 1.5
    assert [(k, int(x)) for k, x, _ in find_breaks(keys, t, v)] == [("b", 20)]


def test_a_jump_between_tiny_values_is_ignored_when_a_minimum_level_is_given():
    v = smooth()
    v[3] = 2.0  # a count series at the level of 2 ...
    v[3, 20:] = 20.0  # ... that jumps tenfold to 20
    keys = [f"s{i}" for i in range(len(v))]
    t = np.arange(v.shape[1])
    assert [(k, int(x)) for k, x, _ in find_breaks(keys, t, v)] == [("s3", 20)]
    assert find_breaks(keys, t, v, min_level=100.0) == []


def test_breaks_that_share_a_period_are_counted_together():
    from series_breaks import breaks_by_time

    v = smooth()
    v[:, 30:] *= 1.25            # all six jump together at 30
    v[1, 12:] *= 1.4             # one series alone at 12
    keys = [f"s{i}" for i in range(len(v))]
    t = np.arange(v.shape[1])
    counts = breaks_by_time(find_breaks(keys, t, v))
    assert counts[30] == 6 and counts[12] == 1


def test_the_change_at_a_series_and_time_can_be_read_from_another_version_of_the_data():
    from series_breaks import change_at

    v = smooth()
    other = v.copy()
    other[2, 25:] *= 1.3         # this version has the jump, the other does not
    v2 = v.copy()
    keys = [f"s{i}" for i in range(len(v))]
    t = np.arange(v.shape[1])
    assert abs(change_at(keys, t, other, "s2", 25) - np.log(1.3)) < 0.05
    assert abs(change_at(keys, t, v2, "s2", 25)) < 0.05
    assert change_at(keys, t, v2, "nope", 25) is None
    assert change_at(keys, t, v2, "s2", 999) is None
