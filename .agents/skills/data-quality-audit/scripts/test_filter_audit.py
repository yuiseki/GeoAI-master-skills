"""uvx --from 'duckdb>=1.5.5' --with pytest pytest test_filter_audit.py

Worked by hand:
- agreement with a = 2 (both keep), b = 1, c = 1, d = 96 (both drop), n = 100: po = 0.98; each reviewer keeps 3 of
  100, so pe = 0.03 * 0.03 + 0.97 * 0.97 = 0.9418; kappa = (0.98 - 0.9418) / (1 - 0.9418) = 0.6564;
  PABAK = 2 * 0.98 - 1 = 0.96. Agreement is high, kappa is moderate: keeping is rare.
- Wilson 95% interval for 3 of 100: centre (0.03 + 1.96^2 / 200) / (1 + 1.96^2 / 100) = 0.04739, half width
  1.96 * sqrt(0.03 * 0.97 / 100 + 1.96^2 / 40000) / (1 + 1.96^2 / 100) = 0.03713, so 0.0103 to 0.0845.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from filter_audit import agreement, draw_recheck, rescue, seed_status  # noqa: E402


def test_each_seed_is_found_dropped_or_kept():
    before = ["a", "b", "c", "d"]
    after = ["a", "c"]
    assert seed_status(before, after, ["a", "b", "z"]) == [("a", "kept"), ("b", "dropped"), ("z", "not_in_input")]


def test_the_recheck_sample_is_drawn_from_the_dropped_rows_only_and_does_not_depend_on_their_order():
    before = [str(i) for i in range(500)]
    after = [str(i) for i in range(0, 500, 2)]           # the odd ones were dropped
    s = draw_recheck(before, after, n=30, seed=7)
    assert len(s) == 30 and all(int(k) % 2 == 1 for k in s)
    assert s == draw_recheck(list(reversed(before)), after, n=30, seed=7)
    assert s != draw_recheck(before, after, n=30, seed=8)
    # fewer dropped rows than the sample: all of them
    assert draw_recheck(["a", "b", "c"], ["a"], n=30) == ["b", "c"]


def test_the_recheck_sample_has_a_floor():
    with pytest.raises(SystemExit, match="at least 20"):
        draw_recheck([str(i) for i in range(100)], [], n=10)


def test_agreement_reports_counts_kappa_and_pabak():
    first = ["keep"] * 3 + ["drop"] * 97
    second = ["keep", "keep", "drop", "keep"] + ["drop"] * 96
    r = agreement(first, second, positive="keep")
    assert (r["both_positive"], r["first_only"], r["second_only"], r["both_negative"], r["n"]) == (2, 1, 1, 96, 100)
    assert r["observed"] == pytest.approx(0.98)
    assert r["kappa"] == pytest.approx(0.6564, abs=1e-4)
    assert r["pabak"] == pytest.approx(0.96)


def test_kappa_is_undefined_when_both_reviewers_give_one_label():
    r = agreement(["drop"] * 10, ["drop"] * 10, positive="keep")
    assert r["kappa"] is None and r["pabak"] == 1.0


def test_agreement_needs_pairs():
    with pytest.raises(SystemExit, match="pairs"):
        agreement(["keep"], ["keep", "drop"], positive="keep")


def test_rescue_rate_with_an_interval_and_the_count_it_implies_among_all_dropped_rows():
    r = rescue(["keep"] * 3 + ["drop"] * 97, positive="keep", dropped_total=2000)
    assert r["rescued"] == 3 and r["sampled"] == 100
    assert r["share"] == pytest.approx(0.03)
    assert r["share_95"] == pytest.approx([0.0103, 0.0845], abs=1e-4)
    assert r["implied_rescued_95"] == [21, 169]           # 2000 * the interval, rounded


def test_command_line_seeds_sample_and_agree(tmp_path):
    before = tmp_path / "before.csv"
    after = tmp_path / "after.csv"
    before.write_text("id,name,reason\n" + "".join(f"{i},n{i},r{i}\n" for i in range(60)))
    after.write_text("id,name\n" + "".join(f"{i},n{i}\n" for i in range(0, 60, 3)))
    run = lambda *a: subprocess.run([sys.executable, str(HERE / "filter_audit.py"), *map(str, a)],  # noqa: E731
                                    capture_output=True, text=True)
    r = run("seeds", "--before", before, "--after", after, "--key", "id", "--seeds", 0, 3)
    assert r.returncode == 0, r.stdout + r.stderr
    r = run("seeds", "--before", before, "--after", after, "--key", "id", "--seeds", 0, 1, 999)
    assert r.returncode == 1 and "1\tdropped" in r.stdout and "999\tnot_in_input" in r.stdout
    out = tmp_path / "recheck.csv"
    r = run("sample", "--before", before, "--after", after, "--key", "id", "--n", 20, "--seed", 1,
            "--hide", "reason", "--out", out)
    assert r.returncode == 0, r.stderr
    rows = out.read_text().splitlines()
    assert rows[0] == "id,name" and len(rows) == 21          # the earlier reason is not shown to the rechecker
    meta = json.loads(out.with_suffix(".json").read_text())
    assert meta["dropped"] == 40 and meta["sampled"] == 20 and meta["seed"] == 1 and meta["hidden"] == ["reason"]
    labels = tmp_path / "labels.csv"
    labels.write_text("id,first,second\n" + "".join(f"{i},drop,{'keep' if i < 2 else 'drop'}\n" for i in range(20)))
    r = run("rescue", "--labels", labels, "--column", "second", "--positive", "keep", "--dropped-total", 40)
    assert r.returncode == 0 and json.loads(r.stdout)["rescued"] == 2
    r = run("agree", "--labels", labels, "--a", "first", "--b", "second", "--positive", "keep")
    assert r.returncode == 0 and json.loads(r.stdout)["second_only"] == 2
