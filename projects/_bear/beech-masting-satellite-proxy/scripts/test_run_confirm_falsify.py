"""uvx --python 3.12 --with numpy --with pandas --with pytest pytest -q -p no:cacheprovider test_run_confirm_falsify.py"""

# claims and load_spec of run_confirm.py, summary of run_falsify.py.
import hashlib
import json

import numpy as np
import pytest

import run_confirm as rc
import run_falsify as rf

YEARS = range(2000, 2009)


def by_year(v):
    return {"by_year": {t: v for t in YEARS}}


def test_claims_apply_the_plan_rule_to_paired_year_differences():
    # every year: S2 0.4, S1 0.3, B0 0.1, RS2 0.2, R0 0.25 -> differences are constant, so the interval is the point
    within = {"S2": by_year(0.4), "S1": by_year(0.3), "B0": by_year(0.1), "RS2": by_year(0.2), "R0": by_year(0.25)}
    c = rc.claims(within)
    assert c["H"]["diff"] == pytest.approx(0.3) and c["H"]["verdict"] == "supported" and c["H"]["years"] == 9
    assert c["H-cs"]["verdict"] == "supported" and c["H-ps"]["verdict"] == "supported"
    assert c["R-vs-R0"]["diff"] == pytest.approx(-0.05) and c["R-vs-R0"]["verdict"] == "not supported"
    assert c["R-level"]["verdict"] == "supported"                 # RS2 above 0 in every year
    assert c["R"]["verdict"] == "not supported"                    # needs both R-level and R-vs-R0


def test_claims_r_supported_only_when_both_parts_are():
    within = {"S2": by_year(0.4), "S1": by_year(0.3), "B0": by_year(0.1), "RS2": by_year(0.3), "R0": by_year(0.25)}
    assert rc.claims(within)["R"]["verdict"] == "supported"


def test_load_spec_hashes_the_file_text(tmp_path):
    with pytest.raises(SystemExit):
        rc.load_spec(tmp_path)
    body = json.dumps({"coverage_rule": {"min_years": 5}})
    (tmp_path / "b2_frozen_spec.json").write_text(body, encoding="utf-8")
    spec, sha = rc.load_spec(tmp_path)
    assert spec["coverage_rule"]["min_years"] == 5 and sha == hashlib.sha256(body.encode()).hexdigest()


def test_falsify_summary_compares_the_median_real_value_with_the_permutations_p95():
    perm = np.linspace(0.0, 0.19, 20)                               # p95 = 0.1805
    s = rf.summary([0.3] * 20, perm)
    assert s["passes"] and s["perms"] == 20 and s["share_perm_at_least_real"] == 0.0
    assert s["perm_p95"] == pytest.approx(np.percentile(perm, 95)) and s["perm_median"] == pytest.approx(0.095)
    assert s["real_minus_perm_median"] == pytest.approx(0.3 - 0.095)
    s = rf.summary([0.175] * 20, perm)                             # below p95; perms 0.18 and 0.19 reach it
    assert not s["passes"] and s["share_perm_at_least_real"] == pytest.approx(2 / 20)
