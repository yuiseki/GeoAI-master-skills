"""uvx --python 3.12 --with 'duckdb>=1.5.5' --with pytest pytest -q test_fetch_wiki.py"""

# Tests for fetch_wiki.py: copy only the coordinate and geotag columns of the pinned geotagged Wikipedia shards
# (5 English, 2 Japanese) to data/wiki_coords.parquet. The script reads Hugging Face URLs; here duckdb.connect is
# wrapped so the pinned URL prefix points at shards built in tmp_path, and nothing goes to the network.
# `load httpfs` needs the extension installed locally.

import runpy
from pathlib import Path

import duckdb
import pytest

SCRIPT = Path(__file__).parent / "fetch_wiki.py"
PREFIX = "https://huggingface.co/datasets/yuiseki/wikipedia-geotagged/resolve/24e53f69ef27eb099801ecef1bcca501fcd44a07/"
REAL_CONNECT = duckdb.connect
COLUMNS = ["filename", "id", "qid", "lat", "lon", "gt_type", "gt_globe", "gt_primary", "gt_country"]


class LocalCon:
    def __init__(self, root):
        self.con, self.root = REAL_CONNECT(), root

    def sql(self, q):
        return self.con.sql(q.replace(PREFIX, self.root))


def write_shards(root: Path, missing=None):
    c = REAL_CONNECT()
    shards = [("en", i, 5) for i in range(5)] + [("ja", i, 2) for i in range(2)]
    for k, (lang, i, total) in enumerate(shards):
        p = root / f"20260901.{lang}" / f"train-0000{i}-of-0000{total}.parquet"
        p.parent.mkdir(parents=True, exist_ok=True)
        if p.name == missing and lang == "en":
            continue
        # two articles per shard; the same article id 0 appears in every en shard to show count(distinct id)
        c.sql(f"""copy (select * from (values
            ({0 if lang == 'en' else 100 + k}, 'Q{k}a', 35.0, 139.0, 'city', 'earth', true, 'JP', 'title', 'long text'),
            ({1000 + k}, 'Q{k}b', NULL, NULL, NULL, NULL, false, NULL, 'title', 'long text'))
            t(id, qid, lat, lon, gt_type, gt_globe, gt_primary, gt_country, title, text))
            to '{p}' (format parquet)""")


def run(tmp_path, monkeypatch):
    (tmp_path / "data").mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(duckdb, "connect", lambda *a, **k: LocalCon(str(tmp_path / "hf") + "/"))
    runpy.run_path(str(SCRIPT), run_name="fetch_wiki")


def test_only_coordinate_and_geotag_columns_are_kept(tmp_path, monkeypatch):
    write_shards(tmp_path / "hf")
    run(tmp_path, monkeypatch)
    c = REAL_CONNECT()
    cols = [r[0] for r in c.sql("describe select * from 'data/wiki_coords.parquet'").fetchall()]
    assert cols == COLUMNS


def test_every_row_of_all_seven_shards_is_copied(tmp_path, monkeypatch, capsys):
    write_shards(tmp_path / "hf")
    run(tmp_path, monkeypatch)
    c = REAL_CONNECT()
    assert c.sql("select count(*) from 'data/wiki_coords.parquet'").fetchall() == [(14,)]
    out = capsys.readouterr().out.splitlines()
    # per language: rows, distinct ids, rows with a latitude
    assert sorted(eval(out[-1])) == [("20260901.en", 10, 6, 5), ("20260901.ja", 4, 4, 2)]


def test_a_missing_shard_fails_loudly(tmp_path, monkeypatch):
    write_shards(tmp_path / "hf", missing="train-00003-of-00005.parquet")
    with pytest.raises(duckdb.Error, match="train-00003-of-00005"):
        run(tmp_path, monkeypatch)
    assert not (tmp_path / "data" / "wiki_coords.parquet").exists()
