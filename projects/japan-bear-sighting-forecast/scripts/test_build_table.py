"""Tests for build_table.weekly_table, on a few hand-made rows whose weekly counts are known."""

import datetime as dt

import duckdb
import pytest

from build_table import weekly_table


def make_con(sightings, munis):
    con = duckdb.connect()
    con.execute(
        "CREATE TABLE sighting (id INT, species VARCHAR, info_type VARCHAR, municipality VARCHAR,"
        " observed_at TIMESTAMP, code5 VARCHAR)"
    )
    for r in sightings:
        con.execute("INSERT INTO sighting VALUES (?,?,?,?,?,?)", r)
    con.execute("CREATE TABLE munis (code5 VARCHAR, name VARCHAR)")
    for r in munis:
        con.execute("INSERT INTO munis VALUES (?,?)", r)
    return con


MUNIS = [("05201", "秋田市"), ("05202", "能代市")]
T = dt.datetime


def test_full_grid_with_zeros_and_week_boundaries():
    # Mon 2022-04-11 .. Sun 2022-04-17 is week 1; Mon 04-18 starts week 2.
    rows = [
        (1, "ツキノワグマ", "目撃", "秋田市", T(2022, 4, 11, 0, 0), "05201"),  # Monday 00:00 -> week 1
        (2, "ツキノワグマ", "目撃", "秋田市", T(2022, 4, 17, 23, 59), "05201"),  # Sunday night -> week 1
        (3, "ツキノワグマ", "痕跡(食害)", "秋田市", T(2022, 4, 18, 0, 0), "05201"),  # week 2
        (4, "ニホンジカ", "目撃", "能代市", T(2022, 4, 12, 9, 0), "05202"),  # not a bear
        (5, "ツキノワグマ", "人身被害", "能代市", T(2022, 4, 20, 9, 0), "05202"),  # week 2
    ]
    con = make_con(rows, MUNIS)
    out = weekly_table(con, first_week=dt.date(2022, 4, 11), last_week=dt.date(2022, 4, 18))
    got = {(r[0], r[1]): r[2:] for r in out}
    assert len(out) == 2 * 2  # 2 municipalities x 2 weeks, zeros included
    assert got[("05201", dt.date(2022, 4, 11))][0] == 2
    assert got[("05201", dt.date(2022, 4, 18))][0] == 1
    assert got[("05202", dt.date(2022, 4, 11))][0] == 0  # the deer row is not counted
    assert got[("05202", dt.date(2022, 4, 18))][0] == 1


def test_columns_split_sighting_and_injury():
    rows = [
        (1, "ツキノワグマ", "目撃", "秋田市", T(2022, 4, 11, 1, 0), "05201"),
        (2, "ツキノワグマ", "痕跡(その他)", "秋田市", T(2022, 4, 11, 2, 0), "05201"),
        (3, "ツキノワグマ", "人身被害", "秋田市", T(2022, 4, 11, 3, 0), "05201"),
    ]
    con = make_con(rows, MUNIS)
    out = weekly_table(con, first_week=dt.date(2022, 4, 11), last_week=dt.date(2022, 4, 11))
    r = {x[0]: x for x in out}["05201"]
    # (code5, week_start, bear, bear_sight, injury)
    assert r[2:] == (3, 1, 1)


def test_rows_outside_the_weeks_are_reported_not_dropped_silently():
    rows = [
        (1, "ツキノワグマ", "目撃", "秋田市", T(2022, 4, 10, 14, 0), "05201"),  # before first_week
        (2, "ツキノワグマ", "目撃", "秋田市", T(2022, 4, 12, 14, 0), "05201"),
    ]
    con = make_con(rows, MUNIS)
    out = weekly_table(con, first_week=dt.date(2022, 4, 11), last_week=dt.date(2022, 4, 11))
    assert sum(x[2] for x in out) == 1
    assert weekly_table.last_outside == 1  # the one row we left out is counted


def test_unmatched_code_stops():
    rows = [(1, "ツキノワグマ", "目撃", "秋田市", T(2022, 4, 12, 14, 0), None)]
    con = make_con(rows, MUNIS)
    with pytest.raises(ValueError):
        weekly_table(con, first_week=dt.date(2022, 4, 11), last_week=dt.date(2022, 4, 11))


def test_first_week_must_be_a_monday():
    con = make_con([], MUNIS)
    with pytest.raises(ValueError):
        weekly_table(con, first_week=dt.date(2022, 4, 10), last_week=dt.date(2022, 4, 17))
