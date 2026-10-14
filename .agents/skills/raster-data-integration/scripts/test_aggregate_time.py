"""uvx --with numpy --with rasterio --with pytest pytest test_aggregate_time.py

Expected values are worked out by hand from month lengths, not with the code under test.
"""

from datetime import datetime, timedelta, timezone

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from aggregate_time import aggregate_period, main, months

UTC = timezone.utc
JST = timezone(timedelta(hours=9))


def stack(values):
    """One pixel per slice: shape (T, 1, 1)."""
    return np.array(values, float)[:, None, None]


def year(y, values):
    starts, ends = months(y)
    return stack(values), starts, ends


def test_months_have_their_own_lengths_and_february_follows_leap_years():
    s, e = months(2023)
    assert [(b - a).days for a, b in zip(s, e)] == [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    s, e = months(2024)
    assert (e[1] - s[1]).days == 29


def test_annual_mean_of_monthly_means_weights_each_month_by_its_days():
    v, s, e = year(2023, [10] * 12)
    v[1] = 38  # a warm February
    r = aggregate_period(v, s, e, "state", s[0], e[-1])
    assert r["value"][0, 0] == pytest.approx((337 * 10 + 28 * 38) / 365)  # 12.148, not the plain mean 12.333
    v, s, e = year(2024, [10] * 12)
    v[1] = 38
    r = aggregate_period(v, s, e, "state", s[0], e[-1])
    assert r["value"][0, 0] == pytest.approx((337 * 10 + 29 * 38) / 366)


def test_accumulations_add_and_a_partial_slice_adds_its_share_of_the_time():
    # January 31 mm (1 mm a day), February 56 mm (2 mm a day). 15 January to 15 February:
    # 17 days of January (17 mm) and 14 days of February (28 mm), assuming the rate is even within a month
    v, s, e = year(2023, [31, 56] + [0] * 10)
    r = aggregate_period(v, s, e, "accumulation", datetime(2023, 1, 15, tzinfo=UTC), datetime(2023, 2, 15, tzinfo=UTC))
    assert r["value"][0, 0] == pytest.approx(17 + 28)
    full = aggregate_period(v, s, e, "accumulation", s[0], e[-1])
    assert full["value"][0, 0] == pytest.approx(87)


def test_a_rate_becomes_an_amount_by_multiplying_by_the_duration():
    # 1 mm/day in January, 2 mm/day in February: 31 + 2 x 28 in 2023, 31 + 2 x 29 in 2024
    for y, total in ((2023, 87), (2024, 89)):
        v, s, e = year(y, [1, 2] + [0] * 10)
        r = aggregate_period(v, s, e, "rate", s[0], s[2])
        assert r["value"][0, 0] == pytest.approx(total)
    r = aggregate_period(v, s, e, "rate", s[0], datetime(y, 1, 11, tzinfo=UTC))
    assert r["value"][0, 0] == pytest.approx(10)  # ten days of January, not the whole month


def test_a_missing_slice_leaves_the_period_incomplete_instead_of_shrinking_it():
    v, s, e = year(2023, [100] * 12)
    v[6] = np.nan  # July is missing (31 days)
    r = aggregate_period(v, s, e, "accumulation", s[0], e[-1])
    assert r["coverage"][0, 0] == pytest.approx(334 / 365)
    assert np.isnan(r["value"][0, 0])  # 1,100 mm would read as a dry year
    r = aggregate_period(v, s, e, "accumulation", s[0], e[-1], min_coverage=0.9)
    assert r["value"][0, 0] == pytest.approx(1100)  # the sum over the covered time, not scaled up


def test_a_gap_between_slices_counts_as_missing_time():
    s, e = months(2023)
    keep = [i for i in range(12) if i != 3]  # no file for April
    r = aggregate_period(stack([5] * 11), [s[i] for i in keep], [e[i] for i in keep], "state", s[0], e[-1])
    assert r["coverage"][0, 0] == pytest.approx(335 / 365)
    assert np.isnan(r["value"][0, 0])


def test_unequal_slices_are_weighted_by_their_length():
    # dekads of 10, 10 and 11 days in a 31-day month: means 0, 0, 31
    t0 = datetime(2023, 1, 1, tzinfo=UTC)
    s = [t0, t0 + timedelta(days=10), t0 + timedelta(days=20)]
    e = [s[1], s[2], t0 + timedelta(days=31)]
    r = aggregate_period(stack([0, 0, 31]), s, e, "state", t0, e[-1])
    assert r["value"][0, 0] == pytest.approx(11)  # 10.333 as a plain mean of the three


def test_a_day_in_utc_is_not_a_day_in_japan():
    # 24 mm on 1 May UTC (even within the day), nothing on 2 May UTC. The Japanese day of 1 May runs from
    # 15:00 UTC on 30 April to 15:00 UTC on 1 May, so it holds 15 of the 24 hours.
    s = [datetime(2023, 5, d, tzinfo=UTC) for d in (1, 2)]
    e = [datetime(2023, 5, d, tzinfo=UTC) for d in (2, 3)]
    p0, p1 = datetime(2023, 5, 1, tzinfo=JST), datetime(2023, 5, 2, tzinfo=JST)
    r = aggregate_period(stack([24, 0]), s, e, "accumulation", p0, p1, min_coverage=0)
    assert r["value"][0, 0] == pytest.approx(15)
    assert r["coverage"][0, 0] == pytest.approx(15 / 24)  # 30 April UTC has no slice


def test_naive_timestamps_are_refused():
    s, e = months(2023)
    with pytest.raises(ValueError):
        aggregate_period(stack([1] * 12), s, e, "state", datetime(2023, 1, 1), e[-1])


def test_nodata_is_per_pixel():
    v = np.array([[[1.0, 2.0]], [[3.0, np.nan]]])  # two slices of 1 x 2 pixels
    t0 = datetime(2023, 1, 1, tzinfo=UTC)
    s, e = [t0, t0 + timedelta(days=1)], [t0 + timedelta(days=1), t0 + timedelta(days=2)]
    r = aggregate_period(v, s, e, "state", t0, e[-1], min_coverage=0.5)
    assert r["value"][0, 0] == pytest.approx(2) and r["value"][0, 1] == pytest.approx(2)
    assert list(r["coverage"][0]) == [1, 0.5]


def test_command_line_reads_slices_from_a_table(tmp_path):
    rows = ["path,start,end"]
    for i, (a, b) in enumerate(zip(*months(2023))):
        p = tmp_path / f"m{i}.tif"
        with rasterio.open(p, "w", driver="GTiff", height=1, width=1, count=1, dtype="float32", crs="EPSG:4326",
                           transform=from_origin(139, 36, 1, 1), nodata=-9999) as d:
            d.write(np.array([[[(b - a).days]]], "float32"))  # 1 mm a day
        rows.append(f"{p},{a.isoformat()},{b.isoformat()}")
    (tmp_path / "slices.csv").write_text("\n".join(rows) + "\n")
    out = tmp_path / "year.tif"
    main([str(tmp_path / "slices.csv"), "--kind", "accumulation", "--start", "2023-01-01T00:00:00+00:00",
          "--end", "2024-01-01T00:00:00+00:00", "--out", str(out)])
    with rasterio.open(out) as d:
        assert d.read(1)[0, 0] == pytest.approx(365)
        assert d.read(2)[0, 0] == pytest.approx(1)
