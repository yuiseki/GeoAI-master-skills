"""uvx --python 3.12 --with pytest pytest -q -p no:cacheprovider test_compare.py"""

# B0 and B1 of compare.py on hand-made chain tables (the same three chains in every box).
import csv

import pytest

import compare as cp

FIELDS = ["start_source_rows", "start_names", "stop", "overflowed_source_rows", "overflowed_names", "overflowed",
          "people_chain", "end_at_edge"]
OLD = [["1", "上池", "pond", "1|2", "上池|下池", "2", "5", "False"],
       ["3", "山池", "flow leaves the area or reaches no pond", "3", "山池", "1", "0", "True"],
       ["4", "谷池", "pond", "4", "谷池", "1", "2", "False"]]
NEW = [["1", "上池", "pond", "1|2", "上池|下池", "2", "5", "False"],
       ["3", "山池", "pond", "3|5", "山池|里池", "2", "3", "True"],
       ["4", "谷池", "pond", "4|6", "谷池|川池", "2", "1.0", "False"],
       ["7", "新池", "pond", "", "", "0", "0", "False"]]


def write(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


@pytest.fixture
def out(tmp_path, monkeypatch):
    new, old = tmp_path / "wide", tmp_path / "breach"
    new.mkdir()
    old.mkdir()
    for box in ("kagawa", "fukuyama", "awaji"):
        write(old / f"{box}_chains.csv", FIELDS, OLD)
        write(new / f"{box}_chains.csv", FIELDS, NEW)
    boxes = ("kagawa", "fukuyama", "awaji")
    write(new / "summary.csv", ["box", "chains_2plus_people"], [[b, n] for b in boxes for n in (3, 4)])
    write(old / "summary.csv", ["box", "chains_2plus_people"], [[b, n] for b in boxes for n in (1, 2)])
    monkeypatch.setattr(cp, "OUT", new)
    monkeypatch.setattr(cp, "BREACH", old)
    cp.main()
    return new


def test_b0_pairs_starts_and_checks_only_chains_that_stayed_inside(out):
    b0 = cp.load(out / "b0.csv")
    assert len(b0) == 3
    assert b0[0] == dict(box="kagawa", starts_old="3", starts_new="4", starts_in_both="3", starts_only_new="1",
                         starts_only_old="0", checked="2", same="1", same_share="0.5")
    diffs = cp.load(out / "b0_differences.csv")
    assert [(d["box"], d["start_source_rows"], d["new_overflowed"]) for d in diffs] == [
        (b, "4", "谷池|川池") for b in ("kagawa", "fukuyama", "awaji")]


def test_b1_chains_of_two_or_more_with_people(out):
    b1 = cp.load(out / "b1.csv")[1]
    assert b1["box"] == "fukuyama"
    assert (b1["chains_2plus_people_old"], b1["chains_2plus_people_new"]) == ("1", "3")
    assert (b1["old_ending_at_edge"], b1["new_ending_at_edge"], b1["new_ending_at_edge_share"]) == ("0", "1", "0.333")
    assert (b1["max_overflowed_old"], b1["max_overflowed_new"]) == ("2", "2")
    assert (b1["old_chains_longer_now"], b1["old_chains_shorter_now"]) == ("2", "0")
    assert (b1["variants_min_new"], b1["variants_max_new"], b1["variants_min_old"], b1["variants_max_old"]) == ("3", "4", "1", "2")
