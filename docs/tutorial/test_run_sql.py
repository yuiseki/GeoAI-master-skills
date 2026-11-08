"""uvx --python 3.12 --with 'duckdb>=1.5.5' --with pytest pytest -q test_run_sql.py"""

# Tests for run_sql.py: run a file of SQL statements with DuckDB and print the result of the last one.
# The script runs `install httpfs` first; that is a no-op when the extension is already installed locally.

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent / "run_sql.py"


def run(tmp_path, sql, name="q.sql"):
    f = tmp_path / name
    f.write_text(sql, encoding="utf-8")
    return subprocess.run([sys.executable, str(SCRIPT), str(f)], capture_output=True, text=True, cwd=tmp_path)


def test_statements_run_in_order_and_only_the_last_result_is_printed(tmp_path):
    r = run(tmp_path, "create table t as select 1 as a;\ninsert into t values (2), (40);\n"
                      "select 'first' as marker;\nselect sum(a) as total from t;\n")
    assert r.returncode == 0, r.stderr
    assert "total" in r.stdout and "43" in r.stdout
    assert "first" not in r.stdout


def test_a_file_written_by_one_statement_is_read_by_the_next(tmp_path):
    # the tutorial's wdi_2022.sql copies a table to parquet, then counts rows of that parquet
    r = run(tmp_path, "copy (select range as i from range(5)) to 'x.parquet' (format parquet);\n"
                      "select count(*) as n, max(i) as top from 'x.parquet';\n")
    assert r.returncode == 0, r.stderr
    assert (tmp_path / "x.parquet").exists()
    lines = r.stdout.split("\n")
    assert any(line.split() == ["│", "5", "│", "4", "│"] for line in lines), r.stdout


def test_the_last_statement_may_end_without_a_semicolon(tmp_path):
    r = run(tmp_path, "select 7 * 6 as answer")
    assert r.returncode == 0, r.stderr
    assert "42" in r.stdout


def test_a_file_with_no_statements_prints_nothing(tmp_path):
    r = run(tmp_path, "\n  \n")
    assert r.returncode == 0, r.stderr
    assert r.stdout == ""


def test_a_bad_statement_fails_loudly(tmp_path):
    r = run(tmp_path, "select 1;\nselect * from no_such_table;\nselect 2;\n")
    assert r.returncode != 0
    assert "no_such_table" in r.stderr


def test_no_file_argument_fails():
    r = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True)
    assert r.returncode != 0


def test_a_missing_file_fails(tmp_path):
    r = subprocess.run([sys.executable, str(SCRIPT), str(tmp_path / "nope.sql")], capture_output=True, text=True)
    assert r.returncode != 0
    assert "nope.sql" in r.stderr


@pytest.mark.xfail(strict=True, reason="BUG: a trailing comment after the last statement becomes its own "
                                       "'statement'; duckdb.sql returns None for it and the script prints nothing")
def test_a_comment_after_the_last_statement_does_not_hide_its_result(tmp_path):
    r = run(tmp_path, "select 42 as answer;\n-- end of file\n")
    assert r.returncode == 0, r.stderr
    assert "42" in r.stdout


@pytest.mark.xfail(strict=True, reason="BUG: the file is split on every ';\\n', even inside a string literal, "
                                       "so a valid statement is cut in two")
def test_a_semicolon_and_newline_inside_a_string_is_not_a_statement_break(tmp_path):
    r = run(tmp_path, "select 'a;\nb' as s;\n")
    assert r.returncode == 0, r.stderr
    assert "a;" in r.stdout
