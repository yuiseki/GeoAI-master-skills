import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("bench", Path(__file__).with_name("benchmark.py"))
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)


def test_matching_detects_missing_and_score_changes():
    a = [{"view": "a", "query": "pole", "box": [0, 0, 10, 10], "score": .5}]
    b = [{"view": "a", "query": "pole", "box": [0, 0, 10, 10], "score": .51}]
    result = bench.compare(a, b)
    assert result["matched"] == 1
    assert result["max_score_difference"] > .009
    assert bench.compare(a, [])['missing'] == 1
    assert bench.compare([], b)['extra'] == 1


def test_matching_does_not_cross_queries():
    a = [{"view": "a", "query": "pole", "box": [0, 0, 10, 10], "score": .5}]
    b = [{"view": "a", "query": "tree", "box": [0, 0, 10, 10], "score": .5}]
    result = bench.compare(a, b)
    assert result["missing"] == result["extra"] == 1
