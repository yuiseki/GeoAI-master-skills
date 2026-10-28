"""Tests for build_table_gifu: reading the Gifu month text and filling the municipality x month grid."""

import datetime as dt

import duckdb
import pytest

from build_table_gifu import calendar_month, monthly_table, parse_month


@pytest.mark.parametrize(
    "text, expected",
    [("０４月", 4), ("１１月", 11), ("4月", 4), ("12月", 12), ("３月", 3), (" ９月 ", 9),
     ("6", 6), ("６", 6), ("11", 11), ("１０", 10)],  # FY2019-2022 files also have a bare number without 月
)
def test_parse_month_reads_full_and_half_width_digits(text, expected):
    assert parse_month(text) == expected


@pytest.mark.parametrize("text", [None, "", "不明", "13月", "0月", "月", "13", "0", "１０時"])
def test_parse_month_returns_none_when_it_cannot_read_a_month(text):
    assert parse_month(text) is None


def test_calendar_month_puts_january_to_march_in_the_next_calendar_year():
    assert calendar_month(2014, 4) == dt.date(2014, 4, 1)
    assert calendar_month(2014, 12) == dt.date(2014, 12, 1)
    assert calendar_month(2014, 1) == dt.date(2015, 1, 1)
    assert calendar_month(2014, 3) == dt.date(2015, 3, 1)


def test_monthly_table_fills_zeros_counts_and_reports_rows_outside():
    con = duckdb.connect()
    con.execute("CREATE TABLE sighting (fy INT, month_start DATE, code5 VARCHAR)")
    rows = [
        (2014, dt.date(2014, 4, 1), "21201"),
        (2014, dt.date(2014, 4, 1), "21201"),
        (2014, dt.date(2014, 5, 1), "21202"),
        (2013, dt.date(2013, 12, 1), "21201"),  # before the first month
    ]
    con.executemany("INSERT INTO sighting VALUES (?,?,?)", rows)
    con.execute("CREATE TABLE munis (code5 VARCHAR, name VARCHAR)")
    con.executemany("INSERT INTO munis VALUES (?,?)", [("21201", "岐阜市"), ("21202", "大垣市")])
    out = monthly_table(con, dt.date(2014, 4, 1), dt.date(2014, 5, 1))
    got = {(r[0], r[1]): r[2] for r in out}
    assert len(out) == 4
    assert got[("21201", dt.date(2014, 4, 1))] == 2
    assert got[("21202", dt.date(2014, 4, 1))] == 0
    assert got[("21202", dt.date(2014, 5, 1))] == 1
    assert monthly_table.last_outside == 1


def test_monthly_table_stops_on_a_first_month_that_is_not_the_first_of_a_month():
    con = duckdb.connect()
    con.execute("CREATE TABLE sighting (fy INT, month_start DATE, code5 VARCHAR)")
    con.execute("CREATE TABLE munis (code5 VARCHAR, name VARCHAR)")
    with pytest.raises(ValueError):
        monthly_table(con, dt.date(2014, 4, 2), dt.date(2014, 5, 1))
