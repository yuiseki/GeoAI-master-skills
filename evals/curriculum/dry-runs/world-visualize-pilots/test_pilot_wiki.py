"""uvx --python 3.12 --with 'duckdb>=1.5.5' --with pytest pytest -q test_pilot_wiki.py"""

# Tests for pilot_wiki.py: geotagged Wikipedia articles (en, ja) per H3 r4 cell and per country. Runs with
# `python -I` in tmp_path on synthetic data/wiki_coords.parquet and data/wdi.parquet and a pilot.duckdb holding
# table hexcty. The DuckDB h3 extension must already be installed locally.
#
# Cells: A holds (lat 10, lon 10) in AAA; N is one of A's neighbours, in BBB; F holds (lat -30, lon -60) in FFF.

import subprocess
import sys
from pathlib import Path

import duckdb
import pytest

SCRIPT = Path(__file__).parent / "pilot_wiki.py"
EN = "/x/20260901.en/train-00000-of-00005.parquet"
JA = "/x/20260901.ja/train-00000-of-00002.parquet"


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    d = tmp_path_factory.mktemp("wiki")
    (d / "data").mkdir()
    c = duckdb.connect(str(d / "pilot.duckdb"))
    c.sql("load h3")
    a = c.sql("select h3_latlng_to_cell_string(10, 10, 4)").fetchall()[0][0]
    n = sorted(set(c.sql(f"select h3_grid_disk('{a}', 1)").fetchall()[0][0]) - {a})[0]
    f = c.sql("select h3_latlng_to_cell_string(-30, -60, 4)").fetchall()[0][0]
    nlat, nlon = c.sql(f"select h3_cell_to_lat('{n}'), h3_cell_to_lng('{n}')").fetchall()[0]
    c.execute("create table hexcty(h3 varchar, pop double, a3 varchar)")
    c.executemany("insert into hexcty values (?, ?, ?)", [(a, 1e6, "AAA"), (n, 2e6, "BBB"), (f, 3e6, "FFF")])
    c.sql(f"""copy (select * from (values
        ('{EN}', 1, 'Q1', 10.0, 10.0, 'city', 'earth'),
        ('{EN}', 2, 'Q2', 10.0, 10.0, NULL, NULL),          -- no globe given: earth
        ('{EN}', 3, 'Q3', 10.0, 10.0, 'landmark', 'moon'),   -- not on earth
        ('{EN}', 4, 'Q4', 0.0, 0.0, 'landmark', 'earth'),    -- in no populated cell
        ('{EN}', 5, 'Q5', 95.0, 0.0, 'landmark', 'earth'),   -- not a latitude
        ('{JA}', 6, 'Q6', {nlat}, {nlon}, 'landmark', ''))
        t(filename, id, qid, lat, lon, gt_type, gt_globe)) to '{d}/data/wiki_coords.parquet' (format parquet)""")
    c.sql(f"""copy (select * from (values ('AAA', 'NY.GDP.PCAP.CD', 2023, 5000.0))
              t(country_code, indicator_code, year, value)) to '{d}/data/wdi.parquet' (format parquet)""")
    c.close()
    r = subprocess.run([sys.executable, "-I", str(SCRIPT)], cwd=d, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return duckdb.connect(str(d / "pilot.duckdb"), read_only=True), r.stdout, (a, n, f)


def test_language_comes_from_the_shard_path(run):
    c, _, _ = run
    assert sorted(c.sql("select lang, count(*) from wk group by 1").fetchall()) == [("en", 3), ("ja", 1)]


def test_articles_per_cell_and_non_admin_articles(run):
    c, _, (a, n, _) = run
    got = {(lang, h): (k, na) for lang, h, k, na in c.sql("select lang, h3, n, n_nonadmin from wkc").fetchall()}
    # at A: a city (admin) and one without a type (not admin)
    assert got[("en", a)] == (2, 1)
    assert got[("ja", n)] == (1, 1)
    assert len(got) == 3


def test_share_of_articles_outside_populated_cells(run):
    _, out, _ = run
    line = next(l for l in out.splitlines() if "'en'" in l and "'ja'" in l)
    rows = sorted(eval(line))
    # en: 3 articles, 2 in populated cells; ja: 1 of 1
    assert rows == [("en", 3, 2, 0.333), ("ja", 1, 1, 0.0)]


def test_articles_by_country(run):
    c, _, _ = run
    got = {a3: (en, ja, na) for a3, en, ja, na in c.sql("select a3, en, ja, en_na from wkcty").fetchall()}
    assert got == {"AAA": (2, 0, 1), "BBB": (0, 1, 0), "FFF": (0, 0, 0)}
