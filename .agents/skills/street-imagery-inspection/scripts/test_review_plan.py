"""uvx --with pytest pytest test_review_plan.py

Worked by hand: 100 items, a budget of 10 looks, half on the top. The top 5 by score are all looked at; 5 of the
other 95 are drawn at random, each standing for 19. With 4 positives in the top and 1 of 5 in the sample, the
estimate is 4 + 95 * 0.2 = 23. Wilson 95% for 1 of 5: centre (0.2 + 1.96^2 / 10) / (1 + 1.96^2 / 5) = 0.3304,
half width 1.96 * sqrt(0.2 * 0.8 / 5 + 1.96^2 / 100) / (1 + 1.96^2 / 5) = 0.2941, so 0.0362 to 0.6245, and the
total 4 + 95 * that = 7.4 to 63.3. The ranking alone would have said 4.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from review_plan import estimate, plan  # noqa: E402

IDS = [str(i) for i in range(100)]
SCORES = [float(i) for i in range(100)]


def test_the_top_is_looked_at_in_full_and_the_rest_is_sampled():
    rows = plan(IDS, SCORES, budget=10, top_share=0.5, seed=0)
    top = [r for r in rows if r["stratum"] == "top"]
    rest = [r for r in rows if r["stratum"] == "rest"]
    assert [r["id"] for r in top] == ["99", "98", "97", "96", "95"]
    assert len(rest) == 5 and all(int(r["id"]) < 95 for r in rest)
    assert all(r["stratum_size"] == 5 for r in top) and all(r["stratum_size"] == 95 for r in rest)
    # the same plan whatever the row order; another seed gives another sample of the rest
    assert plan(IDS[::-1], SCORES[::-1], 10, 0.5, 0) == rows
    assert plan(IDS, SCORES, 10, 0.5, 1) != rows


def test_without_a_sample_of_the_rest_nothing_can_be_said_about_what_the_ranking_missed():
    with pytest.raises(SystemExit, match="rest"):
        plan(IDS, SCORES, budget=10, top_share=1.0)
    # a budget that covers everything is a census
    assert {r["stratum"] for r in plan(IDS[:8], SCORES[:8], budget=10)} == {"top"}


def test_ties_are_broken_by_id():
    rows = plan(["b", "a", "c"], [1.0, 1.0, 0.0], budget=3, top_share=0.5)
    assert [r["id"] for r in rows] == ["a", "b", "c"]


def test_the_estimate_adds_the_sampled_rest_to_the_top():
    rows = plan(IDS, SCORES, budget=10, top_share=0.5, seed=0)
    top_pos = {"99", "98", "97", "96"}
    rest_ids = [r["id"] for r in rows if r["stratum"] == "rest"]
    labels = {i: i in top_pos or i == rest_ids[0] for i in IDS}
    e = estimate([dict(r, label="yes" if labels[r["id"]] else "no") for r in rows], positive="yes")
    assert e["top_positives"] == 4 and e["rest_positives_sampled"] == 1 and e["rest_sampled"] == 5
    assert e["total_estimate"] == pytest.approx(23)
    assert e["rest_share_95"] == pytest.approx([0.0362, 0.6245], abs=1e-4)
    assert e["total_95"] == pytest.approx([7.4, 63.3], abs=0.05)
    assert e["top_catches"] == pytest.approx(4 / 23)


def test_command_line_plans_and_estimates(tmp_path):
    scores = tmp_path / "scores.csv"
    scores.write_text("box,score\n" + "".join(f"b{i:02d},{i / 100}\n" for i in range(40)))
    out = tmp_path / "review.csv"
    run = lambda *a: subprocess.run([sys.executable, str(HERE / "review_plan.py"), *map(str, a)],  # noqa: E731
                                    capture_output=True, text=True)
    r = run("plan", scores, "--id", "box", "--score", "score", "--budget", 20, "--out", out)
    assert r.returncode == 0, r.stderr
    rows = out.read_text().splitlines()
    assert rows[0] == "id,score,stratum,stratum_size,label" and len(rows) == 21
    lab = tmp_path / "labelled.csv"
    lab.write_text("\n".join([rows[0]] + [x[:-0 or None] + ("yes" if ",top," in x else "no") for x in rows[1:]]))
    r = run("estimate", lab, "--positive", "yes")
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)["top_positives"] == 10
