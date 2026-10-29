"""Known-answer tests for collecting the held-out differences from B_env."""

import json

import pytest

import added_predictors as ap


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj), encoding="utf-8")


def test_pick_follows_dict_keys_and_list_indices():
    obj = {"a": {"b": [1, {"c": 3}]}}
    assert ap.pick(obj, ("a", "b", 1, "c")) == 3
    with pytest.raises(KeyError):
        ap.pick(obj, ("a", "x"))


def test_triple_reads_dicts_and_lists_the_same_way():
    assert ap.triple({"diff": .1, "lo90": -.2, "hi90": .3}) == (.1, -.2, .3)
    assert ap.triple([.1, -.2, .3]) == (.1, -.2, .3)


def test_rows_read_every_comparison_from_its_output(tmp_path):
    for rel, path, value in [(r.file, r.path, r) for r in ap.COMPARISONS]:
        obj = {}
        node = obj
        for key in path[:-1]:
            node = node.setdefault(key, {})
        node[path[-1]] = [.01, -.02, .03]
        target = tmp_path / rel
        if target.exists():  # several comparisons share one file
            old = json.loads(target.read_text(encoding="utf-8"))
            merge(old, obj)
            obj = old
        write(target, obj)
    rows = ap.rows(tmp_path)
    assert len(rows) == len(ap.COMPARISONS)
    assert all((r["diff"], r["lo90"], r["hi90"]) == (.01, -.02, .03) for r in rows)
    assert {r["role"] for r in rows} <= {"confirmation", "diagnostic"}


def merge(a, b):
    for k, v in b.items():
        if isinstance(v, dict) and isinstance(a.get(k), dict):
            merge(a[k], v)
        else:
            a[k] = v
