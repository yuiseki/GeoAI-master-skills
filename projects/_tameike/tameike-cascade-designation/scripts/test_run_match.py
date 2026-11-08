"""uvx --python 3.12 --with 'duckdb>=1.5.5' --with pytest pytest -q -p no:cacheprovider test_run_match.py"""

# rows_of and write of run_match.py (ledger reads the remote ledger and is not tested here).
import csv

import run_match as rm


def test_rows_of_splits_ledger_rows():
    assert rm.rows_of("3|10|3") == {3, 10} and rm.rows_of("") == set()


def test_write_uses_the_first_row_for_the_header(tmp_path):
    rm.write(tmp_path / "x.csv", [dict(a=1, b="池"), dict(a=2, b="")])
    with open(tmp_path / "x.csv", encoding="utf-8") as f:
        assert list(csv.DictReader(f)) == [{"a": "1", "b": "池"}, {"a": "2", "b": ""}]
